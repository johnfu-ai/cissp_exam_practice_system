# P0 #6 — Health Readiness + TLS + Safe Migrations Implementation Plan

> TDD. Spec: `docs/superpowers/specs/2026-07-04-health-tls-migrations-design.md`.

## Task 1: /live + /ready + /health (TDD)

- [ ] Failing tests in `tests/test_health.py`: `/live` 200 always; `/ready` 200+detailed happy; `/ready` 503 + `degraded` when a dep down (monkeypatch `_check_deps`); `/health` 503 when dep down.
- [ ] Implement `_check_deps()` (pooled engine + module-level redis client) + `/live`, `/ready`, `/health` (alias) in `app/main.py`.
- [ ] Pass. Commit `feat(health): /live + /ready split, 503 on dep failure`.

## Task 2: HTTPS redirect in prod

- [ ] Add `HTTPSRedirectMiddleware` to `create_app()` when `app_env` not dev. Commit `feat(security): HTTPS redirect in non-dev`.

## Task 3: Compose migrate service + backend healthcheck

- [ ] `backend/Dockerfile` CMD → uvicorn only.
- [ ] `docker-compose.yml`: `migrate` one-shot service + backend `depends_on: service_completed_successfully` + backend `healthcheck` on `/live`.
- [ ] Full suite green. Commit + docs + push.
