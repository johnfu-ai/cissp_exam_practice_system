from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.requests import Request

from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.etl import router as etl_router
from app.api.exam import router as exam_router
from app.api.practice import router as practice_router
from app.api.questions import router as questions_router
from app.api.taxonomy import router as taxonomy_router
from app.api.users import router as users_router
from app.core.config import settings
from app.db.session import get_engine

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Defense-in-depth response headers (NFR-SEC-07): a strict CSP blocks
    script injection even if sanitized content slipped through; nosniff /
    frame-options / referrer-policy harden the browser side. HSTS is sent only
    when the request is over TLS (directly or via a trusted X-Forwarded-Proto)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


_health_redis = None


def _get_health_redis():
    """A single shared Redis client for health probes (avoids opening a new
    connection on every /ready check — audit M-11)."""
    global _health_redis
    if _health_redis is None:
        import redis

        _health_redis = redis.from_url(settings.redis_url, socket_connect_timeout=2)
    return _health_redis


def _check_deps() -> tuple[str, str]:
    """Return (db_status, redis_status) — each 'ok' or 'error'. Never raises."""
    db_status = "ok"
    redis_status = "ok"
    try:
        engine = get_engine()
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    try:
        _get_health_redis().ping()
    except Exception:
        redis_status = "error"
    return db_status, redis_status


def create_app() -> FastAPI:
    app = FastAPI(title="CISSP Exam Practice System", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Added last -> outermost, so security headers land on every response
    # (including CORS preflight).
    app.add_middleware(SecurityHeadersMiddleware)
    # In non-dev environments, force HTTPS (audit C-3). Dev keeps plain HTTP.
    if settings.app_env.lower() not in {"development", "dev", "test"}:
        app.add_middleware(HTTPSRedirectMiddleware)

    @app.get("/live")
    def live() -> dict:
        # Liveness: process is up. No dependency checks (so a dep blip doesn't
        # get the pod killed by a liveness probe).
        return {"status": "ok"}

    def _ready_body(response: Response) -> dict:
        db_status, redis_status = _check_deps()
        ok = db_status == "ok" and redis_status == "ok"
        response.status_code = 200 if ok else 503
        return {"status": "ok" if ok else "degraded", "db": db_status, "redis": redis_status}

    @app.get("/ready")
    def ready(response: Response) -> dict:
        # Readiness: 503 when a dependency is down (audit C-2 fix).
        return _ready_body(response)

    @app.get("/health")
    def health(response: Response) -> dict:
        # Backward-compat alias of /ready (frontend status badge + existing
        # tests). Now returns 503 when degraded instead of always 200.
        return _ready_body(response)

    app.include_router(analytics_router)
    app.include_router(auth_router)
    app.include_router(etl_router)
    app.include_router(taxonomy_router)
    app.include_router(questions_router)
    app.include_router(practice_router)
    app.include_router(exam_router)
    app.include_router(admin_router)
    app.include_router(users_router)

    return app


app = create_app()
