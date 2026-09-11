# Production runbook — CISSP Exam Practice System

Operational guide for a non-local deployment. Companion to `docker-compose.yml` + `docker-compose.prod.yml` and Tier-2 observability.

## Stack

| Piece | Role |
|-------|------|
| Postgres 16 | Primary data |
| Redis 7 (AOF) | Refresh tokens, lockouts, rate limits, reset tokens |
| Backend (FastAPI / uvicorn) | API — migrate via one-shot `migrate` service |
| Frontend (Next.js) | Admin portal only |
| Flutter apps | Learner clients (Android / iOS / Windows) |

## Deploy (compose)

One command produces a complete, TLS-secured deployment — Caddy terminates TLS with automatic Let's Encrypt and path-routes a single public origin (`/api/*` + health → backend, everything else → admin frontend):

```bash
export JWT_SECRET='…≥32 chars, not change-me…'
export POSTGRES_PASSWORD='…'
export CADDY_DOMAIN='example.com'          # DNS A record → this host, 80+443 reachable
export CORS_ORIGINS='https://example.com'
# Optional but recommended:
export SMTP_HOST=smtp.example.com SMTP_PORT=587 SMTP_USER=… SMTP_PASSWORD=…
export SMTP_FROM='noreply@example.com'     # APP_PUBLIC_URL defaults to https://$CADDY_DOMAIN
export SENTRY_DSN='…'   # empty = disabled

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
curl -sf https://example.com/live
curl -sf https://example.com/ready
```

Required prod env (compose will fail without them): `JWT_SECRET`, `POSTGRES_PASSWORD`, `CADDY_DOMAIN`, `CORS_ORIGINS`.

Local prod-profile test (self-signed cert, use `curl -k`): `CADDY_DOMAIN=localhost JWT_SECRET=… POSTGRES_PASSWORD=… CORS_ORIGINS=https://localhost docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`.

The Flutter learner app's production API address is the same public origin — build release clients with `--dart-define=API_BASE_URL=https://example.com --dart-define=APP_ENV=production` (the release pipeline bakes in the repository variable `PROD_API_BASE_URL`, which should be set to this origin). Same-origin routing also means browser admin sessions need no CORS relaxation.

## TLS

Terminated at the in-stack Caddy service (`deploy/Caddyfile`): automatic HTTPS for real domains, self-signed internal cert for `CADDY_DOMAIN=localhost`, plain-HTTP `:80` fallback for air-gapped use. Backend enables `HTTPSRedirectMiddleware` when `APP_ENV` is not a dev value; uvicorn runs `--proxy-headers` with `FORWARDED_ALLOW_IPS` defaulting to the Docker bridge ranges so the backend sees the real client scheme through the proxy (no redirect loop) and logs real client IPs. Only Caddy's 80/443 are published — backend (including the unauthenticated `/metrics`), DB, and Redis are private to the compose network. To replace Caddy with your own LB, remove the `caddy` service and republish backend/frontend ports.

## Health & metrics

- `GET /live` — liveness (always 200 if process up)
- `GET /ready` / `/health` — readiness (503 if DB/Redis down)
- `GET /metrics` — Prometheus counters (set `PROMETHEUS_MULTIPROC_DIR` when `UVICORN_WORKERS>1`); reachable only inside the compose network (prod) or via `docker compose exec backend curl -s localhost:8000/metrics`
- `X-Request-ID` — echoed on every response; search structured JSON logs by that id

## Monitoring & alerting

`docker-compose.monitoring.yml` is an overlay that runs Prometheus + Alertmanager + Grafana **inside the compose network** (so they reach the unpublished `/metrics`):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f docker-compose.monitoring.yml up -d
```

UIs bind to `127.0.0.1` on the host (SSH-tunnel access, never public): Prometheus `:9090`, Alertmanager `:9093`, Grafana `:3001` (login `admin` / `$GRAFANA_ADMIN_PASSWORD`, default `admin-change-me` — set a real one).

- **Scrape**: backend `/metrics` every 15s, 30d retention.
- **Alert rules** (`deploy/monitoring/alerts.yml`): `BackendDown` (scrape down 2m, critical), `BackendHighErrorRate` (5xx > 2% for 10m, critical), `BackendHighLatencyP95` (p95 > 1s for 10m, warning), `BackendNoSuccessfulScrape` (10m total loss, critical).
- **Delivery**: Alertmanager is drop-by-default — alerts show in its UI but go nowhere until you add a receiver (Slack/Feishu/email webhook) in `deploy/monitoring/alertmanager.yml` and restart the service. Do this before you rely on the alerts.
- **Dashboard**: "CISSP Backend" is auto-provisioned in Grafana (request rate, 5xx ratio, p50/p95 latency, top routes).

## Backups

```bash
# daily (host crontab): custom-format DB dump + tar of the upload_data volume,
# keeps the 30 most recent of each, FAILS LOUDLY on an empty dump.
7 2 * * * cd /path/to/repo && bash scripts/backup.sh >> /var/log/cissp-backup.log 2>&1

