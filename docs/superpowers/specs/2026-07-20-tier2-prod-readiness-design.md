# Tier 2 production-readiness (#24, #25, #26, #27, #28)

**Date:** 2026-07-20
**Audit items:** improvement-audit Tier 2 (#24–#28) + #25 backups/Redis durability.
**Branch:** `feat/p2-tier2-prod-readiness`

## Problem

The full PRD functional scope and all open security holes were closed, but the
stack was not safe to run anywhere but a local dev box: single uvicorn worker
with bcrypt on the event loop (no prod concurrency), no graceful shutdown
(in-flight exam submits killed on deploy), no structured logs / request IDs /
metrics / Sentry, Redis with no persistence (a restart logged out every user
and cleared all lockouts), no Postgres backup story, Dockerfiles ran as root
and shipped the full build toolchain + node_modules, and one compose file
served dev and "prod" with no resource limits or restart policies.

## Design

### #26 Observability (`app/core/{logging,metrics,observability}.py`, `main.py`)
- **Structured logging** via `structlog` - every line is one JSON object on
  stdout (level, iso timestamp, request_id, event, kwargs). stdlib loggers
  (uvicorn.access etc.) are routed through the same renderer via
  `ProcessorFormatter`, so the whole stream is uniform.
- **Request ID** - `RequestContextMiddleware` honors or mints an `X-Request-ID`
  per request, binds it to a `contextvars.ContextVar` (so every structured log
  line for the request carries it), and echoes it on the response.
- **Metrics** - `/metrics` exposes Prometheus counters/histograms
  (`http_requests_total{method,route,status}`, `http_request_duration_seconds`).
  Route labels are the matched route template (or raw path with UUID/numeric
  segments collapsed to `/:id`) so label cardinality stays bounded. Multiprocess-
  aware: when `PROMETHEUS_MULTIPROC_DIR` is set (prod, N workers), each worker
  writes to that dir and `/metrics` aggregates via `MultiProcessCollector`;
  single-worker dev uses the in-process registry.
- **Sentry** - `sentry_sdk.init` only when `SENTRY_DSN` is set (no-op otherwise,
  no SDK overhead); auto-detects the FastAPI/Starlette/SQLAlchemy integrations.
- New settings: `log_level`, `sentry_dsn`, `sentry_traces_sample_rate`.
- New deps: `structlog`, `prometheus-client`, `sentry-sdk[fastapi]`.

### #24 Workers + graceful shutdown (`backend/entrypoint.sh`, `main.py` lifespan)
- `entrypoint.sh` `exec`s uvicorn with `--workers ${UVICORN_WORKERS:-1}` and
  `--timeout-graceful-shutdown ${UVICORN_GRACEFUL_SHUTDOWN_SECONDS:-30}`. `exec`
  makes uvicorn PID 1 so it receives SIGTERM directly.
- On SIGTERM, uvicorn stops accepting new connections and waits up to the
  graceful-shutdown window for in-flight requests (exam submit, migration) to
  finish; the FastAPI `lifespan` then closes the DB pool (`dispose_engine`) and
  the shared health Redis client.
- Multi-worker safety: Redis-backed stores (refresh tokens, rate limits,
  revoked tokens, password-reset tokens) are shared across workers, so scaling
  needs no extra coordination; the engine pool is per-worker (stateless).
- `CMD` (not `ENTRYPOINT`) so the one-shot `migrate` compose service can override
  the command with `alembic upgrade head && python -m app.db.seed`.

### #27 Harden Dockerfiles (multi-stage, non-root)
- **Backend** - two stages: a builder (gcc/libpq-dev + venv) and a slim runtime
  that copies only the venv + app source, runs as a non-root `app` user
  (uid 1001), and ships no build toolchain. `psycopg[binary]` bundles libpq, so
  the runtime needs only `curl` (healthcheck).
- **Frontend** - two stages: a builder (`npm ci` + `next build` with
  `output: "standalone"`) and a slim runtime that copies only the traced
  standalone server + `.next/static`, runs as a non-root `nextjs` user. The
  hardcoded `registry.npmmirror.com` is replaced by a `NPM_REGISTRY` build arg
  (default: official npm registry).
- `.dockerignore` hardened so tests/docs/caches/secrets never enter the image.

### #28 + #25 Compose split, limits, restart, Redis durability, backups
- `docker-compose.yml` (base/dev) + `docker-compose.prod.yml` (prod overrides,
  applied via `-f docker-compose.yml -f docker-compose.prod.yml`).
- **Restart policies** - `unless-stopped` on long-running services (dev),
  `always` in prod.
- **Redis durability** - `redis-server --appendonly yes` + a `redisdata` named
  volume, so a restart no longer logs out every user or clears lockouts.
- **Resource limits** - prod `deploy.resources.limits` (backend 1g/2cpu,
  frontend 512m/1cpu).
- **Prod hardening** - `APP_ENV=production` (HTTPS redirect + strong-secret
  enforcement), DB + Redis NOT published to the host (`ports: !reset []`),
  required env vars (`JWT_SECRET`, `POSTGRES_PASSWORD`, `CORS_ORIGINS` via
  `${VAR:?...}`), `UVICORN_WORKERS=2`, multiprocess metrics.
- **Backups** - a `backup` compose service (profile `backup`) dumps Postgres to
  a `backups` volume (gzipped plain SQL, keeps the 30 most recent).
  `scripts/backup.sh` runs it (host crontab for daily, PRD §7.3);
  `scripts/restore.sh` streams a dump back into the DB.

## Tests / verification
- Backend: `test_observability.py` (5) - /metrics exposes counters, X-Request-ID
  generated + echoed, requests counted by route, 404/UUID paths normalized
  (no cardinality leak). Full suite green (567).
- Frontend: lint 0 errors, `next build` succeeds, `.next/standalone/server.js`
  produced.
- Docker: both images build multi-stage; `docker compose up` e2e (migrate ->
  /health 200, /metrics, login smoke, frontend 200, backup service writes a
  dump, graceful SIGTERM shutdown).

## Out of scope
- A reverse proxy / TLS termination in front of backend+frontend (prod compose
  publishes 8000/3000; an operator fronts them with nginx).
- Fixing the frontend's build-time `NEXT_PUBLIC_BACKEND_URL` (currently falls
  back to `http://localhost:8000`; a real prod deploy needs it set at build or a
  same-origin proxy) - pre-existing, not a Tier 2 Dockerfile concern.
- Stale-multiprocess-file handling across worker deaths (the dir is on the
  container's ephemeral layer, so a fresh container starts clean).
