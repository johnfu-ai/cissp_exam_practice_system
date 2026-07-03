# P0 #3 — Cross-Tenant IDOR on Question + ETL Routes Design Spec

Date: 2026-07-03
Status: Approved (self-approved under autonomous goal directive)
Parent audit: `docs/audits/2026-07-03-improvement-proposals.md` (P0 #3, audit H-1 + H-5)
Parent PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §7.2 (NFR-SEC-04, NFR-COMP-05 tenant isolation)

## 1. Goal & scope

Close two cross-tenant IDOR families:

1. **Question `{question_id}` routes** — `svc.get_question()` fetches by PK with
   no `organization_id` filter, so a user with `question:read`/`question:write`
   in org A can read/edit/delete/publish/view-revisions/post-feedback on any
   org's question by UUID. (`list_questions` is already org-scoped, which masks
   the gap.)
2. **ETL `{run_id}` routes** — `get_run`/`commit_run`/`rollback_run` fetch
   `EtlRun` by PK with no org check; `run_rollback` takes no `org_id` at all.

**Fix:** make `get_question` the single ownership gate (require `org_id`,
raise `NotFound` on mismatch — never reveal existence), thread `org_id` through
every `{question_id}` service function + route, and add org checks to the ETL
run routes/runner. Cross-org → 404.

**Out of scope:** the practice/exam session IDOR (sessions are already
user-scoped via `_load_session` user_id check — verified); broader
per-permission audit (separate).

## 2. Question service changes (`app/services/question.py`)

- `get_question(session, question_id, *, org_id)`: require `org_id`;
  `if q is None or q.deleted_at is not None or q.organization_id != org_id:
  raise NotFound`.
- `update_question(*, question_id, actor_id, payload, org_id)`,
  `delete_question(*, question_id, actor_id, org_id)`,
  `submit_review(*, question_id, actor_id, action, comment, org_id)`,
  `create_feedback(*, org_id, question_id, ...)` (already has `org_id`) —
  pass `org_id` into their `get_question` call.
- `list_revisions` / `list_feedback`: the API route calls `get_question(org_id)`
  first (ownership gate) before listing — no signature change needed, but the
  routes must call `get_question` with `org_id`.

## 3. Question API changes (`app/api/questions.py`)

Every `{question_id}` route captures `current` (not `_`) and threads
`current.org_id`:
- `GET /{id}` → `svc.get_question(session, question_id, org_id=current.org_id)`.
- `PUT /{id}` → `svc.update_question(..., org_id=current.org_id)`.
- `DELETE /{id}` → `svc.delete_question(..., org_id=current.org_id)`.
- `POST /{id}/review` → `svc.submit_review(..., org_id=current.org_id)`.
- `GET /{id}/revisions` → `svc.get_question(..., org_id=current.org_id)` gate,
  then list.
- `POST /{id}/feedback` → already passes `org_id` (service gates via
  `get_question`).
- `GET /{id}/feedback` → add `svc.get_question(..., org_id=current.org_id)`
  gate before listing (currently has NO ownership check).

## 4. ETL changes (`app/etl/runner.py` + `app/api/etl.py`)

- `run_commit(session, org_id, run_id)`: split the missing/cross-org check from
  the phase check — `if run is None or run.organization_id != org_id: raise
  LookupError("run not found")`; phase violation stays `ValueError`.
- `run_rollback(session, run_id, *, org_id)`: add `org_id`; same
  missing/cross-org → `LookupError`.
- API: `get_run` captures `current`, 404 if `run.organization_id !=
  current.org_id`. `commit_run`/`rollback_run` catch `LookupError` → 404
  (alongside `ValueError` → 409). `rollback_run` passes `org_id=current.org_id`.

## 5. Testing

- `tests/test_question_api.py` (append): for each of GET/PUT/DELETE/review/
  revisions/feedback, a user in org A targeting org B's question → 404. Also
  assert same-org still 200.
- `tests/test_etl` or `tests/etl/test_api_etl.py` (append): cross-org
  `get_run`/`commit_run`/`rollback_run` → 404; same-org → 200/409-as-before.

## 6. Migration

None.

## 7. Acceptance criteria

1. A user cannot read/edit/delete/review/view-revisions/post-or-list-feedback
   on another org's question — all return 404.
2. A user cannot get/commit/rollback another org's ETL run — 404.
3. Same-org operations behave exactly as before (no regression).
4. Full suite green.