# monthly restore drill (first of the month): restores the latest backup into
# a THROWAWAY database, verifies core tables + users + alembic version, drops
# it, and never touches the live DB.
17 3 1 * * cd /path/to/repo && bash scripts/restore-drill.sh >> /var/log/cissp-drill.log 2>&1

# real restore (DESTRUCTIVE — see the warnings inside the script):
bash scripts/restore.sh cissp-YYYYMMDDTHHMMSSZ.dump
```

Recovery objectives with this setup: **RPO ≈ 24h** (daily crontab — tighten by running `backup.sh` more often), **RTO ≈ minutes** (`docker compose stop backend migrate` → drop/recreate DB → `restore.sh` → `docker compose run --rm migrate` → start). A backup is only real after a restore has been exercised — that is what the drill cron proves monthly. Uploaded ETL datasets (`upload_data` volume) are tarred alongside each dump; restore them with `tar -xzf uploads-*.tar.gz -C <upload_data mount>`.

Redis AOF survives restarts; still treat Redis as ephemeral for tokens (users re-login after full wipe).

## Password reset email

When `SMTP_HOST` is set, `POST /api/auth/reset-password/request` emails `{APP_PUBLIC_URL}/forgot-password?token=…`. Production never returns the token in the JSON body. Without SMTP, self-serve reset is unavailable — use admin `POST /api/admin/users/{id}/reset-password`.

Dev default admin password after seed: `Adminadmin1` (override with `SEED_ADMIN_PASSWORD`).

## Flutter store signing

**Android:** copy `mobile/android/key.properties.example` → `mobile/android/key.properties`, point `storeFile` at an upload keystore. Without it, local release builds fall back to debug signing (local-dev convenience only — see below for the release pipeline, which enforces signing).

**iOS:** CI uses `--no-codesign`. App Store / TestFlight needs Apple Developer certs + provisioning profiles in the Mac runner (not stored in this repo).

**Windows:** MSIX / Store signing is a follow-up; the release pipeline ships an unsigned release zip.

## Release pipeline

Push a `v*` tag (e.g. `git tag v1.3.1 && git push origin v1.3.1`) to run `.github/workflows/release.yml`, which produces versioned, installable artifacts and registry images:

- **Signed Android APK + AAB** — requires the repository secrets `ANDROID_KEYSTORE_BASE64` (base64 of the upload keystore), `ANDROID_STORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`. The job **fails with a clear error** when they are missing instead of shipping a debug-signed build.
- **Windows x64 release zip** (unsigned) and an **unsigned iOS release compile** (proves release builds; store upload still needs Apple credentials on the runner).
- **Server images pushed to ghcr.io** — `ghcr.io/<repo>/backend:<version>` and `ghcr.io/<repo>/frontend:<version>` (+ `:latest`), built with `NEXT_PUBLIC_API_URL` baked in. Compose can then reference these image tags instead of building locally, which is what makes "roll back by redeploying the previous image tag" real.
- A **GitHub release** with the artifacts and generated notes. All app builds pass `--dart-define=APP_ENV=production` (dev conveniences compiled out) and `--build-name/--build-number` from the tag + run number.

Prerequisite: set the repository **variable** `PROD_API_BASE_URL` (Settings → Secrets and variables → Actions → Variables) to the production API origin; the workflow fails fast when it is unset. A `workflow_dispatch` dry run (version input) exercises all build jobs without creating the GitHub release.

## Incident basics

1. Check `/ready` and recent `docker compose logs backend --tail=200`.
2. Correlate with `X-Request-ID` in client errors and JSON logs.
3. If auth mass-fail: Redis down clears refresh cookies → users re-login; verify Redis volume.
4. If deploy stuck: confirm `migrate` service exited 0 before backend started.
5. Roll back by redeploying the previous image tag; DB migrations that are not backward-compatible need a forward fix (prefer expand/contract).

## Related docs

- `README.md` — local + prod compose shortcuts
- `docs/superpowers/specs/2026-07-20-tier2-prod-readiness-design.md` — Tier-2 design
- `docs/audits/2026-08-10-improvement-review.md` — current improvement backlog status
