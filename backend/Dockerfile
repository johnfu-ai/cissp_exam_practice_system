# Tier 2 #27: multi-stage build. Every Python dep ships a wheel
# (psycopg[binary] bundles libpq), so the builder needs NO gcc/libpq-dev and NO
# apt-get - the image builds without hitting a package mirror. The runtime is
# slim, runs as a non-root user, and ships only the venv + app source.

# ---- builder ----
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---- runtime ----
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Non-root user (useradd ships in the base debian image's `passwd` package).
RUN useradd --create-home --uid 1001 app

COPY --from=builder --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app . .

# #35 / FR-IMP-01: writable upload dir for the non-root `app` user. The named
# `upload_data` volume mounts here; creating it now (owned by app) makes the
# volume inherit app ownership on first mount so uploads can write to it.
RUN mkdir -p /app/uploads && chown -R app:app /app/uploads

USER app

EXPOSE 8000

# Tier 2 #24: the entrypoint `exec`s uvicorn with --workers (UVICORN_WORKERS,
# default 1) + --timeout-graceful-shutdown so in-flight requests finish on
# SIGTERM. CMD (not ENTRYPOINT) so the one-shot `migrate` compose service can
# override the command with `alembic upgrade head && python -m app.db.seed`.
CMD ["./entrypoint.sh"]
