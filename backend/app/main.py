from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
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

    @app.get("/health")
    def health() -> dict:
        db_status = "ok"
        redis_status = "ok"
        try:
            engine = get_engine()
            with Session(engine) as session:
                session.execute(text("SELECT 1"))
        except Exception:
            db_status = "error"
        try:
            import redis

            r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
            r.ping()
        except Exception:
            redis_status = "error"
        return {"status": "ok", "db": db_status, "redis": redis_status}

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
