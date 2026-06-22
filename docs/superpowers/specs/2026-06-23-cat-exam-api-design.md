# Sub-project G: CAT Exam API — Design Spec

> Source of truth: PRD §11 (CAT 模拟策略) and FR-CAT-01..10 in
> `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md`. Supersedes nothing; extends
> sub-project F (fixed exam API).

## 1. Goal

Add a rule-driven Computerized Adaptive Testing (CAT) exam with **simplified
ability estimation** (NOT 3PL IRT — that is Phase 5, explicitly out of P0
scope per PRD §11.2/§11.3). The CAT session:

- starts at medium difficulty,
- estimates learner ability from successive answers,
- selects the next item by matching difficulty to current ability while
  respecting domain-weight coverage and anti-clustering,
- enforces forward-only / no-skip / non-revisable answering,
- terminates at 150 items or 3 hours, or early (≥100 items) when the ability
  estimate has clearly converged past the passing line,
- produces the same report/review/history shape as the fixed exam, extended
  with ability estimate, confidence interval, readiness level, and the
  "study tool, not official prediction" disclaimer.

## 2. Architecture (Approach A: pure engine + service branch)

A new **DB-free** module `app/services/cat_engine.py` owns all the math and
selection logic. The existing `app/services/exam.py` gains a CAT branch that
owns DB access and delegates pure logic to the engine. The CAT session reuses
the existing `/api/exam/sessions`, `/answers`, `/finish`, `/report`,
`/review`, `/history` routes — the service branches on `session_kind` — plus
one new CAT-only route `GET /api/exam/sessions/{id}/next`.

Rationale: honors the service-layer convention (CLAUDE.md), keeps the engine
trivially unit-testable with synthetic candidates (no Postgres), maximally
reuses the fixed-exam report/review/history machinery, and needs **no
migration** (`ExamSession.session_kind` already has a `cat` value;
`ExamAnswer.ability_estimate_after`/`se_after` Float columns already exist
and are currently unused by the fixed exam; `ExamSession.config` JSONB
already exists).

## 3. Data model (no migration)

`ExamSession` with `session_kind == ExamSessionKind.cat`. The `config` JSONB
column holds all CAT runtime state (see §6). `ExamAnswer` rows store
`ability_estimate_after` and `se_after` (the ability/SEM *after* that answer
was recorded), plus the existing snapshot columns. `Question.difficulty`
(`Integer | None`, range 1–5; missing → 3 per FR-ETL-09) drives selection.
`Question.source` and `QuestionMapping.knowledge_point_id` drive the
anti-clustering rule (PRD §11.1.5).

## 4. `cat_engine.py` (pure, no SQLAlchemy)

Constants:

- `DEFAULT_PARAMS = {"k0": 0.5, "decay": 0.1, "base_se": 1.0, "early_stop_enabled": True}` — snapshotted into `config.cat_params` at session creation so later param changes never retroactively affect running/old exams (parameter-version fidelity, PRD §11.3).
- `DISCLAIMER = "本 CAT 模拟为学习评估工具，其通过/未通过结果不代表 ISC2 官方评分算法的预测。"` (FR-CAT-10).
- `MIN_ITEMS_DEFAULT = 100`, `MAX_ITEMS_DEFAULT = 150` (PRD §11.1.6/7). These come from the blueprint's `min_items`/`max_items` at runtime; the constants are fallbacks only.

Functions (all pure):

- `clamp(x, lo, hi) -> float`.
- `initial_ability() -> 3.0` — PRD §11.1.2 (midpoint of 1–5).
- `default_difficulty(d) -> int` — `d if d in 1..5 else 3`.
- `update_ability(ability, difficulty, correct, answered, params) -> float`:
  - `K_n = params["k0"] / (1 + params["decay"] * answered)` (shrinks as more items are answered → converges).
  - `step = K_n` (transparent additive rule; PRD §11.1.3 only requires "up on correct, down on wrong").
  - `return clamp(ability + (step if correct else -step), 1.0, 5.0)`.
