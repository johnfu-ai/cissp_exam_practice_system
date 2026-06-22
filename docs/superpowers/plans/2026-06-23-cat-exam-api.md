# CAT Exam API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a rule-driven Computerized Adaptive Testing (CAT) exam (sub-project G, FR-CAT-01..10) with simplified ability estimation that reuses the existing ExamSession/ExamAnswer models and the fixed-exam report/review/history machinery.

**Architecture:** A new DB-free `app/services/cat_engine.py` owns all ability/selection/termination math (pure functions, unit-testable without Postgres). `app/services/exam.py` gains CAT branches that own DB access and delegate pure logic to the engine. The CAT session reuses the existing `/api/exam/sessions`, `/answers`, `/finish`, `/report`, `/review`, `/history` routes (service branches on `session_kind`) plus one new CAT-only route `GET /sessions/{id}/next`. No migration: `ExamSession.session_kind` already has a `cat` value and `ExamAnswer.ability_estimate_after`/`se_after` Float columns already exist.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Pydantic v2, PostgreSQL 16 JSONB, pytest (real `cissp_test` DB).

**Branch:** `feat/cat-exam-api` off `master`.

## Global Constraints

- Tests run against the dedicated `cissp_test` DB (NOT dev `cissp`); per-test SAVEPOINT rollback. Tests use `Base.metadata.create_all`, NOT migrations — a model change needs a migration too (for dev DB + drift test), but this sub-project adds NO model columns so NO migration is needed.
- Service-layer backend: routes delegate to `app/services/exam.py`; caller commits the session after successful mutations; `log_audit` flushes but does NOT commit.
- CAT answers are NON-revisable and NON-skippable (forward-only) — this DIFFERS from the fixed exam where answers ARE revisable. CAT submit enforces one-shot via a position check (no upsert).
- CAT is a study tool, not an ISC2 official prediction (PRD §11.3): the report carries a disclaimer (FR-CAT-10) and prefers "readiness"/"weak areas" framing; full 3PL IRT is Phase 5, out of scope.
- Do NOT name a route handler `get_session` — it shadows the `get_session` DB-session dependency. The exam detail handler is `get_exam_detail`.
- NFR-DATA-01: completed answers store a snapshot at answer time (`ExamAnswer.question_snapshot`/`options_snapshot`); judge and review from the snapshot, not live options.
- `Question.difficulty` is `Integer | None`, range 1–5; missing → 3 (medium). `Question.source` and `QuestionMapping.knowledge_point_id` drive the anti-clustering rule.
- Do not touch the uncommitted working-tree edit to `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` (not ours).
- Activate venv from `backend/`: `cd /home/john/cissp_exam/backend && source venv/bin/activate`. Run pytest from `backend/`.
- Default branch is `master` (not `main`).

---

## File Structure

- **Create** `backend/app/services/cat_engine.py` — pure CAT math (no SQLAlchemy): constants, ability update, SEM, passing-ability mapping, confidence interval, scaled score, readiness bands, termination decision, first-item selection, next-item selection.
- **Create** `backend/tests/test_cat_engine.py` — pure unit tests for the engine (no DB).
- **Modify** `backend/app/schemas/exam.py` — add `ExamCreateIn.kind`, `ExamAnswerAck.finished`, CAT fields on `ExamReportOut`.
- **Modify** `backend/app/services/exam.py` — add CAT branches in `create_session`, `submit_answer`, `finish_session`, `_build_report`, `_scaled`; add `create_cat_session`, `get_next_question`, `_cat_candidate_pool`, `_submit_cat_answer`, `_build_cat_report`, `_domain_and_wrong` helpers.
- **Modify** `backend/app/api/exam.py` — add `GET /sessions/{id}/next` route; extend `_session_out` to strip CAT-internal config keys.
- **Modify** `backend/tests/test_exam_service.py` — CAT service-layer tests.
- **Modify** `backend/tests/test_exam_api.py` — CAT HTTP tests.
- **Modify** `CLAUDE.md` — record sub-project G completion.

---

### Task 1: Engine math module

**Files:**
- Create: `backend/app/services/cat_engine.py`
- Test: `backend/tests/test_cat_engine.py`

**Interfaces:**
- Produces: `DEFAULT_PARAMS`, `DISCLAIMER`, `MIN_ITEMS_DEFAULT`, `MAX_ITEMS_DEFAULT`, `TerminationDecision` (dataclass `{must_stop: bool, reason: str}`), `clamp(x, lo, hi) -> float`, `initial_ability() -> float`, `default_difficulty(d) -> int`, `update_ability(ability, difficulty, correct, answered, params) -> float`, `sem(answered, params) -> float`, `passing_ability(passing_score, max_score) -> float`, `confidence_interval(ability, sem) -> tuple[float, float]`, `scaled_score(ability, max_score) -> int`, `readiness_level(ability) -> str`, `decide_termination(answered, ability, sem, min_items, max_items, time_up, passing_ability, params) -> TerminationDecision`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cat_engine.py`:

```python
"""Pure unit tests for the CAT engine (no DB)."""

import math

from app.services import cat_engine as ce


def test_initial_ability_is_median():
    assert ce.initial_ability() == 3.0


def test_default_difficulty():
    assert ce.default_difficulty(3) == 3
    assert ce.default_difficulty(None) == 3
    assert ce.default_difficulty(7) == 3  # out of range -> 3
    assert ce.default_difficulty(0) == 3
    assert ce.default_difficulty(5) == 5
    assert ce.default_difficulty(1) == 1


def test_update_ability_direction_and_shrinkage_and_clamp():
    p = ce.DEFAULT_PARAMS
    # correct raises, wrong lowers
    up = ce.update_ability(3.0, 3, True, 0, p)
    down = ce.update_ability(3.0, 3, False, 0, p)
    assert up > 3.0
    assert down < 3.0
    # step shrinks as more items answered
    step0 = up - 3.0
    step_later = ce.update_ability(3.0, 3, True, 20, p) - 3.0
    assert step_later < step0
    # clamps to [1, 5]
    hi = ce.update_ability(4.9, 3, True, 0, p)
    assert hi == 5.0
    lo = ce.update_ability(1.1, 3, False, 0, p)
    assert lo == 1.0


def test_sem_decreases_and_floored():
    p = ce.DEFAULT_PARAMS
    s1 = ce.sem(1, p)
    s10 = ce.sem(100, p)
    assert s10 < s1
    assert s10 >= 0.05  # floor


def test_passing_ability():
    assert ce.passing_ability(700, 1000) == 3.8
    assert ce.passing_ability(0, 1000) == 1.0
    assert ce.passing_ability(1000, 1000) == 5.0


def test_confidence_interval_clamps():
    lo, hi = ce.confidence_interval(1.2, 1.0)
    assert lo == 1.0
    assert math.isclose(hi, 2.2)
    lo2, hi2 = ce.confidence_interval(4.8, 1.0)
    assert hi2 == 5.0


def test_scaled_score():
    assert ce.scaled_score(3.0, 1000) == 500
    assert ce.scaled_score(5.0, 1000) == 1000
    assert ce.scaled_score(1.0, 1000) == 0


def test_readiness_level_bands():
    assert ce.readiness_level(4.5) == "ready"
    assert ce.readiness_level(3.6) == "almost_ready"
    assert ce.readiness_level(3.0) == "developing"
    assert ce.readiness_level(2.0) == "needs_work"


def test_termination_time_up():
    p = ce.DEFAULT_PARAMS
    d = ce.decide_termination(50, 3.0, 0.5, 100, 150, True, 3.8, p)
    assert d.must_stop is True
    assert d.reason == "time_up"


def test_termination_max_items():
    p = ce.DEFAULT_PARAMS
    d = ce.decide_termination(150, 3.0, 0.5, 100, 150, False, 3.8, p)
    assert d.must_stop is True
    assert d.reason == "max_items"


def test_termination_converged_pass():
    # ability high, CI entirely above passing line
    p = ce.DEFAULT_PARAMS
    # answered >= min_items, lo > pa
    d = ce.decide_termination(100, 4.5, 0.1, 100, 150, False, 3.8, p)
    assert d.must_stop is True
    assert d.reason == "converged"


def test_termination_converged_fail():
    p = ce.DEFAULT_PARAMS
    # ability low, CI entirely below passing line (hi < pa)
    d = ce.decide_termination(100, 2.0, 0.1, 100, 150, False, 3.8, p)
    assert d.must_stop is True
    assert d.reason == "converged"


def test_termination_continue_below_min_items():
    p = ce.DEFAULT_PARAMS
    d = ce.decide_termination(5, 5.0, 0.05, 100, 150, False, 3.8, p)
    assert d.must_stop is False
    assert d.reason == "continue"


def test_termination_continue_ci_straddles():
    p = ce.DEFAULT_PARAMS
    # ability 3.8, sem 1.0 -> CI [2.8, 4.8] straddles pa=3.8
    d = ce.decide_termination(120, 3.8, 1.0, 100, 150, False, 3.8, p)
    assert d.must_stop is False
    assert d.reason == "continue"


