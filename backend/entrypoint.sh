#!/bin/sh
# Tier 2 #24: launch uvicorn with N workers + graceful shutdown.
#
# `exec` replaces the shell with uvicorn so it becomes PID 1 and receives
# SIGTERM directly. On SIGTERM (deploy / scale-down / `docker stop`) uvicorn
# stops accepting new connections and waits up to --timeout-graceful-shutdown
# for in-flight requests (an exam submit, a migration) to finish, then the
# FastAPI lifespan closes the DB pool + Redis client.
#
# Worker count is runtime-configurable via UVICORN_WORKERS (default 1 = current
# behavior). Redis-backed stores (refresh tokens, rate limits, revoked tokens)
# are shared across workers, so horizontal scaling needs no extra coordination.
set -e
# Tier 2 #26: when multiprocess Prometheus metrics are enabled (prod, N workers),
# ensure the shared dir exists before uvicorn imports the metrics module. It
# lives on the container's ephemeral layer (not a volume) so stale files from a
# previous run never accumulate. Created as the non-root `app` user (USER app).
if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
  mkdir -p "${PROMETHEUS_MULTIPROC_DIR}"
fi
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${UVICORN_WORKERS:-1}" \
  --timeout-graceful-shutdown "${UVICORN_GRACEFUL_SHUTDOWN_SECONDS:-30}"
