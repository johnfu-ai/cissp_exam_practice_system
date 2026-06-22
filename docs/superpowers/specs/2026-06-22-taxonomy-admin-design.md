# Sub-project D: Taxonomy Admin — Design Spec

**Date:** 2026-06-22
**Status:** Approved (autonomous /goal build-out; PRD is source of truth)
**Depends on:** Sub-project A (models), C (taxonomy read API + service layer patterns)

## Goal

Build the *write/admin* side of the taxonomy subsystem: let a `system_admin` (via the `admin:manage_taxonomy` permission) maintain exam blueprints, domain weights/effective dates, books, chapters, the knowledge-point tree, knowledge-point↔domain bindings, and tags. The read side (sub-project C) already exists; this adds create/update/delete + a set-current operation, all audit-logged.

Covers PRD **FR-TAX-02** (exam version/domain weights/effective dates), **FR-TAX-03** (books/chapters), **FR-TAX-04** (knowledge-point tree, bind to ≥1 domain), **FR-TAX-05** (cross-mappings), **FR-TAX-06** (tags), and **FR-ADMIN-02** (classification management). FR-TAX-01 (built-in 8 domains + blueprint) is already satisfied by the seed.

## Architecture

- **Service layer:** a new `app/services/taxonomy_admin.py` owns all write logic + validation + audit logging. Routes in `app/api/taxonomy.py` (extended) delegate to it. Reuses the read service (`app/services/taxonomy.py`) for fetches.
- **Tenant scoping:** ExamBlueprint, ExamDomain, KnowledgePoint, KnowledgePointDomain, Tag are GLOBAL (shared across orgs) — admin ops on them are not org-scoped. Book and Chapter are tenant-scoped (`organization_id` from `current.org_id`).
- **Permissions:** every admin route uses `require_permission("admin:manage_taxonomy")` (granted only to `system_admin`). Reads remain gated by `question:read` (unchanged from sub-project C).
- **Audit:** every create/update/delete/set-current calls `log_audit` with `AuditAction.config_change` for global taxonomy (blueprint/domain/kp/binding/tag) and `AuditAction.edit`/`delete` for tenant-scoped book/chapter (NFR-DATA-05).
- **No migration:** all tables already exist from sub-project A. No schema changes. (If a field is missing, stop and add a migration — but none are needed.)

## Data model (already implemented — no changes)

`ExamBlueprint` (version_label unique, effective_date, min/max_items, duration_minutes, passing_score, max_score, is_current) · `ExamDomain` (unique blueprint_id+number, name, weight_pct) · `KnowledgePoint` (self-ref parent_id, name, description) · `KnowledgePointDomain` (unique kp+domain) · `Tag` (unique name) · `Book`/`Chapter` (tenant-scoped; Chapter unique-ish by book_id+order_index).

## API surface

All admin routes prefixed `/api/admin/...` except book/chapter/kp/tag writes which extend the existing `/api/books`, `/api/knowledge-points`, `/api/tags` paths (writes are admin-gated, reads stay `question:read`).

**ExamBlueprint (GLOBAL):**
- `POST /api/admin/blueprints` — create
- `GET /api/admin/blueprints` — list (all versions)
- `GET /api/admin/blueprints/{id}` — detail incl. domains
- `PUT /api/admin/blueprints/{id}` — update fields (not is_current)
- `POST /api/admin/blueprints/{id}/set-current` — flip this to current, all others false (atomic)
- `DELETE /api/admin/blueprints/{id}` — delete (refuse if is_current or has published questions referencing its domains)

**ExamDomain (GLOBAL, nested under blueprint):**
- `POST /api/admin/blueprints/{id}/domains`
- `GET /api/admin/blueprints/{id}/domains`
- `PUT /api/admin/blueprints/{id}/domains/{domain_id}`
- `DELETE /api/admin/blueprints/{id}/domains/{domain_id}` — refuse if questions map to it

**Book (tenant-scoped):**
- `POST /api/books` (admin) — extend existing read router
- `GET /api/books/{id}`, `PUT /api/books/{id}`, `DELETE /api/books/{id}`

**Chapter (tenant-scoped, nested under book):**
- `POST /api/books/{book_id}/chapters` (admin)
- `PUT /api/books/{book_id}/chapters/{chapter_id}`, `DELETE /api/books/{book_id}/chapters/{chapter_id}`
- `GET /api/books/{book_id}/chapters` (existing, `question:read`)

**KnowledgePoint (GLOBAL, tree):**
- `POST /api/knowledge-points` (admin) — optional parent_id
- `GET /api/knowledge-points?parent_id=<uuid|root>` — list; `parent_id=root` (or omitted) returns roots
- `GET /api/knowledge-points/{id}`, `PUT /api/knowledge-points/{id}`, `DELETE /api/knowledge-points/{id}` — delete refuses if children or bindings or mapped questions exist

**KnowledgePoint↔Domain binding (GLOBAL):**
- `POST /api/admin/knowledge-points/{id}/domains` — body `{domain_id}`
- `GET /api/admin/knowledge-points/{id}/domains` — list bound domains
- `DELETE /api/admin/knowledge-points/{id}/domains/{domain_id}`

**Tag (GLOBAL):**
- `POST /api/tags` (admin), `GET /api/tags`
- `PUT /api/tags/{id}`, `DELETE /api/tags/{id}` — delete refuses if questions map to it (or cascade-clear mappings — choose refuse for safety)

## Validation rules

- **ExamBlueprint:** `min_items ≤ max_items`, both > 0; `duration_minutes > 0`; `0 < passing_score < max_score`; `effective_date` required; `version_label` non-empty (DB unique). `set-current` is the only way to set `is_current=true` (PUT ignores `is_current`).
- **ExamDomain:** `number ≥ 1`; unique per blueprint (DB); `0 ≤ weight_pct ≤ 100`; name non-empty.
- **Book:** title non-empty; tenant = caller org.
- **Chapter:** `order_index ≥ 0`; title non-empty; book must belong to caller org.
- **KnowledgePoint:** name non-empty; `parent_id` (if set) must exist; **no cycle** — parent cannot be the kp itself or any of its descendants. Delete refused if it has children, bindings, or mapped questions.
- **Tag:** name non-empty; unique (DB). Names stored as given (PRD examples lowercase but not enforced).
- **Delete guards:** deleting a blueprint/domain/kp/tag that live questions reference → `409 Conflict` (refuse). Book/chapter delete: refuse if questions map to them.

## Error mapping

Service raises → HTTP: `ValidationError(ValueError)` → 422; `NotFound(LookupError)` → 404; `ConflictError(ValueError)` → 409 (delete guards, cycles, unique collisions caught as integrity). Routes catch and map; `session.commit()` only after success.

## Testing

TDD against `cissp_test` (per-test SAVEPOINT rollback). Service tests in `tests/test_taxonomy_admin_service.py`; API tests in `tests/test_taxonomy_admin_api.py`. Reuse the `_admin`/`_headers` helper pattern from `test_taxonomy_api.py`/`test_question_api.py` (register user, set role to system_admin, mint token with all perms). FK constraints require real rows — never random UUIDs for org/actor.

Key test cases: blueprint create + set-current flips others; domain weight bounds; book/chapter tenant isolation (foreign org → 404); kp cycle prevention; kp delete-with-children refused; tag unique-name 409; delete-with-mapped-questions 409; permission 403 for non-admin; audit log written.

## Out of scope (later sub-projects)

- Practice/exam session APIs (E/F), CAT (G), analytics & full admin UI (H).
- Bulk import of taxonomy (the seed already loads the canonical 8 domains).
- Frontend admin pages (H).