- `sem(answered, params) -> float` — `params["base_se"] / sqrt(max(1, answered))`, floored at `0.05`.
- `passing_ability(passing_score, max_score) -> float` — `1.0 + (passing_score / max_score) * 4.0` (maps 0–1000 onto 1–5; 700 → 3.8).
- `confidence_interval(ability, sem) -> tuple[float, float]` — `(clamp(ability - sem, 1, 5), clamp(ability + sem, 1, 5))`.
- `scaled_score(ability, max_score) -> int` — `round((clamp(ability,1,5) - 1.0) / 4.0 * max_score)` (ability-based, not raw-correct — principled for adaptive exams).
- `readiness_level(ability) -> str` — `≥4.0 "ready"`, `≥3.5 "almost_ready"`, `≥3.0 "developing"`, else `"needs_work"` (PRD §11.3 prefers readiness framing over pass/fail).
- `decide_termination(answered, ability, sem, min_items, max_items, time_up, params) -> TerminationDecision`:
  - `time_up` → `TerminationDecision(True, "time_up")`.
  - `answered >= max_items` → `TerminationDecision(True, "max_items")`.
  - `params["early_stop_enabled"] and answered >= min_items`: compute `lo, hi = confidence_interval(ability, sem)` and `pa = passing_ability(...)`; if `hi < pa` or `lo > pa` → `TerminationDecision(True, "converged")`.
  - else → `TerminationDecision(False, "continue")`.
  - `TerminationDecision` is a small dataclass `{must_stop: bool, reason: str}`.
- `select_next_item(candidates, ability, domain_targets, domain_answered, seen, last_kp, last_source, rng) -> str | None`:
  - Input `candidates` is a list of dicts `{"id": str, "difficulty": int|None, "domain_id": str|None, "knowledge_point_id": str|None, "source": str|None}`.
  - Exclude any `id in seen`.
  - **Domain selection** (FR-CAT-05 domain coverage): compute each domain's deficit `= (target / max_items) * (len(seen) + 1) - domain_answered.get(d, 0)` using `domain_targets` normalized; pick the domain with the largest deficit that still has eligible candidates. (Targets are proportional guides, not hard caps.)
  - Within the chosen domain, choose the candidate whose `default_difficulty(difficulty)` is closest to `ability`; collect all candidates within `+0` difficulty-distance ties.
  - **Anti-clustering** (§11.1.5): among the tied set, prefer candidates with `knowledge_point_id != last_kp` and `source != last_source`; if none, keep the tied set.
  - Break final ties with `rng.choice`.
  - Return the chosen `id`, or `None` if no eligible candidates.
- `select_first_item(candidates, rng) -> str | None` — medium-difficulty start (FR-CAT-04): prefer candidates with `default_difficulty == 3`; if none, pick the one closest to 3; ties → `rng`; empty pool → `None`.

## 5. `exam.py` CAT branch (service layer, owns DB)

Reuses existing helpers: `_load_session`, `_deadline`, `_time_remaining_ms`,
`_auto_submit_if_expired`, `_options_for`, `_judge`, `_allocate`,
`_current_blueprint`, `_domain_question_ids`, `snapshot_question`,
`log_audit`.

### `create_cat_session(session, *, org_id, actor_id, payload) -> ExamSession`

