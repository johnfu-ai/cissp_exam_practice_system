FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg and healthchecks
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# The API only. Migrations + seed run once via the `migrate` compose service
# (depends_on: service_completed_successfully) so N replicas don't race on
# `alembic upgrade head` (audit P0 #6 C-4).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
