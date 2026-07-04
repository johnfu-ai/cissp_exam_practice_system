# P0 #6 — Health Readiness + TLS + Safe Migrations Design Spec

Date: 2026-07-04
Status: Approved (self-approved under autonomous goal directive)
Parent audit: `docs/audits/2026-07-03-improvement-proposals.md` (P0 #6, audit C-2/C-3/C-4 + M-11)

## 1. Goal & scope

1. **`/health` always returns 200 even when DB/Redis are down** (audit C-2) —
   useless as a readiness probe. Split into `/live` (liveness, no deps) and
   `/ready` (readiness, 503 when a dep is down); keep `/health` as an alias of
   `/ready` (detailed body + correct status code) so the frontend + existing
   tests keep working. Reuse a pooled Redis client instead of opening a new
   connection per probe (audit M-11).
2. **No TLS path** (audit C-3) — add `HTTPSRedirectMiddleware` in non-dev
   `app_env` so production HTTP is redirected to HTTPS. (Full reverse-proxy TLS
   is a deploy concern; this ensures the app itself enforces HTTPS.)
3. **Migration runs on every container start with no lock** (audit C-4) — races
   across N replicas. Move `alembic upgrade head && seed` out of the backend
   CMD into a one-shot `migrate` compose service that the backend
   `depends_on: service_completed_successfully`. Add a backend compose
   `healthcheck` against `/live`.

**Out of scope:** a managed reverse proxy / cert manager (deploy infra); k8s
manifests; PgBouncer (audit L3).

## 2. Health endpoints (`app/main.py`)

- `_check_deps() -> (db_status, redis_status)` — DB via the pooled engine
  (`SELECT 1`); Redis via a module-level pooled client (`ping`). Each wrapped in
  try/except → `"ok"` / `"error"`.
- `GET /live` → always `200 {"status":"ok"}` (process up; no dep checks).
- `GET /ready` → `200` + `{"status":"ok","db":"ok","redis":"ok"}` when both ok;
  `503` + `{"status":"degraded",...}` when any dep down.
- `GET /health` → alias of `/ready` (same body + status). Fixes the always-200
  bug; the frontend status badge + existing test still work on the happy path.

## 3. HTTPS redirect (`app/main.py`)

When `settings.app_env.lower() not in {development,dev,test}`, add
`HTTPSRedirectMiddleware` (Starlette) so HTTP requests 301 → HTTPS. Dev keeps
plain HTTP.

## 4. Compose + Dockerfile

- `backend/Dockerfile` CMD → `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  (migration + seed removed from the per-replica start path).
- `docker-compose.yml`: new `migrate` service (builds `./backend`, runs
  `alembic upgrade head && python -m app.db.seed`, `restart: "no"`, depends on
  postgres+redis healthy); `backend` `depends_on: migrate:
  condition: service_completed_successfully`. Add a backend `healthcheck`
  (`curl -f /live`).

## 5. Testing

- `tests/test_health.py`: `/live` always 200; `/ready` 200+detailed when deps
  ok; `/ready` 503 when DB down (monkeypatch `_check_deps`); `/health` 503 when
  a dep down (the bug fix); deps-down does NOT raise.
- Existing `test_health_returns_ok_with_db_and_redis` still passes (happy path).

## 6. Migration

None.

## 7. Acceptance criteria

1. `/live` is 200 unconditionally; `/ready` + `/health` return 503 when a dep is
   down (no longer always 200).
2. Non-dev `app_env` redirects HTTP → HTTPS.
3. The backend container no longer runs migrations on every start; a one-shot
   `migrate` service does, and the backend waits for it + has a healthcheck.
4. Full suite green.
