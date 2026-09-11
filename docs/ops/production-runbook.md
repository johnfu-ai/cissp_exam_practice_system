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
- `GET /metrics` — Prometheus counters (set `PROMETHEUS_MULTIPROC_DIR` when `UVICORN_WORKERS>1`)
- `X-Request-ID` — echoed on every response; search structured JSON logs by that id

## Backups

```bash
# daily (host crontab)
0 2 * * * cd /path/to/repo && bash scripts/backup.sh
# restore drill
bash scripts/restore.sh /path/to/backups/cissp_YYYYMMDD.sql.gz
```

Verify restore on a staging DB before relying on it. Redis AOF survives restarts; still treat Redis as ephemeral for tokens (users re-login after full wipe).

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