- `bp = _current_blueprint(session)`.
- Snapshot into `config`: `kind="cat"`, `max_score=bp.max_score`, `passing_score=bp.passing_score`, `duration_minutes=bp.duration_minutes`, `min_items=bp.min_items`, `max_items=bp.max_items`, `cat_params=DEFAULT_PARAMS`, `disclaimer=DISCLAIMER`, `deadline_at = now + duration_minutes`, `ability=initial_ability()`, `se=base_se`, `answered=0`, `correct=0`, `question_ids=[]`, `seen=[]`, `domain_answered={}`, `position=0`, `next_question_id=None`.
- Compute `domain_targets` via `_allocate(max_items, [d.weight_pct for d in domains])` → store as `{str(d.id): target}`.
- Fetch candidate pool: all published, tenant-scoped, not-deleted questions mapped to a domain, as the dict shape the engine expects (id, difficulty, domain_id, knowledge_point_id, source).
- `first_id = cat_engine.select_first_item(candidates, rng)`. If `None` → `ValidationError("not enough published questions for CAT")`.
- `config["next_question_id"] = str(first_id)`.
- Create `ExamSession(session_kind=cat, status=in_progress, total_questions=0, correct_count=0, config=config)`. Flush. Audit. Return.

### `get_next_question(session, *, session_id, user_id) -> dict`

- `es = _load_session(...)`; if `_auto_submit_if_expired(...)` or `es.status != in_progress` → `ConflictError`.
- `qid = es.config.get("next_question_id")`; if falsy → `ConflictError("exam session has no next question")`.
- Load question; if missing/deleted → `NotFound`.
- Return the delivery dict (same shape as fixed `get_question_at`): `session_id, position=config["position"], total=config["max_items"], question_id, stem, question_type, options (stripped of is_correct), elapsed_ms, time_remaining_ms, previous_answer=None`.

### `submit_answer` (CAT branch, selected by `es.session_kind == cat`)

