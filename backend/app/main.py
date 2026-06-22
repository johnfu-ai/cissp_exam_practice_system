from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.etl import router as etl_router
from app.api.taxonomy import router as taxonomy_router
from app.core.config import settings
from app.db.session import get_engine


def create_app() -> FastAPI:
    app = FastAPI(title="CISSP Exam Practice System", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    app.include_router(auth_router)
    app.include_router(etl_router)
    app.include_router(taxonomy_router)

    return app


app = create_app()