def test_termination_early_stop_disabled():
    p = {**ce.DEFAULT_PARAMS, "early_stop_enabled": False}
    d = ce.decide_termination(120, 5.0, 0.05, 100, 150, False, 3.8, p)
    assert d.must_stop is False  # convergence disabled, below max
    assert d.reason == "continue"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_cat_engine.py -v`
Expected: collection error / `ModuleNotFoundError: app.services.cat_engine`.

- [ ] **Step 3: Implement the engine math**

Create `backend/app/services/cat_engine.py`:

```python
"""CAT engine: rule-driven, simplified ability estimation (PRD §11.1).

Pure functions only — no SQLAlchemy, no DB. The service layer
(`app/services/exam.py`) owns DB access and delegates math here so the
engine is trivially unit-testable with synthetic inputs.

This is NOT 3PL IRT (Phase 5, out of P0 scope). Ability is a transparent
1–5 scale updated by shrunk additive steps; SEM shrinks as 1/sqrt(n).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


DEFAULT_PARAMS = {
    "k0": 0.5,            # base ability step
    "decay": 0.1,         # step shrinkage rate with items answered
    "base_se": 1.0,       # SEM numerator
    "early_stop_enabled": True,
}

DISCLAIMER = (
    "本 CAT 模拟为学习评估工具，其通过/未通过结果不代表 ISC2 官方评分算法的预测。"
)

MIN_ITEMS_DEFAULT = 100
MAX_ITEMS_DEFAULT = 150
ABILITY_MIN = 1.0
ABILITY_MAX = 5.0
SEM_FLOOR = 0.05


@dataclass(frozen=True)
class TerminationDecision:
    must_stop: bool
    reason: str  # "time_up" | "max_items" | "converged" | "continue"


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def initial_ability() -> float:
    """PRD §11.1.2: learner initial ability is the midpoint of 1–5."""
    return 3.0


def default_difficulty(d) -> int:
    """Map a Question.difficulty (int|None, range 1–5) to a valid 1–5 int; missing/invalid -> 3."""
    if isinstance(d, int) and 1 <= d <= 5:
        return d
    return 3


def update_ability(ability: float, difficulty, correct: bool, answered: int, params: dict) -> float:
    """PRD §11.1.3: ability rises on correct, falls on wrong; step shrinks with items answered."""
    k_n = params["k0"] / (1.0 + params["decay"] * max(0, answered))
    step = k_n
    new = ability + (step if correct else -step)
    return clamp(new, ABILITY_MIN, ABILITY_MAX)


def sem(answered: int, params: dict) -> float:
    """Standard error of measurement: shrinks as 1/sqrt(n), floored."""
    n = max(1, answered)
    return max(SEM_FLOOR, params["base_se"] / math.sqrt(n))


def passing_ability(passing_score: int, max_score: int) -> float:
    """Map the 0–max_score passing line onto the 1–5 ability space.

    700/1000 -> 3.8.
    """
    if max_score <= 0:
        return ABILITY_MIN
    ratio = min(1.0, max(0.0, passing_score / max_score))
    return ABILITY_MIN + ratio * (ABILITY_MAX - ABILITY_MIN)


def confidence_interval(ability: float, sem_value: float) -> tuple[float, float]:
    lo = clamp(ability - sem_value, ABILITY_MIN, ABILITY_MAX)
    hi = clamp(ability + sem_value, ABILITY_MIN, ABILITY_MAX)
    return lo, hi


def scaled_score(ability: float, max_score: int) -> int:
    """Ability-based scaled score (adaptive exams are scored on ability, not raw correct)."""
    ratio = (clamp(ability, ABILITY_MIN, ABILITY_MAX) - ABILITY_MIN) / (ABILITY_MAX - ABILITY_MIN)
    return round(ratio * max_score)


def readiness_level(ability: float) -> str:
    """PRD §11.3: prefer readiness framing over pass/fail."""
    if ability >= 4.0:
        return "ready"
    if ability >= 3.5:
        return "almost_ready"
    if ability >= 3.0:
        return "developing"
    return "needs_work"


def decide_termination(
    answered: int,
    ability: float,
    sem_value: float,
    min_items: int,
    max_items: int,
    time_up: bool,
    pass_ability: float,
    params: dict,
) -> TerminationDecision:
    """PRD §11.1.6/7: end at 150 items or 3h; may end >=100 if ability has converged."""
    if time_up:
        return TerminationDecision(True, "time_up")
    if answered >= max_items:
        return TerminationDecision(True, "max_items")
    if params.get("early_stop_enabled", True) and answered >= min_items:
        lo, hi = confidence_interval(ability, sem_value)
        if hi < pass_ability or lo > pass_ability:
            return TerminationDecision(True, "converged")
    return TerminationDecision(False, "continue")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_cat_engine.py -v`
Expected: 14 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/cat_engine.py backend/tests/test_cat_engine.py
git commit -m "feat(cat): pure engine math module (ability/sem/termination)"
```

---

### Task 2: Engine item selection

**Files:**
- Modify: `backend/app/services/cat_engine.py` (append selection functions)
- Modify: `backend/tests/test_cat_engine.py` (append selection tests)

**Interfaces:**
- Consumes: `default_difficulty` from Task 1.
- Produces: `select_first_item(candidates, rng) -> str | None`, `select_next_item(candidates, ability, domain_targets, domain_answered, seen, last_kp, last_source, rng) -> str | None`. `candidates` is a list of dicts `{"id": str, "difficulty": int|None, "domain_id": str|None, "knowledge_point_id": str|None, "source": str|None}`. `rng` is a `random.Random`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_cat_engine.py`:

```python
import random


def _cand(cid, difficulty=None, domain_id="d1", kp=None, source=None):
    return {"id": cid, "difficulty": difficulty, "domain_id": domain_id,
            "knowledge_point_id": kp, "source": source}


def test_select_first_item_prefers_medium():
    candidates = [_cand("hard", 5), _cand("easy", 1), _cand("mid", 3)]
    rng = random.Random(0)
    assert ce.select_first_item(candidates, rng) == "mid"


def test_select_first_item_falls_back_to_closest():
    candidates = [_cand("hard", 5), _cand("easy", 1)]
    rng = random.Random(0)
    # closest to 3 is 5 (dist 2) vs 1 (dist 2) -> tie, rng picks one of them
    choice = ce.select_first_item(candidates, rng)
    assert choice in {"hard", "easy"}


def test_select_first_item_empty_pool():
    assert ce.select_first_item([], random.Random(0)) is None


def test_select_next_item_excludes_seen():
    candidates = [_cand("a", 3), _cand("b", 3)]
    rng = random.Random(0)
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 2}, {}, ["a"], None, None, rng)
    assert choice == "b"


def test_select_next_item_closest_difficulty():
    candidates = [_cand("a", 1), _cand("b", 4), _cand("c", 5)]
    rng = random.Random(0)
    # ability 4.2 -> closest is b (4)
    choice = ce.select_next_item(
        candidates, 4.2, {"d1": 3}, {}, [], None, None, rng)
    assert choice == "b"


def test_select_next_item_domain_deficit_priority():
    # Two domains; d2 is behind on coverage -> pick from d2 even though its
    # item is farther from ability.
    candidates = [
        _cand("a1", 3, domain_id="d1"),
        _cand("b1", 5, domain_id="d2"),
    ]
    rng = random.Random(0)
    # targets: d1=1, d2=2; answered: d1=1, d2=0 -> d2 has larger deficit
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 1, "d2": 2}, {"d1": 1},
        [], None, None, rng)
    assert choice == "b1"


def test_select_next_item_empty_pool():
    rng = random.Random(0)
    assert ce.select_next_item([], 3.0, {}, {}, [], None, None, rng) is None


def test_select_next_item_anti_cluster_prefers_different_kp_and_source():
    # Two items equally close to ability; one shares kp+source with last.
    candidates = [
        _cand("same", 3, kp="k1", source="s1"),
        _cand("fresh", 3, kp="k2", source="s2"),
    ]
    rng = random.Random(0)
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 2}, {}, [], "k1", "s1", rng)
    assert choice == "fresh"


def test_select_next_item_anti_cluster_falls_back_when_all_same():
    candidates = [_cand("only", 3, kp="k1", source="s1")]
    rng = random.Random(0)
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 1}, {}, [], "k1", "s1", rng)
    assert choice == "only"


def test_select_next_item_domain_with_no_candidates_falls_to_other():
    # d1 has candidates but d2 (higher deficit) has none -> fall back to d1.
    candidates = [_cand("a1", 3, domain_id="d1")]
    rng = random.Random(0)
    choice = ce.select_next_item(
        candidates, 3.0, {"d1": 1, "d2": 5}, {"d2": 0},
        [], None, None, rng)
    assert choice == "a1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_cat_engine.py -k "select" -v`
Expected: FAIL — `select_first_item` / `select_next_item` not defined.

- [ ] **Step 3: Implement selection functions**

Append to `backend/app/services/cat_engine.py`:

```python
def select_first_item(candidates: list[dict], rng) -> str | None:
    """FR-CAT-04: start from a medium-difficulty item; fall back to closest-to-3."""
    if not candidates:
        return None
    medium = [c for c in candidates if default_difficulty(c.get("difficulty")) == 3]
    if medium:
        return rng.choice(medium)["id"]
    # fall back to the candidate whose difficulty is closest to 3
    best_diff = min(abs(default_difficulty(c.get("difficulty")) - 3) for c in candidates)
    tied = [c for c in candidates if abs(default_difficulty(c.get("difficulty")) - 3) == best_diff]
    return rng.choice(tied)["id"]


def select_next_item(
    candidates: list[dict],
    ability: float,
    domain_targets: dict,
    domain_answered: dict,
    seen: list,
    last_kp,
    last_source,
    rng,
) -> str | None:
    """FR-CAT-05 + §11.1.5: pick by domain coverage deficit, then closest
    difficulty to current ability, with anti-clustering by knowledge point
    and source among ties."""
    seen_set = set(seen)
    eligible = [c for c in candidates if c["id"] not in seen_set]
    if not eligible:
        return None

    by_domain: dict[str | None, list[dict]] = {}
    for c in eligible:
        by_domain.setdefault(c.get("domain_id"), []).append(c)

    def deficit(did) -> int:
        target = domain_targets.get(did, 0) if domain_targets else 0
        return target - domain_answered.get(did, 0)

    # Among domains that still have eligible candidates, pick the largest deficit.
    best_domain = max(by_domain.keys(), key=lambda did: (deficit(did), did or ""))
    pool = by_domain[best_domain]

    def diff(c) -> float:
        return abs(default_difficulty(c.get("difficulty")) - ability)

    best_diff = min(diff(c) for c in pool)
    tied = [c for c in pool if diff(c) == best_diff]

    fresh = [
        c for c in tied
        if c.get("knowledge_point_id") != last_kp and c.get("source") != last_source
    ]
    chosen_pool = fresh if fresh else tied
    return rng.choice(chosen_pool)["id"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_cat_engine.py -v`
Expected: all engine tests pass (24 total).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/cat_engine.py backend/tests/test_cat_engine.py
git commit -m "feat(cat): engine first-item + next-item selection"
```

---

### Task 3: Schemas for CAT

**Files:**
- Modify: `backend/app/schemas/exam.py`

**Interfaces:**
- Produces: `ExamCreateIn.kind: str = "fixed"`, `ExamAnswerAck.finished: bool = False`, and optional CAT fields on `ExamReportOut` (`ability_estimate`, `ability_ci_lower`, `ability_ci_upper`, `sem`, `readiness_level`, `disclaimer`).

- [ ] **Step 1: Add `kind` to `ExamCreateIn`**

In `backend/app/schemas/exam.py`, replace the `ExamCreateIn` class:

```python
class ExamCreateIn(BaseModel):
    kind: str = Field(default="fixed", pattern="^(fixed|cat)$")
    count: int | None = Field(default=None, ge=1, le=500)
```

- [ ] **Step 2: Add `finished` to `ExamAnswerAck`**

Replace the `ExamAnswerAck` class:

```python
class ExamAnswerAck(BaseModel):
    position: int
    saved: bool
    time_remaining_ms: int
    finished: bool = False
```

- [ ] **Step 3: Add CAT fields to `ExamReportOut`**

Replace the `ExamReportOut` class:

```python
class ExamReportOut(BaseModel):
    session_id: uuid.UUID
    status: str
    total_questions: int
    answered_count: int
    correct_count: int
    scaled_score: int
    max_score: int
    passing_score: int
    passed: bool
    accuracy: float
    total_time_ms: int
    avg_time_ms: float
    domains: list[DomainPerformance]
    wrong_questions: list[WrongQuestion]
    # CAT-only (None for fixed exams):
    ability_estimate: float | None = None
    ability_ci_lower: float | None = None
    ability_ci_upper: float | None = None
    sem: float | None = None
    readiness_level: str | None = None
    disclaimer: str | None = None
```

- [ ] **Step 4: Verify existing tests still pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_service.py tests/test_exam_api.py -q`
Expected: all previously-passing exam tests still pass (schemas are backward-compatible — new fields are optional with defaults).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/schemas/exam.py
git commit -m "feat(exam): schemas for CAT (kind/finished/report fields)"
```

---

### Task 4: Service — CAT session creation + next-item delivery

**Files:**
- Modify: `backend/app/services/exam.py`
- Modify: `backend/tests/test_exam_service.py`

**Interfaces:**
- Consumes: `cat_engine.initial_ability`, `cat_engine.DEFAULT_PARAMS`, `cat_engine.DISCLAIMER`, `cat_engine.select_first_item` (Tasks 1–2); existing `_current_blueprint`, `_allocate`, `_load_session`, `_auto_submit_if_expired`, `_options_for`, `_time_remaining_ms`, `snapshot_question`, `log_audit`.
- Produces: `create_cat_session(session, *, org_id, actor_id, bp) -> ExamSession`, `get_next_question(session, *, session_id, user_id) -> dict`, `_cat_candidate_pool(session, *, org_id, blueprint) -> list[dict]`. Also modifies `create_session` to branch on `body.kind`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_exam_service.py`:

```python
def _cat_blueprint(db_session, *, min_items=1, max_items=5, passing_score=700,
                   max_score=1000, duration_minutes=30):
    bp = _blueprint(
        db_session, min_items=min_items, max_items=max_items,
        passing_score=passing_score, max_score=max_score,
        duration_minutes=duration_minutes, version="cat-v1",
    )
    d1 = _domain(db_session, bp, number=1, name="D1", weight_pct=100)
    return bp, d1


def _seed_cat_questions(db_session, org, actor, domain, n=5, difficulty=3):
    qs = []
    for i in range(n):
        q = _question(db_session, org, actor, stem=f"cat-q{i}", difficulty=difficulty)
        _map(db_session, q, domain)
        qs.append(q)
    return qs


def test_create_cat_session_medium_start_and_config_shape(db_session):
    from app.models.enums import ExamSessionKind, ExamSessionStatus

    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5, difficulty=3)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    assert es.session_kind == ExamSessionKind.cat
    assert es.status == ExamSessionStatus.in_progress
    cfg = es.config
    assert cfg["kind"] == "cat"
    assert cfg["ability"] == 3.0
    assert cfg["answered"] == 0
    assert cfg["position"] == 0
    assert cfg["next_question_id"]  # first item selected
    assert cfg["question_ids"] == []
    assert cfg["max_items"] == 5
    assert cfg["min_items"] == 1
    assert "deadline_at" in cfg
    assert "disclaimer" in cfg
    assert "cat_params" in cfg


def test_create_cat_first_item_is_medium_difficulty(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    qs = _seed_cat_questions(db_session, org, actor, d1, n=5, difficulty=3)
    # add a couple of extreme-difficulty items that must NOT be chosen first
    hard = _question(db_session, org, actor, stem="hard", difficulty=5)
    _map(db_session, hard, d1)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    first_id = uuid.UUID(es.config["next_question_id"])
    chosen = next(q for q in qs if q.id == first_id)
    assert chosen.difficulty == 3


def test_create_cat_rejects_empty_pool(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session)  # no questions seeded
    with pytest.raises(svc.ValidationError):
        svc.create_session(
            db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
        )


def test_get_next_question_strips_correctness(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    out = svc.get_next_question(db_session, session_id=es.id, user_id=actor.id)
    assert out["position"] == 0
    assert out["total"] == 5
    for opt in out["options"]:
        assert "is_correct" not in opt
    assert out["previous_answer"] is None
    assert out["time_remaining_ms"] > 0


def test_get_next_question_other_user_404(db_session):
    org = _org(db_session)
    actor = _actor(db_session, org)
    intruder = _actor(db_session, org, email="other@example.com")
    bp, d1 = _cat_blueprint(db_session, min_items=1, max_items=5)
    _seed_cat_questions(db_session, org, actor, d1, n=5)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    with pytest.raises(svc.NotFound):
        svc.get_next_question(db_session, session_id=es.id, user_id=intruder.id)
```

Also add a `difficulty` kwarg to the existing `_question` helper. Replace the `_question` function signature and body:

```python
def _question(db_session, org, actor, *, stem="q",
              qtype=QuestionType.single_choice, options=None, difficulty=None):
    q = Question(
        organization_id=org.id,
        question_type=qtype,
        stem=stem,
        stem_format=TextFormat.markdown,
        status=QuestionStatus.published,
        created_by_id=actor.id,
        difficulty=difficulty,
    )
    db_session.add(q)
    db_session.flush()
    opts = options if options is not None else [
        (0, "A", True),
        (1, "B", False),
    ]
    for order_index, content, is_correct in opts:
        db_session.add(QuestionOption(
            question_id=q.id, order_index=order_index, content=content,
            content_format=TextFormat.markdown, is_correct=is_correct,
        ))
    db_session.flush()
    return q
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_service.py -k "cat" -v`
Expected: FAIL — `create_session` ignores `kind` and runs fixed assembly (which needs `count`/assembly, producing wrong shape or errors); `get_next_question` does not exist.

- [ ] **Step 3: Implement CAT creation + next delivery**

In `backend/app/services/exam.py`:

Add to the imports at the top (after the existing `from app.services.snapshot import snapshot_question` line):

```python
from app.services import cat_engine
from sqlalchemy.orm.attributes import flag_modified
```

Modify `create_session` to branch on `kind`. Replace the existing `create_session` function body's first lines. The new `create_session`:

```python
def create_session(
    session: Session, *, org_id, actor_id, payload
) -> ExamSession:
    body = _as_create_in(payload)
    bp = _current_blueprint(session)
    if getattr(body, "kind", "fixed") == "cat":
        return create_cat_session(session, org_id=org_id, actor_id=actor_id, bp=bp)
    count = body.count if body.count else bp.max_items
    if count < bp.min_items:
        count = bp.min_items
    if count > bp.max_items:
        count = bp.max_items
    question_ids = _assemble(session, org_id=org_id, blueprint=bp, count=count)
    if not question_ids:
        raise ValidationError(
            f"not enough published questions to assemble a {count}-question exam"
        )
    started = datetime.now(timezone.utc)
    deadline = started + timedelta(minutes=bp.duration_minutes)
    config = {
        "count": len(question_ids),
        "question_ids": [str(q) for q in question_ids],
        "deadline_at": deadline.isoformat(),
        "max_score": bp.max_score,
        "passing_score": bp.passing_score,
        "duration_minutes": bp.duration_minutes,
    }
    es = ExamSession(
        user_id=actor_id,
        organization_id=org_id,
        blueprint_id=bp.id,
        session_kind=ExamSessionKind.fixed,
        status=ExamSessionStatus.in_progress,
        total_questions=len(question_ids),
        correct_count=0,
        config=config,
    )
    session.add(es)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
        entity_type="exam_session", entity_id=str(es.id),
        details={"total_questions": len(question_ids), "kind": "fixed"},
    )
    return es
```

Add the candidate-pool helper, `create_cat_session`, and `get_next_question` after `create_session` (before `_load_session`):

```python
def _cat_candidate_pool(
    session: Session, *, org_id, blueprint: ExamBlueprint
) -> list[dict]:
    """All published, tenant-scoped questions mapped to a domain of this
    blueprint, as engine-consumable candidate dicts. Deduped by question id
    (a question mapped to multiple domains counts once, first mapping wins)."""
    rows = session.execute(
        select(
            Question.id,
            Question.difficulty,
            QuestionMapping.domain_id,
            QuestionMapping.knowledge_point_id,
            Question.source,
        )
        .join(QuestionMapping, QuestionMapping.question_id == Question.id)
        .where(
            Question.organization_id == org_id,
            Question.status == QuestionStatus.published,
            not_deleted(Question),
            QuestionMapping.domain_id.in_(
                select(ExamDomain.id).where(ExamDomain.blueprint_id == blueprint.id)
            ),
        )
        .order_by(Question.id)
    ).all()
    out: list[dict] = []
    seen_ids: set[uuid.UUID] = set()
    for r in rows:
        if r.id in seen_ids:
            continue
        seen_ids.add(r.id)
        out.append({
            "id": str(r.id),
            "difficulty": r.difficulty,
            "domain_id": str(r.domain_id) if r.domain_id else None,
            "knowledge_point_id": str(r.knowledge_point_id) if r.knowledge_point_id else None,
            "source": r.source,
        })
    return out


def create_cat_session(
    session: Session, *, org_id, actor_id, bp: ExamBlueprint
) -> ExamSession:
    domains = list(
        session.execute(
            select(ExamDomain)
            .where(ExamDomain.blueprint_id == bp.id)
            .order_by(ExamDomain.number)
        ).scalars().all()
    )
    if not domains:
        raise ValidationError("current blueprint has no domains configured")
    targets = _allocate(bp.max_items, [d.weight_pct for d in domains])
    domain_targets = {str(d.id): t for d, t in zip(domains, targets)}
    candidates = _cat_candidate_pool(session, org_id=org_id, blueprint=bp)
    if not candidates:
        raise ValidationError("not enough published questions for CAT")
    rng = random.Random()
    first_id = cat_engine.select_first_item(candidates, rng)
    if first_id is None:
        raise ValidationError("not enough published questions for CAT")
    started = datetime.now(timezone.utc)
    deadline = started + timedelta(minutes=bp.duration_minutes)
    config = {
        "kind": "cat",
        "question_ids": [],
        "next_question_id": first_id,
        "position": 0,
        "ability": cat_engine.initial_ability(),
        "se": cat_engine.DEFAULT_PARAMS["base_se"],
        "answered": 0,
        "correct": 0,
        "domain_targets": domain_targets,
        "domain_answered": {},
        "seen": [],
        "last_knowledge_point": None,
        "last_source": None,
        "deadline_at": deadline.isoformat(),
        "max_score": bp.max_score,
        "passing_score": bp.passing_score,
        "duration_minutes": bp.duration_minutes,
        "min_items": bp.min_items,
        "max_items": bp.max_items,
        "cat_params": dict(cat_engine.DEFAULT_PARAMS),
        "disclaimer": cat_engine.DISCLAIMER,
    }
    es = ExamSession(
        user_id=actor_id,
        organization_id=org_id,
        blueprint_id=bp.id,
        session_kind=ExamSessionKind.cat,
        status=ExamSessionStatus.in_progress,
        total_questions=0,
        correct_count=0,
        config=config,
    )
    session.add(es)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=actor_id, organization_id=org_id,
        entity_type="exam_session", entity_id=str(es.id),
        details={"kind": "cat", "max_items": bp.max_items},
    )
    return es


def get_next_question(session: Session, *, session_id, user_id) -> dict:
    es = _load_session(session, session_id, user_id)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    qid_str = es.config.get("next_question_id")
    if not qid_str:
        raise ConflictError("exam session has no next question")
    question = session.get(Question, uuid.UUID(qid_str))
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question.id)
    started = es.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed_ms = int(
        (datetime.now(timezone.utc) - started).total_seconds() * 1000
    )
    return {
        "session_id": str(es.id),
        "position": es.config.get("position", 0),
        "total": es.config.get("max_items", 0),
        "question_id": str(question.id),
        "stem": question.stem,
        "question_type": question.question_type.value,
        "options": [
            {
                "id": str(o.id),
                "order_index": o.order_index,
                "content": o.content,
                "content_format": o.content_format.value,
            }
            for o in options
        ],
        "elapsed_ms": elapsed_ms,
        "time_remaining_ms": _time_remaining_ms(es),
        "previous_answer": None,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_service.py -k "cat or create_cat or get_next" -v`
Expected: the 5 new CAT creation/next tests pass, and existing fixed tests still pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/exam.py backend/tests/test_exam_service.py
git commit -m "feat(cat): service CAT session creation + next-item delivery"
```

---

### Task 5: Service — CAT answer submission (non-revisable, forward-only, adaptive)

**Files:**
- Modify: `backend/app/services/exam.py`
- Modify: `backend/tests/test_exam_service.py`

**Interfaces:**
- Consumes: `cat_engine.update_ability`, `cat_engine.sem`, `cat_engine.passing_ability`, `cat_engine.decide_termination`, `cat_engine.select_next_item` (Tasks 1–2); `create_cat_session`/`_cat_candidate_pool`/`get_next_question` (Task 4); existing `_judge`, `snapshot_question`, `_options_for`, `_time_remaining_ms`, `_auto_submit_if_expired`.
- Produces: `_submit_cat_answer(session, *, es, user_id, payload) -> ExamAnswerAck` (with `finished` set); modifies `submit_answer` to branch on `session_kind`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_exam_service.py`:

```python
def _cat_start(db_session, *, passing_score=700, max_score=1000,
               min_items=1, max_items=5, n_questions=5, difficulty=3,
               early_stop=True):
    org = _org(db_session)
    actor = _actor(db_session, org)
    bp, d1 = _cat_blueprint(
        db_session, min_items=min_items, max_items=max_items,
        passing_score=passing_score, max_score=max_score,
    )
    _seed_cat_questions(db_session, org, actor, d1, n=n_questions, difficulty=difficulty)
    es = svc.create_session(
        db_session, org_id=org.id, actor_id=actor.id, payload={"kind": "cat"}
    )
    if not early_stop:
        es.config["cat_params"]["early_stop_enabled"] = False
        flag_modified_for_test(es)
    return org, actor, es


def flag_modified_for_test(es):
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(es, "config")


def _answer(db_session, es, actor, *, selected, position):
    from datetime import datetime, timezone
    return svc.submit_answer(
        db_session, session_id=es.id, user_id=actor.id,
        payload={"position": position, "selected": selected,
                 "started_at": datetime.now(timezone.utc)},
    )


def test_cat_submit_advances_position_and_ability(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    # option 0 is correct on every seeded question
    ack = _answer(db_session, es, actor, selected=[0], position=0)
    assert ack.saved is True
    assert ack.finished is False
    assert es.config["answered"] == 1
    assert es.config["correct"] == 1
    assert es.config["ability"] > 3.0  # correct -> ability up
    assert es.config["position"] == 1  # advanced
    assert es.config["next_question_id"]  # next item selected


def test_cat_submit_wrong_lowers_ability(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    _answer(db_session, es, actor, selected=[1], position=0)  # wrong
    assert es.config["ability"] < 3.0
    assert es.config["correct"] == 0


def test_cat_submit_records_ability_on_answer(db_session):
    from app.models.exam import ExamAnswer

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    _answer(db_session, es, actor, selected=[0], position=0)
    ans = db_session.query(ExamAnswer).filter_by(session_id=es.id).one()
    assert ans.ability_estimate_after is not None
    assert ans.se_after is not None
    assert ans.ability_estimate_after > 3.0


def test_cat_submit_non_revisable(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    _answer(db_session, es, actor, selected=[0], position=0)  # position -> 1
    # re-submitting position 0 is now a position mismatch -> rejected (forward-only)
    with pytest.raises(svc.ValidationError):
        _answer(db_session, es, actor, selected=[0], position=0)


def test_cat_submit_position_mismatch_rejected(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    with pytest.raises(svc.ValidationError):
        _answer(db_session, es, actor, selected=[0], position=5)


def test_cat_terminate_at_max_items(db_session):
    from app.models.enums import ExamSessionStatus

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=3, n_questions=5)
    ack0 = _answer(db_session, es, actor, selected=[0], position=0)
    assert ack0.finished is False
    ack1 = _answer(db_session, es, actor, selected=[0], position=1)
    assert ack1.finished is False
    ack2 = _answer(db_session, es, actor, selected=[0], position=2)
    assert ack2.finished is True  # reached max_items=3
    assert es.status == ExamSessionStatus.completed
    assert es.total_questions == 3
    assert es.correct_count == 3
    assert es.config["next_question_id"] is None


def test_cat_early_stop_converged_pass(db_session):
    from app.models.enums import ExamSessionStatus

    # passing_score=0 -> pass_ability=1.0; one correct answer -> ability 3.5,
    # CI entirely above 1.0 -> converged pass at min_items=1.
    org, actor, es = _cat_start(
        db_session, passing_score=0, min_items=1, max_items=10, early_stop=True)
    ack = _answer(db_session, es, actor, selected=[0], position=0)
    assert ack.finished is True
    assert es.status == ExamSessionStatus.completed
    assert es.total_questions == 1


def test_cat_early_stop_converged_fail(db_session):
    from app.models.enums import ExamSessionStatus

    # passing_score=1000 -> pass_ability=5.0; one wrong answer -> ability 2.5,
    # CI entirely below 5.0 -> converged fail at min_items=1.
    org, actor, es = _cat_start(
        db_session, passing_score=1000, min_items=1, max_items=10, early_stop=True)
    ack = _answer(db_session, es, actor, selected=[1], position=0)
    assert ack.finished is True
    assert es.status == ExamSessionStatus.completed


def test_cat_time_up_auto_submits(db_session):
    from datetime import datetime, timezone

    from app.models.enums import ExamSessionStatus

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    es.config["deadline_at"] = datetime.now(timezone.utc).isoformat()
    flag_modified_for_test(es)
    db_session.flush()
    with pytest.raises(svc.ConflictError):
        svc.get_next_question(db_session, session_id=es.id, user_id=actor.id)
    assert db_session.get(ExamSession, es.id).status == ExamSessionStatus.auto_submitted
```

(Note: `ExamSession` is already imported at the top of `test_exam_service.py`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_service.py -k "cat_submit or cat_terminate or cat_early or cat_time" -v`
Expected: FAIL — `submit_answer` runs the fixed (revisable) branch, so `finished`/ability/termination do not behave as asserted.

- [ ] **Step 3: Implement the CAT submit branch**

In `backend/app/services/exam.py`, modify `submit_answer` to branch on session kind. Replace the existing `submit_answer` function with:

```python
def submit_answer(session: Session, *, session_id, user_id, payload) -> ExamAnswerAck:
    body = payload if isinstance(payload, ExamAnswerIn) else ExamAnswerIn(**payload)
    es = _load_session(session, session_id, user_id)
    if es.session_kind == ExamSessionKind.cat:
        return _submit_cat_answer(session, es=es, user_id=user_id, payload=body)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    qids = es.config.get("question_ids", [])
    if body.position < 0 or body.position >= len(qids):
        raise ValidationError("position out of range")
    question_id = uuid.UUID(qids[body.position])
    question = session.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question_id)
    snap = snapshot_question(question, options)
    is_correct = _judge(snap, body.selected)
    now = datetime.now(timezone.utc)
    started = body.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    time_spent_ms = max(0, int((now - started).total_seconds() * 1000))
    existing = session.execute(
        select(ExamAnswer).where(
            ExamAnswer.session_id == es.id,
            ExamAnswer.question_id == question_id,
        )
    ).scalars().first()
    if existing is None:
        existing = ExamAnswer(
            session_id=es.id, user_id=user_id, question_id=question_id,
        )
        session.add(existing)
    existing.question_snapshot = snap
    existing.options_snapshot = snap["options"]
    existing.user_answer = {"selected": body.selected}
    existing.is_correct = is_correct
    existing.time_spent_ms = time_spent_ms
    existing.answered_at = now
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=es.organization_id, entity_type="exam_answer",
        entity_id=str(existing.id), details={"is_correct": is_correct},
    )
    return ExamAnswerAck(
        position=body.position, saved=True,
        time_remaining_ms=_time_remaining_ms(es),
    )
```

Add the `_submit_cat_answer` helper after `submit_answer`:

```python
def _submit_cat_answer(
    session: Session, *, es: ExamSession, user_id, payload
) -> ExamAnswerAck:
    body = payload if isinstance(payload, ExamAnswerIn) else ExamAnswerIn(**payload)
    if _auto_submit_if_expired(session, es) or es.status != ExamSessionStatus.in_progress:
        raise ConflictError("exam session is not in progress")
    cfg = es.config
    if body.position != cfg.get("position", 0):
        raise ValidationError("position does not match current CAT position")
    qid_str = cfg.get("next_question_id")
    if not qid_str:
        raise ConflictError("exam session has no next question")
    question_id = uuid.UUID(qid_str)
    question = session.get(Question, question_id)
    if question is None or question.deleted_at is not None:
        raise NotFound("question no longer available")
    options = _options_for(session, question_id)
    snap = snapshot_question(question, options)
    is_correct = _judge(snap, body.selected)
    now = datetime.now(timezone.utc)
    started = body.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    time_spent_ms = max(0, int((now - started).total_seconds() * 1000))

    params = cfg.get("cat_params", dict(cat_engine.DEFAULT_PARAMS))
    prev_answered = cfg.get("answered", 0)
    answered = prev_answered + 1
    new_ability = cat_engine.update_ability(
        cfg.get("ability", cat_engine.initial_ability()),
        question.difficulty, is_correct, prev_answered, params,
    )
    new_se = cat_engine.sem(answered, params)

    # Domain + knowledge point of the answered item (for coverage + anti-cluster).
    mapping = session.execute(
        select(QuestionMapping).where(QuestionMapping.question_id == question_id)
    ).scalars().first()
    domain_id = str(mapping.domain_id) if mapping and mapping.domain_id else None
    kp = str(mapping.knowledge_point_id) if mapping and mapping.knowledge_point_id else None

    ans = ExamAnswer(session_id=es.id, user_id=user_id, question_id=question_id)
    session.add(ans)
    ans.question_snapshot = snap
    ans.options_snapshot = snap["options"]
    ans.user_answer = {"selected": body.selected}
    ans.is_correct = is_correct
    ans.time_spent_ms = time_spent_ms
    ans.ability_estimate_after = new_ability
    ans.se_after = new_se
    ans.answered_at = now

    # Update CAT runtime state in config.
    cfg["question_ids"] = cfg.get("question_ids", []) + [str(question_id)]
    cfg["seen"] = cfg.get("seen", []) + [str(question_id)]
    cfg["answered"] = answered
    cfg["correct"] = cfg.get("correct", 0) + (1 if is_correct else 0)
    cfg["ability"] = new_ability
    cfg["se"] = new_se
    if domain_id:
        cfg["domain_answered"][domain_id] = cfg["domain_answered"].get(domain_id, 0) + 1
    cfg["last_knowledge_point"] = kp
    cfg["last_source"] = question.source

    min_items = cfg.get("min_items", cat_engine.MIN_ITEMS_DEFAULT)
    max_items = cfg.get("max_items", cat_engine.MAX_ITEMS_DEFAULT)
    pa = cat_engine.passing_ability(
        cfg.get("passing_score", 700), cfg.get("max_score", 1000)
    )
    decision = cat_engine.decide_termination(
        answered, new_ability, new_se, min_items, max_items, False, pa, params
    )

    finished = False
    if decision.must_stop:
        finished = True
        es.status = ExamSessionStatus.completed
        es.ended_at = now
        es.total_questions = answered
        es.correct_count = cfg["correct"]
        cfg["next_question_id"] = None
    else:
        bp = session.get(ExamBlueprint, es.blueprint_id)
        candidates = _cat_candidate_pool(session, org_id=es.organization_id, blueprint=bp)
        rng = random.Random()
        next_id = cat_engine.select_next_item(
            candidates, new_ability, cfg.get("domain_targets", {}),
            cfg.get("domain_answered", {}), cfg.get("seen", []),
            kp, question.source, rng,
        )
        if next_id is None:
            # Pool exhausted: terminate.
            finished = True
            es.status = ExamSessionStatus.completed
            es.ended_at = now
            es.total_questions = answered
            es.correct_count = cfg["correct"]
            cfg["next_question_id"] = None
        else:
            cfg["next_question_id"] = next_id
            cfg["position"] = cfg.get("position", 0) + 1

    flag_modified(es, "config")
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=es.organization_id, entity_type="exam_answer",
        entity_id=str(ans.id),
        details={"is_correct": is_correct, "ability": new_ability, "finished": finished},
    )
    return ExamAnswerAck(
        position=body.position, saved=True,
        time_remaining_ms=_time_remaining_ms(es), finished=finished,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_service.py -k "cat" -v`
Expected: all CAT service tests pass; existing fixed-exam tests still pass.

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/exam.py backend/tests/test_exam_service.py
git commit -m "feat(cat): service CAT answer submission (non-revisable, adaptive, terminating)"
```

---

### Task 6: Service — CAT finish/report/review/history

**Files:**
- Modify: `backend/app/services/exam.py`
- Modify: `backend/tests/test_exam_service.py`

**Interfaces:**
- Consumes: `cat_engine.scaled_score`, `cat_engine.confidence_interval`, `cat_engine.readiness_level` (Task 1); `_submit_cat_answer` (Task 5); existing `_build_report`, `finish_session`, `get_report`, `get_review`, `list_history`, `_scaled`.
- Produces: `_domain_and_wrong(session, es, qids, answers) -> tuple[list[DomainPerformance], list[WrongQuestion]]` (extracted from `_build_report`), `_build_cat_report(session, es) -> ExamReportOut`; CAT branches in `finish_session`, `_build_report`, `_scaled`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_exam_service.py`:

```python
def _finish_cat(db_session, *, passing_score=700, max_score=1000, selected=0,
                early_stop=False, max_items=3, n_questions=5):
    org, actor, es = _cat_start(
        db_session, passing_score=passing_score, max_score=max_score,
        early_stop=early_stop, max_items=max_items, n_questions=n_questions,
    )
    pos = 0
    ack = _answer(db_session, es, actor, selected=[selected], position=pos)
    while not ack.finished:
        pos += 1
        ack = _answer(db_session, es, actor, selected=[selected], position=pos)
    return org, actor, es


def test_cat_report_carries_ability_and_disclaimer(db_session):
    org, actor, es = _finish_cat(db_session, early_stop=False, max_items=3)
    report = svc.get_report(db_session, session_id=es.id, user_id=actor.id)
    assert report.ability_estimate is not None
    assert report.sem is not None
    assert report.ability_ci_lower is not None
    assert report.ability_ci_upper is not None
    assert report.readiness_level in {"ready", "almost_ready", "developing", "needs_work"}
    assert report.disclaimer  # FR-CAT-10
    # ability-based scoring: all correct -> ability high -> scaled > 500
    assert report.scaled_score > 500
    assert report.total_questions == 3


def test_cat_report_pass_line_is_ability_based(db_session):
    # passing_score=1000 -> pass_ability=5.0; even all-correct cannot reach 5.0
    # exactly, so a 3-item run stays below -> passed False.
    org, actor, es = _finish_cat(
        db_session, passing_score=1000, max_score=1000,
        early_stop=False, max_items=3, selected=0)
    report = svc.get_report(db_session, session_id=es.id, user_id=actor.id)
    assert report.passed is False


def test_cat_review_is_snapshot_graded(db_session):
    from app.models.question import QuestionOption

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=3, n_questions=5)
    _answer(db_session, es, actor, selected=[0], position=0)
    # mutate the live first question's options
    first_qid = uuid.UUID(es.config["question_ids"][0])
    opt0 = db_session.query(QuestionOption).filter_by(
        question_id=first_qid, order_index=0).one()
    opt1 = db_session.query(QuestionOption).filter_by(
        question_id=first_qid, order_index=1).one()
    opt0.is_correct = False
    opt1.is_correct = True
    db_session.flush()
    # finish by answering remaining
    ack = _answer(db_session, es, actor, selected=[0], position=1)
    if not ack.finished:
        _answer(db_session, es, actor, selected=[0], position=2)
    svc.finish_session(db_session, session_id=es.id, user_id=actor.id)
    review = svc.get_review(db_session, session_id=es.id, user_id=actor.id)
    item0 = review[0]
    # snapshot still says order_index 0 was correct
    assert item0.options[0].is_correct is True
    assert item0.options[1].is_correct is False
    assert item0.your_answer["is_correct"] is True  # judged against snapshot


def test_cat_finish_manual_when_in_progress(db_session):
    from app.models.enums import ExamSessionStatus

    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5, n_questions=5)
    _answer(db_session, es, actor, selected=[0], position=0)
    # manually finish mid-exam
    report = svc.finish_session(db_session, session_id=es.id, user_id=actor.id)
    assert db_session.get(ExamSession, es.id).status == ExamSessionStatus.completed
    assert es.total_questions == 1
    assert report.total_questions == 1


def test_cat_history_ability_based(db_session):
    org, actor, es = _finish_cat(db_session, early_stop=False, max_items=3, selected=0)
    hist = svc.list_history(db_session, user_id=actor.id)
    assert len(hist) == 1
    # all correct -> ability high -> scaled > 500 (ability-based, not raw)
    assert hist[0].scaled_score > 500
    assert hist[0].total_questions == 3


def test_cat_history_excludes_in_progress(db_session):
    org, actor, es = _cat_start(db_session, early_stop=False, max_items=5)
    # leave in progress
    assert svc.list_history(db_session, user_id=actor.id) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_service.py -k "cat_report or cat_review or cat_finish or cat_history" -v`
Expected: FAIL — `_build_report`/`_scaled` use raw-correct scoring and do not populate CAT fields; `finish_session` does not set `total_questions` for CAT.

- [ ] **Step 3: Extract `_domain_and_wrong` and add CAT report/finish/scale branches**

In `backend/app/services/exam.py`, refactor `_build_report` to extract the shared per-domain + wrong-question assembly into a helper, then branch on session kind. Replace the existing `_build_report` function with:

```python
def _domain_and_wrong(session: Session, es: ExamSession, qids, answers):
    """Shared per-domain grouping + wrong-question list (snapshot-sourced)."""
    domain_rows = list(
        session.execute(
            select(ExamDomain).where(ExamDomain.blueprint_id == es.blueprint_id)
        ).scalars().all()
    )
    domain_by_id = {d.id: d for d in domain_rows}
    qid_to_domain: dict[uuid.UUID, uuid.UUID | None] = {}
    if qids:
        mapping_rows = session.execute(
            select(QuestionMapping.question_id, QuestionMapping.domain_id).where(
                QuestionMapping.question_id.in_(qids)
            )
        ).all()
        for qid, did in mapping_rows:
            qid_to_domain.setdefault(qid, did)
    answer_by_qid = {a.question_id: a for a in answers}
    per_domain: dict[uuid.UUID | None, dict] = {}
    for qid in qids:
        did = qid_to_domain.get(qid)
        bucket = per_domain.setdefault(did, {"answered": 0, "correct": 0})
        a = answer_by_qid.get(qid)
        if a is not None:
            bucket["answered"] += 1
            if a.is_correct:
                bucket["correct"] += 1
    domains = [
        DomainPerformance(
            domain_id=did,
            domain_name=domain_by_id[did].name if did in domain_by_id else None,
            weight_pct=domain_by_id[did].weight_pct if did in domain_by_id else None,
            answered=b["answered"],
            correct=b["correct"],
            accuracy=b["correct"] / b["answered"] if b["answered"] else 0.0,
        )
        for did, b in per_domain.items()
    ]
    wrong = []
    for a in answers:
        if a.is_correct:
            continue
        correct_indexes = [
            o["order_index"] for o in (a.options_snapshot or []) if o.get("is_correct")
        ]
        selected = (a.user_answer or {}).get("selected", [])
        stem = (a.question_snapshot or {}).get("stem", "")
        wrong.append(WrongQuestion(
            question_id=a.question_id,
            stem=stem,
            selected_indexes=list(selected),
            correct_indexes=correct_indexes,
        ))
    return domains, wrong


def _build_report(session: Session, es: ExamSession) -> ExamReportOut:
    if es.session_kind == ExamSessionKind.cat:
        return _build_cat_report(session, es)
    cfg = es.config or {}
    max_score = cfg.get("max_score", 1000)
    passing_score = cfg.get("passing_score", 700)
    qids = [uuid.UUID(q) for q in cfg.get("question_ids", [])]
    total = len(qids) or es.total_questions

    answers = list(
        session.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    )
    answered = len(answers)
    correct = sum(1 for a in answers if a.is_correct)

    scaled_score = round(correct / total * max_score) if total else 0
    passed = scaled_score >= passing_score
    accuracy = correct / answered if answered else 0.0
    total_time = sum(a.time_spent_ms or 0 for a in answers)
    avg_time = total_time / answered if answered else 0.0

    domains, wrong = _domain_and_wrong(session, es, qids, answers)

    return ExamReportOut(
        session_id=es.id,
        status=es.status.value if hasattr(es.status, "value") else es.status,
        total_questions=total,
        answered_count=answered,
        correct_count=correct,
        scaled_score=scaled_score,
        max_score=max_score,
        passing_score=passing_score,
        passed=passed,
        accuracy=accuracy,
        total_time_ms=total_time,
        avg_time_ms=avg_time,
        domains=domains,
        wrong_questions=wrong,
    )


def _build_cat_report(session: Session, es: ExamSession) -> ExamReportOut:
    cfg = es.config or {}
    max_score = cfg.get("max_score", 1000)
    passing_score = cfg.get("passing_score", 700)
    ability = cfg.get("ability", cat_engine.initial_ability())
    se_value = cfg.get("se", cat_engine.DEFAULT_PARAMS["base_se"])
    qids = [uuid.UUID(q) for q in cfg.get("question_ids", [])]
    total = len(qids) or es.total_questions

    answers = list(
        session.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    )
    answered = len(answers)
    correct = sum(1 for a in answers if a.is_correct)

    scaled_score = cat_engine.scaled_score(ability, max_score)
    passed = scaled_score >= passing_score
    accuracy = correct / answered if answered else 0.0
    total_time = sum(a.time_spent_ms or 0 for a in answers)
    avg_time = total_time / answered if answered else 0.0

    domains, wrong = _domain_and_wrong(session, es, qids, answers)
    ci_lo, ci_hi = cat_engine.confidence_interval(ability, se_value)

    return ExamReportOut(
        session_id=es.id,
        status=es.status.value if hasattr(es.status, "value") else es.status,
        total_questions=total,
        answered_count=answered,
        correct_count=correct,
        scaled_score=scaled_score,
        max_score=max_score,
        passing_score=passing_score,
        passed=passed,
        accuracy=accuracy,
        total_time_ms=total_time,
        avg_time_ms=avg_time,
        domains=domains,
        wrong_questions=wrong,
        ability_estimate=ability,
        ability_ci_lower=ci_lo,
        ability_ci_upper=ci_hi,
        sem=se_value,
        readiness_level=cat_engine.readiness_level(ability),
        disclaimer=cfg.get("disclaimer"),
    )
```

Add a CAT branch to `finish_session`. Replace the existing `finish_session` function with:

```python
def finish_session(session: Session, *, session_id, user_id) -> ExamReportOut:
    es = _load_session(session, session_id, user_id)
    _auto_submit_if_expired(session, es)
    if es.status == ExamSessionStatus.in_progress:
        es.status = ExamSessionStatus.completed
        es.ended_at = datetime.now(timezone.utc)
        if es.session_kind == ExamSessionKind.cat:
            cfg = es.config
            es.total_questions = cfg.get("answered", 0)
            cfg["next_question_id"] = None
            flag_modified(es, "config")
        session.flush()
    # Recompute correct_count from stored answers.
    answers = list(
        session.execute(
            select(ExamAnswer).where(ExamAnswer.session_id == es.id)
        ).scalars().all()
    )
    es.correct_count = sum(1 for a in answers if a.is_correct)
    session.flush()
    log_audit(
        session, action=AuditAction.edit, actor_id=user_id,
        organization_id=es.organization_id, entity_type="exam_session",
        entity_id=str(es.id),
        details={"status": es.status.value, "correct_count": es.correct_count},
    )
    return _build_report(session, es)
```

Add a CAT branch to `_scaled`. Replace the existing `_scaled` function with:

```python
def _scaled(es: ExamSession) -> tuple[int, bool, float]:
    max_score = es.config.get("max_score", 0)
    passing_score = es.config.get("passing_score", 0)
    total = es.total_questions or 0
    if es.session_kind == ExamSessionKind.cat:
        ability = es.config.get("ability", cat_engine.initial_ability())
        scaled = cat_engine.scaled_score(ability, max_score)
        accuracy = (es.correct_count / total) if total else 0.0
        return scaled, scaled >= passing_score, accuracy
    scaled = round((es.correct_count / total) * max_score) if total else 0
    passed = scaled >= passing_score
    accuracy = (es.correct_count / total) if total else 0.0
    return scaled, passed, accuracy
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_service.py -v`
Expected: all exam service tests pass (fixed + CAT).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/services/exam.py backend/tests/test_exam_service.py
git commit -m "feat(cat): service CAT report/finish/history (ability-based scoring)"
```

---

### Task 7: API — `GET /sessions/{id}/next` route + config stripping

**Files:**
- Modify: `backend/app/api/exam.py`
- Modify: `backend/tests/test_exam_api.py`

**Interfaces:**
- Consumes: `svc.get_next_question` (Task 4), `svc.create_session` (branches on kind, Task 4).
- Produces: `GET /api/exam/sessions/{session_id}/next` route; extended `_session_out` that strips CAT-internal config keys.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_exam_api.py`:

```python
def _seed_cat_pool(db, *, n=5, difficulty=3, min_items=1, max_items=5):
    from app.models.enums import QuestionStatus, QuestionType, TextFormat
    from app.models.question import Question, QuestionMapping, QuestionOption
    from app.models.taxonomy import ExamBlueprint, ExamDomain
    from app.models.auth import Organization, User

    org = db.query(Organization).first()
    actor = db.query(User).first()
    bp = ExamBlueprint(
        version_label="cat-v1", effective_date="2026-04-15",
        min_items=min_items, max_items=max_items, duration_minutes=30,
        passing_score=700, max_score=1000, is_current=True,
    )
    db.add(bp); db.flush()
    dom = ExamDomain(blueprint_id=bp.id, number=1, name="D1", weight_pct=100)
    db.add(dom); db.flush()
    qs = []
    for i in range(n):
        q = Question(
            organization_id=org.id, question_type=QuestionType.single_choice,
            stem=f"cat-q{i}", stem_format=TextFormat.markdown,
            status=QuestionStatus.published, created_by_id=actor.id,
            difficulty=difficulty,
        )
        db.add(q); db.flush()
        db.add(QuestionOption(question_id=q.id, order_index=0, content="A",
                              content_format=TextFormat.markdown, is_correct=True))
        db.add(QuestionOption(question_id=q.id, order_index=1, content="B",
                              content_format=TextFormat.markdown, is_correct=False))
        db.add(QuestionMapping(question_id=q.id, domain_id=dom.id))
        qs.append(q)
    db.flush()
    return bp, qs


def test_cat_happy_path(client):
    c, store, db = client
    h = _headers(db, store, email="cat-hp@example.com")
    _seed_cat_pool(db, n=5, difficulty=3, min_items=1, max_items=3)
    # create cat session
    s = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h)
    assert s.status_code == 200, s.text
    assert s.json()["session_kind"] == "cat"
    sid = s.json()["id"]
    # config must not leak internal CAT keys
    for key in ("question_ids", "next_question_id", "seen",
                "domain_targets", "domain_answered", "cat_params"):
        assert key not in s.json()["config"]
    assert "disclaimer" in s.json()["config"]

    # deliver next item
    d = c.get(f"/api/exam/sessions/{sid}/next", headers=h)
    assert d.status_code == 200, d.text
    assert d.json()["position"] == 0
    assert d.json()["total"] == 3
    assert "is_correct" not in d.json()["options"][0]

    # answer all (max_items=3) -> auto-finish
    pos = 0
    ack = c.post(f"/api/exam/sessions/{sid}/answers",
                 json={"position": pos, "selected": [0],
                       "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
                 headers=h)
    assert ack.status_code == 200, ack.text
    while not ack.json().get("finished"):
        pos += 1
        ack = c.post(f"/api/exam/sessions/{sid}/answers",
                     json={"position": pos, "selected": [0],
                           "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
                     headers=h)
        assert ack.status_code == 200, ack.text
    # report
    rep = c.get(f"/api/exam/sessions/{sid}/report", headers=h)
    assert rep.status_code == 200, rep.text
    assert rep.json()["ability_estimate"] is not None
    assert rep.json()["readiness_level"] in {"ready", "almost_ready", "developing", "needs_work"}
    assert rep.json()["disclaimer"]
    # review
    rev = c.get(f"/api/exam/sessions/{sid}/review", headers=h)
    assert rev.status_code == 200, rev.text
    assert len(rev.json()) == pos + 1
    # history
    hist = c.get("/api/exam/history", headers=h)
    assert hist.status_code == 200
    assert len(hist.json()) == 1
    assert hist.json()[0]["scaled_score"] > 500


def test_cat_next_on_fixed_session_409(client):
    c, store, db = client
    h = _headers(db, store, email="cat-fixed@example.com")
    _seed_blueprint_and_question(db, min_items=1, max_items=1)
    sid = c.post("/api/exam/sessions", json={}, headers=h).json()["id"]
    r = c.get(f"/api/exam/sessions/{sid}/next", headers=h)
    assert r.status_code == 409


def test_cat_submit_wrong_position_422(client):
    c, store, db = client
    h = _headers(db, store, email="cat-pos@example.com")
    _seed_cat_pool(db, n=5, difficulty=3, min_items=1, max_items=5)
    sid = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h).json()["id"]
    r = c.post(f"/api/exam/sessions/{sid}/answers",
               json={"position": 5, "selected": [0],
                     "started_at": dt.datetime.now(dt.timezone.utc).isoformat()},
               headers=h)
    assert r.status_code == 422


def test_cat_other_user_404(client):
    c, store, db = client
    h1 = _headers(db, store, email="cat-owner@example.com")
    h2 = _headers(db, store, email="cat-intruder@example.com")
    _seed_cat_pool(db, n=5, difficulty=3, min_items=1, max_items=3)
    sid = c.post("/api/exam/sessions", json={"kind": "cat"}, headers=h1).json()["id"]
    assert c.get(f"/api/exam/sessions/{sid}/next", headers=h2).status_code == 404


def test_cat_401_without_token(client):
    c, store, db = client
    _seed_cat_pool(db, n=5, difficulty=3, min_items=1, max_items=3)
    assert c.post("/api/exam/sessions", json={"kind": "cat"}).status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_api.py -k "cat" -v`
Expected: FAIL — `GET /next` returns 404 (route missing); config leaks internal keys.

- [ ] **Step 3: Add the `/next` route and extend `_session_out`**

In `backend/app/api/exam.py`, replace the `_session_out` function with one that strips the full set of CAT-internal keys:

```python
_INTERNAL_CONFIG_KEYS = {
    "question_ids", "next_question_id", "seen",
    "domain_targets", "domain_answered", "cat_params",
}


def _session_out(es) -> ExamSessionOut:
    remaining = None
    if es.status.value == "in_progress":
        try:
            from datetime import datetime, timezone
            dl = datetime.fromisoformat(es.config.get("deadline_at"))
            if dl.tzinfo is None:
                dl = dl.replace(tzinfo=timezone.utc)
            remaining = max(0, int((dl - datetime.now(timezone.utc)).total_seconds() * 1000))
        except Exception:
            remaining = None
    safe_config = {
        k: v for k, v in (es.config or {}).items()
        if k not in _INTERNAL_CONFIG_KEYS
    }
    return ExamSessionOut(
        id=es.id, status=es.status.value, session_kind=es.session_kind.value,
        total_questions=es.total_questions, correct_count=es.correct_count,
        started_at=es.started_at, ended_at=es.ended_at,
        time_remaining_ms=remaining, config=safe_config,
    )
```

Add the new route after `get_exam_question` (the `/sessions/{session_id}/questions/{position}` route):

```python
@router.get("/sessions/{session_id}/next", response_model=QuestionDeliveryOut)
def get_exam_next(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(require_permission("exam:read")),
):
    """CAT-only: deliver the adaptively-selected current item."""
    try:
        return svc.get_next_question(
            session, session_id=session_id, user_id=current.user.id
        )
    except svc.NotFound:
        raise HTTPException(status_code=404, detail="session or question not found")
    except svc.ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except svc.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_exam_api.py -v`
Expected: all exam API tests pass (fixed + CAT).

- [ ] **Step 5: Commit**

```bash
cd /home/john/cissp_exam
git add backend/app/api/exam.py backend/tests/test_exam_api.py
git commit -m "feat(cat): HTTP /next route + config key stripping"
```

---

### Task 8: Full suite, docs, finish branch

**Files:**
- Modify: `CLAUDE.md`
- Modify: `/home/john/.claude/projects/-home-john-cissp-exam/memory/cissp-project-roadmap.md` (memory)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest -q`
Expected: all tests pass (221 prior + ~24 engine + ~20 CAT service + ~5 CAT API ≈ 270). No failures.

- [ ] **Step 2: Verify zero migration drift**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && pytest tests/test_migrations.py -q`
Expected: pass — no model columns were added, so autogenerate drift is zero. (If a drift failure appears, do NOT add a migration — investigate which model changed; this sub-project adds none.)

- [ ] **Step 3: Apply migrations to dev DB (no-op expected) and smoke the app**

Run: `cd /home/john/cissp_exam/backend && source venv/bin/activate && alembic upgrade head`
Expected: "No new migration to apply" (head is unchanged at `d8e1f2a3b4cd`).

- [ ] **Step 4: Update CLAUDE.md**

In `/home/john/cissp_exam/CLAUDE.md`, find the sentence in the "Current State" paragraph that lists what does NOT exist yet:

```
What does NOT exist yet: practice/exam APIs, CAT engine, analytics & admin UI, interactive import, taxonomy write/admin — these are later sub-projects (D–H).
```

Hmm — that text may already have been updated for sub-project F. Locate the current "What does NOT exist yet" line and ensure it reads:

```
What does NOT exist yet: analytics & admin UI, interactive import (H) — these are later sub-projects.
```

And ensure the existing "implemented" list mentions the CAT exam. After the fixed-exam clause, append a CAT clause describing: `/api/exam/sessions` with `kind=cat` (rule-driven simplified ability estimation per PRD §11.1, NOT 3PL IRT), `GET /sessions/{id}/next` adaptive delivery, non-revisable/forward-only/no-skip answers, termination at max_items/3h/early-convergence, ability-based scoring + readiness + disclaimer in the report; pure `app/services/cat_engine.py`; reuses ExamSession(session_kind=cat)/ExamAnswer(ability_estimate_after,se_after); no migration.

Also bump the passing-test count in the same paragraph (e.g. "221 passing" → the new total from Step 1) and add "+ CAT engine tests" to the test list.

- [ ] **Step 5: Commit docs**

```bash
cd /home/john/cissp_exam
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for sub-project G (CAT exam API)"
```

- [ ] **Step 6: Update roadmap memory**

Update `/home/john/.claude/projects/-home-john-cissp-exam/memory/cissp-project-roadmap.md`: change the `G — CAT exam (FR-CAT), H — Analytics & admin backoffice (FR-ANA/ADMIN): later.` line to record G as DONE (merged) with a one-paragraph summary mirroring the CLAUDE.md clause (FR-CAT-01..10 coverage, pure `cat_engine.py`, ability-based scoring, non-revisable/forward-only, no migration, test count, gotcha: CAT answers are non-revisable unlike fixed-exam revisable answers; do NOT name handler `get_session`), and leave H as the remaining sub-project.

- [ ] **Step 7: Finish the development branch**

Announce: "I'm using the finishing-a-development-branch skill to complete this work." Then verify the full test suite passes once more on the branch, and merge `feat/cat-exam-api` back to `master` locally (Option 1), running the full suite on the merged result before deleting the branch. (Autonomous mode: choose Option 1 — merge locally.)

```bash
cd /home/john/cissp_exam
git checkout master
git merge --no-ff feat/cat-exam-api -m "Merge feat/cat-exam-api: sub-project G (CAT exam API)"
cd backend && source venv/bin/activate && pytest -q
cd .. && git branch -d feat/cat-exam-api
```

---

## Self-Review

**Spec coverage:**
- §4 `cat_engine.py` constants + math → Task 1. ✓
- §4 `select_first_item` / `select_next_item` → Task 2. ✓
- §5 `create_cat_session` (medium start, config shape, targets, first item) → Task 4. ✓
- §5 `get_next_question` (strips correctness, previous_answer=None, timing) → Task 4. ✓
- §5 `_submit_cat_answer` (non-revisable position check, ability/se update, snapshot, termination, next selection, `finished` ack) → Task 5. ✓
- §5 `finish_session` CAT branch → Task 6. ✓
- §5 `_build_report` CAT branch + `_build_cat_report` (ability score, CI, readiness, disclaimer) → Task 6. ✓
- §5 `_scaled` CAT branch (history ability-based) → Task 6. ✓
- §5 `get_review` unchanged (snapshot-graded, works for both) → covered by Task 6 test `test_cat_review_is_snapshot_graded`. ✓
- §6 config shape → Task 4. ✓
- §7 schemas (`kind`, `finished`, report CAT fields) → Task 3. ✓
- §8 API `/next` route + `_session_out` stripping → Task 7. ✓
- §9 error handling (empty pool 422, position mismatch 422, time-up auto-submit, non-owner 404) → Tasks 4–7 tests. ✓
- §10 testing (engine pure, service CAT, API CAT) → Tasks 1, 2, 4, 5, 6, 7. ✓
- FR-CAT-01 (3h/100–150) → blueprint duration + min/max_items (Task 4). ✓
- FR-CAT-02 (no revise) → position check, no upsert (Task 5). ✓
- FR-CAT-03 (no skip) → `/next` delivers only current; submit requires current position (Tasks 4–5). ✓
- FR-CAT-04 (medium start) → `select_first_item` (Task 2/4). ✓
- FR-CAT-05 (adaptive + domain + difficulty) → `select_next_item` + `update_ability` (Tasks 2/5). ✓
- FR-CAT-06 (early stop ≥100 if converged) → `decide_termination` converged (Tasks 1/5). ✓
- FR-CAT-07 (end at 150/3h) → `decide_termination` max_items/time_up + lazy auto-submit (Tasks 1/5). ✓
- FR-CAT-08 (no real-time pass prob) → ack returns no correctness/pass-prob (Task 5). ✓
- FR-CAT-09 (report ability/CI/domain/suggestions) → `_build_cat_report` + readiness (Task 6). ✓
- FR-CAT-10 (disclaimer) → `DISCLAIMER` in config + report (Tasks 1/4/6). ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". All code blocks complete. ✓

**Type consistency:** `TerminationDecision.must_stop`/`.reason` used consistently. `select_next_item`/`select_first_item` candidate dict keys (`id`, `difficulty`, `domain_id`, `knowledge_point_id`, `source`) match between engine (Task 2), the pool builder `_cat_candidate_pool` (Task 4), and tests. `ExamAnswerAck.finished` added in Task 3, set in Task 5, asserted in Tasks 5/7. `ExamReportOut` CAT field names (`ability_estimate`, `ability_ci_lower`, `ability_ci_upper`, `sem`, `readiness_level`, `disclaimer`) match between Task 3 (schema), Task 6 (`_build_cat_report`), and Task 7 (API assertions). `flag_modified(es, "config")` imported in Task 4 and used in Tasks 5/6. ✓

Plan complete.
