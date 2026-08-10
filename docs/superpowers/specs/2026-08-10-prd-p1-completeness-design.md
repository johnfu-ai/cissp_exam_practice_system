# PRD P1 Completeness + E2E Design

Date: 2026-08-10  
Status: Approved (autonomous execution per product owner directive)  
Related: PRD v1.3 §6 / §12.2 / §14; gap-closure `2026-08-10-prd-apps-gap-closure-design.md`

## 1. Context & audit summary

Backend APIs cover nearly all MVP FR-\*. The 2026-08-10 dual-client gap-closure work closes remaining §14 client holes (book/chapter practice, explanations, analytics sections, CAT no-advance proof, admin template/mapping/coverage/members) and lives in the working tree pending commit.

Remaining product gaps after gap-closure are **P1 learner affordances**, **admin taxonomy wiring**, **upload hardening**, and **automated E2E** — not greenfield backends.

## 2. Approaches considered

| Approach | Scope | Trade-off |
|---|---|---|
| A. Ship gap-closure only | Commit WT + README | Leaves FR-ANS-05/08, PRAC-04/06, ETL-15 UI, E2E open |
| **B. P1 completeness wave (recommended)** | Gap-closure + learner P1 UX + admin mapping UIs + `weak_first` + upload size + API E2E + docs/publish | Feasible in one Superpowers cycle; uses existing APIs |
| C. Full P1+P2 product | Also USER-06 profile, IMP-02 markdown paste, IMP-09/ANA-07 exports, IMP-06 similarity, Q-08 per-item stats | Too large; mixes unrelated subsystems |

**Decision: Approach B.** Explicitly out of this wave (remain Phase 5 / later): 3PL IRT, complex item UX, org billing, offline sync, Flutter Web/macOS/Linux, PDF/DOCX parse, dark mode, AI generation.

## 3. Goals

1. Land gap-closure (commit + verify).
2. Close high-value P1 FRs that already have API support or tiny backend deltas.
3. Add automated E2E coverage for §14 critical paths.
4. Update README/artifacts; review/fix; publish to GitHub.

## 4. Feature contracts

### 4.1 Learner — answer metadata (FR-ANS-05, FR-ANS-06, FR-ANS-08)

| ID | Target |
|---|---|
| FR-ANS-05 | After practice submit, render `AnswerResultOut.mapping` (domain / chapter / knowledge point names when present) and `history` (prior attempts: correctness + relative time). |
| FR-ANS-06 | Add `is_questioned` chip alongside bookmark / flag / mastered; persist via existing `PUT /api/practice/questions/{id}/state`. |
| FR-ANS-08 | After submit (and optionally on review), call `GET /api/practice/questions/{id}/related` and list up to N related stems (bilingual via existing models). Tapping related is informational in v1 (no auto-start new session). |

No new backend routes. Taxonomy display names stay untranslated (FR-I18N-05).

### 4.2 Learner — practice filters & order (FR-PRAC-04, FR-PRAC-06)

| ID | Target |
|---|---|
| FR-PRAC-04 | Flutter create form exposes optional `difficulty` (1–5), `question_type` (single_choice / multiple_choice / true_false), `tag_id` (from `GET /api/tags`). Add backend `knowledge_point_id` on `SessionCreateIn` + candidate filter (parity with question list). |
| FR-PRAC-06 | New order mode `weak_first`: prefer questions the user previously missed / low mastery, then fill with unpracticed, then remainder. Extend `OrderMode` Literal + `_order_ids` in `app/services/practice.py`. Flutter order dropdown includes the new mode. |

### 4.3 Admin — taxonomy wiring (FR-ETL-15, FR-TAX-04/05)

| ID | Target |
|---|---|
| FR-ETL-15 | Taxonomy or Import-adjacent panel: list/create/update/delete `ChapterDomainMapping` via `/api/etl/mappings`. |
| FR-TAX-04/05 | Knowledge-points admin: bind/unbind domains via `/api/admin/knowledge-points/{id}/domains`. |

Reuse existing typed API client; gate by `admin:manage_taxonomy`.

### 4.4 Upload hardening (NFR-SEC-08 partial)

Enforce max upload size (default **5 MiB**) and keep extension allowlist on interactive import. Reject oversized bodies with 413. Malware scanning remains out of scope (no AV infra).

### 4.5 E2E suite

Add `backend/tests/test_e2e_acceptance.py` (real Postgres, same conftest) covering one happy path each:

1. Admin login → import/ETL preview smoke (or seeded bank) → publish gate if needed  
2. Learner practice create with domain+book/chapter filters → answer → assert mapping/history present → state bookmark/questioned  
3. Fixed exam create → answer → finish → report  
4. CAT create → `/next` → answer → language-mode fields present without requiring client advance  
5. Analytics dashboard/domains return 200  

Plus `scripts/e2e_smoke.sh` for Docker stack health + auth + practice create (shell-level CI optional).

### 4.6 Docs & publish

- Update root `README.md`: gap-closure + P1 completeness links, E2E commands, prod compose / backup pointers, drift script.  
- Keep PRD status as Draft until product owner marks Released.  
- Commit on `master`, push `origin`, tag optional `v1.3.1-p1` only if tests green.

## 5. Architecture notes

- Prefer **client-only** work when APIs exist; backend changes limited to `weak_first`, `knowledge_point_id` filter, upload size.  
- TDD: failing tests first for `weak_first`, upload 413, Flutter widget/unit where practical, frontend Vitest for mapping UI helpers / admin tabs.  
- CAT language toggle remains pure client state (never `/next`) — do not regress gap-closure tests.  
- Service-layer rules unchanged: routes stay thin.

## 6. Testing strategy

| Layer | Additions |
|---|---|
| Backend unit/API | `weak_first` ordering; `knowledge_point_id` filter; upload size 413 |
| Backend E2E | `test_e2e_acceptance.py` §14 paths |
| Flutter | Widget/unit for questioned chip / mapping panel if extractable; keep CAT/auth suites |
| Frontend | Vitest for ETL mappings panel + KP domain bind actions |
| Manual/Docker | `scripts/e2e_smoke.sh` |

## 7. Acceptance

- Gap-closure plan Tasks 1–6 remain green.  
- FR-ANS-05/06/08 visible in Flutter practice runner.  
- FR-PRAC-04 filters + FR-PRAC-06 `weak_first` work end-to-end.  
- Admin can maintain chapter→domain mappings and KP↔domain bindings.  
- Oversized upload → 413.  
- E2E suite passes in CI-capable local pytest.  
- README documents dual-client + E2E; changes pushed to GitHub.

## 8. Out of scope

FR-USER-06, FR-IMP-02/09/10, FR-IMP-06 similarity engine, FR-ANA-07/08 file exports, FR-Q-05 interaction, NFR-SEC-08 AV scan, NFR-PERF load suite, full WCAG audit automation, store signing.
