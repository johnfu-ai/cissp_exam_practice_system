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

```bash
export JWT_SECRET='…≥32 chars, not change-me…'
export POSTGRES_PASSWORD='…'
export CORS_ORIGINS='https://admin.example.com'
# Optional but recommended:
export SMTP_HOST=smtp.example.com SMTP_PORT=587 SMTP_USER=… SMTP_PASSWORD=…
export SMTP_FROM='noreply@example.com' APP_PUBLIC_URL='https://admin.example.com'
export SENTRY_DSN='…'   # empty = disabled

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
curl -sf https://api.example.com/live
curl -sf https://api.example.com/ready
```

Required prod env (compose will fail without them): `JWT_SECRET`, `POSTGRES_PASSWORD`, `CORS_ORIGINS`.

## TLS

Terminate TLS at a reverse proxy (Caddy / nginx / cloud LB) in front of the published frontend and backend. Backend enables `HTTPSRedirectMiddleware` when `APP_ENV` is not a dev value. Prefer proxy → container over publishing DB/Redis ports (prod compose already clears host ports).

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

**Android:** copy `mobile/android/key.properties.example` → `mobile/android/key.properties`, point `storeFile` at an upload keystore. Without it, release builds fall back to debug signing. Optional CI secrets for a signed job: `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_PASSWORD`, `ANDROID_KEY_ALIAS` (decode keystore in the job, write `key.properties`, `flutter build appbundle --release`). Default CI still builds **debug** APKs.

**iOS:** CI uses `--no-codesign`. App Store / TestFlight needs Apple Developer certs + provisioning profiles in the Mac runner (not stored in this repo).

**Windows:** MSIX / Store signing is a follow-up; current CI builds an unsigned debug Windows binary.

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
