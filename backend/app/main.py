from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_engine


def create_app() -> FastAPI:
    app = FastAPI(title="CISSP Exam Practice System", version="0.1.0")

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

    return app


app = create_app()