- Auto-submit-if-expired → 409 if not in_progress.
- **Forward-only / no-skip**: require `body.position == es.config["position"]`; else `ValidationError("position does not match current CAT position")`.
- `qid = uuid(es.config["next_question_id"])`. Load question; missing/deleted → `NotFound`.
- Judge from snapshot (`_judge`); write `ExamAnswer` with `ability_estimate_after`, `se_after` set to the *new* ability/SEM. (Non-revisable: there is no upsert — a second submit to the same position is rejected by the position check, FR-CAT-02.)
- Update `config`: append `str(qid)` to `question_ids` and `seen`; `answered += 1`; `correct += is_correct`; `new_ability = update_ability(...)`; `new_se = sem(answered, params)`; `config["ability"]`, `config["se"]`; `domain_answered[domain_id] += 1` (domain looked up via `QuestionMapping`); `last_knowledge_point`, `last_source` = the answered item's.
- `decision = cat_engine.decide_termination(answered, new_ability, new_se, min_items, max_items, time_up=False, params)`.
  - (Time-up is handled lazily by `_auto_submit_if_expired` on the *next* interaction; the submit itself does not check time, matching the fixed exam's lazy model. If the deadline elapsed between this submit and the next call, the next `/next` or `/answers` auto-submits.)
  - If `decision.must_stop`: set status (`completed` if reason in {max_items, converged}, `auto_submitted` if reason == time_up — but time_up is detected lazily, so here it's `completed`), `ended_at = now`, `total_questions = answered`, `correct_count = correct`, `next_question_id = None`.
  - Else: fetch candidate pool, `next_id = cat_engine.select_next_item(candidates, new_ability, domain_targets, domain_answered, seen, last_kp, last_source, rng)`. If `None` → terminate as `completed` with reason "exhausted" (pool ran dry). Else `config["next_question_id"] = str(next_id)`, `config["position"] += 1`.
- Flush. Audit (answer + ability). Return `ExamAnswerAck(position=body.position, saved=True, time_remaining_ms=..., finished=decision.must_stop)`.

### `finish_session` (CAT branch)

- Manual early-finish (user gives up). Auto-submit-if-expired first. If still in_progress: set `completed`, `ended_at = now`, `total_questions = answered`, `correct_count = correct`, `next_question_id = None`. Flush. Audit. Return `_build_report(...)`.

### `_build_report` (CAT branch)

- `scaled_score = cat_engine.scaled_score(config["ability"], max_score)`.
- `passed = scaled_score >= passing_score` (ability-based).
- `accuracy = correct / answered if answered else 0.0`.
- Per-domain grouping via `QuestionMapping.domain_id` (same as fixed).
- Wrong-question list from snapshots (same as fixed).
- **Plus CAT-only fields**: `ability_estimate = config["ability"]`, `sem = config["se"]`, `ability_ci_lower/upper = confidence_interval(...)`, `readiness_level = cat_engine.readiness_level(ability)`, `disclaimer = config["disclaimer"]`.

### `_scaled` (CAT branch for `list_history`)

- `scaled = cat_engine.scaled_score(config["ability"], max_score)`; `passed = scaled >= passing_score`; `accuracy = correct / total if total else 0.0`. (`total_questions`/`correct_count` were set at termination.)

### `get_review` — unchanged

The snapshot-graded review works for both kinds, ordered by `config["question_ids"]`. CAT has no "unanswered item" positions (you only review what you answered), so no live-fallback branch is exercised.

## 6. CAT `config` JSONB shape

```jsonc
{
  "kind": "cat",
  "question_ids": [],             // answered, in order (grows)
  "next_question_id": "uuid",     // item selected to deliver next; null when ended
  "position": 0,                  // == len(question_ids)
  "ability": 3.0,
  "se": 1.0,
  "answered": 0,
  "correct": 0,
  "domain_targets": {"<domain_id>": <target>},
  "domain_answered": {"<domain_id>": <count>},
  "seen": [],                     // answered qids (exclusion set)
  "last_knowledge_point": null,
  "last_source": null,
  "deadline_at": "<iso>",
  "max_score": 1000,
  "passing_score": 700,
  "duration_minutes": 180,
  "min_items": 100,
  "max_items": 150,
  "cat_params": {"k0":0.5,"decay":0.1,"base_se":1.0,"early_stop_enabled":true},
  "disclaimer": "..."
}
```

`_session_out` strips internal keys from the public `config`: `question_ids`,
`next_question_id`, `seen`, `domain_targets`, `domain_answered`,
`cat_params`.

## 7. Schema changes (`app/schemas/exam.py`)

- `ExamCreateIn`: add `kind: str = "fixed"` (values `"fixed"` / `"cat"`; `count` ignored for cat).
- `ExamAnswerAck`: add `finished: bool = False`.
- `ExamReportOut`: add `ability_estimate: float | None = None`, `ability_ci_lower: float | None = None`, `ability_ci_upper: float | None = None`, `sem: float | None = None`, `readiness_level: str | None = None`, `disclaimer: str | None = None`.
- `QuestionDeliveryOut`, `ReviewItemOut`, `ExamHistoryItemOut`: unchanged.

## 8. API surface (`app/api/exam.py`)

- `POST /api/exam/sessions` — extended: branches on `body.kind`.
- `GET /api/exam/sessions/{id}/next` — **new**, CAT-only. For a `fixed` session → `409` (fixed uses `/questions/{position}`). Delivers the adaptively-selected current item.
- `POST /api/exam/sessions/{id}/answers` — shared; service branches on `session_kind`.
- `POST /api/exam/sessions/{id}/finish`, `GET .../report`, `GET .../review`, `GET /history` — shared; service branches.
- All gated by `require_permission("exam:read")`. Error mapping unchanged: `NotFound`→404, `ValidationError`→422, `ConflictError`→409.

## 9. Error handling & edge cases

- Empty candidate pool at create or at next-item selection → `ValidationError` (422) "not enough published questions for CAT" / terminate as `completed` reason "exhausted".
- First-item medium pool empty → `select_first_item` falls back to closest-to-3 available.
- Submit to a finished session → 409. Position mismatch → 422 (forward-only/no-skip). Non-owner → 404.
- Time-up detected lazily on `/next` or `/answers` via `_auto_submit_if_expired` → status `auto_submitted`.
- `Question.difficulty is None` → treated as 3 (via `default_difficulty`).
- No current blueprint → 422 (reuse `_current_blueprint`).

## 10. Testing

### `tests/test_cat_engine.py` (pure, fast, no DB)

- `update_ability`: correct↑ / wrong↓, shrinkage with `answered`, clamp to [1,5].
- `sem`: decreases with `answered`, floored.
- `passing_ability`: 700/1000 → 3.8.
- `confidence_interval`: clamps to [1,5].
- `scaled_score`: ability 3 → 500, 5 → 1000, 1 → 0.
- `readiness_level`: all four bands.
- `decide_termination`: each branch — `time_up`, `max_items`, `converged` (pass: `lo > pa`), `converged` (fail: `hi < pa`), `continue` (below min_items), `continue` (CI straddles pa), `early_stop_enabled=False` disables convergence.
- `select_next_item`: closest-difficulty wins; domain-deficit priority picks the behind domain; `seen` excluded; anti-clustering prefers different kp/source among ties; empty pool → None.
- `select_first_item`: prefers difficulty 3; falls back to closest-to-3; empty → None.

### `tests/test_exam_service.py` (CAT branch, real DB)

- Create CAT session: medium start, config shape, `session_kind=cat`, status in_progress.
- `/next` delivers current item, strips `is_correct`, `previous_answer=None`.
- Submit is non-revisable: second submit at same position → 422/409; advances position.
- Forward-only: submit with wrong position → 422.
- ability/se advance on each answer; `ExamAnswer.ability_estimate_after`/`se_after` populated.
- Auto-terminate at `max_items` (use a small max for the test) → completed.
- Early-stop when CI converges past `min_items` (use small min + extreme answers) → completed.
- Time-up auto-submit (force `deadline_at` into the past) → auto_submitted.
- Report carries ability/CI/readiness/disclaimer; `passed`/`scaled_score` are ability-based.
- Review is snapshot-graded (mutate live options after answer; review still shows original).
- History: CAT item scaled/passed are ability-based; only completed/auto_submitted appear.

### `tests/test_exam_api.py` (CAT HTTP)

- Happy path: create cat → `/next` → answer×N → auto-finish → `/report` → `/review` → `/history`.
- 401 without token.
- Other-user 404.
- Submit wrong position → 422.
- `GET /next` on a fixed session → 409.

## 11. Out of scope (explicitly deferred)

- Full 3PL IRT (a/b/c/theta calibration) — Phase 5 (PRD §11.2).
- Admin-tunable CAT params UI + saved param versions — sub-project H (FR-ADMIN-04, P1); MVP snapshots `DEFAULT_PARAMS`.
- Real-time pass-probability display — never (FR-CAT-08, P1; not built).
- Item exposure rate control — Phase 5.

## 12. FR coverage

| FR | Priority | Coverage |
|----|----------|----------|
| FR-CAT-01 3h/100–150 CAT | P0 | blueprint duration + min/max_items; §5 create, §4 termination |
| FR-CAT-02 no revise | P0 | submit position-check, no upsert; §5 submit |
| FR-CAT-03 no skip | P0 | `/next` delivers only current; submit requires current position; §5 |
| FR-CAT-04 medium start | P0 | `select_first_item`; §4, §5 create |
| FR-CAT-05 adaptive + domain + difficulty | P0 | `select_next_item` + `update_ability`; §4, §5 submit |
| FR-CAT-06 early stop ≥100 if decided | P1 | `decide_termination` converged branch; §4, §5 |
| FR-CAT-07 must end at 150/3h | P0 | `decide_termination` max_items/time_up + lazy auto-submit; §4, §5 |
| FR-CAT-08 no real-time pass prob | P1 | submit ack returns no correctness/pass-prob; §5 |
| FR-CAT-09 report: ability/CI/domain/suggestions | P1 | `_build_report` CAT branch + readiness; §5 |
| FR-CAT-10 disclaimer | P0 | `DISCLAIMER` in config + report; §4, §5 |
