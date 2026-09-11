"""Edge hardening #8: the general per-IP /api/* rate-limit middleware.

The middleware is exercised directly at the ASGI level (fabricated scope +
send) so the tests never touch the app's shared limiter or the network.
"""

import asyncio
import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import ApiRateLimitMiddleware
from app.core.security import InMemoryRateLimiter


class _Recorder:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, scope, receive, send):
        self.calls += 1
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b"{}"})


class _Sink:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, message) -> None:
        self.messages.append(message)


async def _no_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def _http_scope(path: str, method: str = "GET", ip: str = "1.2.3.4"):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": method,
        "path": path,
        "headers": [],
        "client": (ip, 12345),
        "query_string": b"",
    }


def _run(middleware, path, method="GET", ip="1.2.3.4"):
    async def go():
        sink = _Sink()
        await middleware(_http_scope(path, method, ip), _no_receive, sink)
        status = next(
            m["status"] for m in sink.messages if m["type"] == "http.response.start"
        )
        body = b"".join(
            m.get("body", b"") for m in sink.messages if m["type"] == "http.response.body"
        )
        return status, body

    return asyncio.run(go())


def _set_limit(monkeypatch, value: int):
    monkeypatch.setattr(settings, "api_rate_limit_per_minute", value, raising=False)


def test_over_limit_returns_429(monkeypatch):
    _set_limit(monkeypatch, 3)
    mw = ApiRateLimitMiddleware(_Recorder(), limiter=InMemoryRateLimiter())
    for _ in range(3):
        status, _ = _run(mw, "/api/questions")
        assert status == 200
    status, body = _run(mw, "/api/questions")
    assert status == 429
    assert json.loads(body) == {"detail": "too many requests"}


def test_exempt_paths_and_methods_never_consume_the_window(monkeypatch):
    _set_limit(monkeypatch, 3)
    mw = ApiRateLimitMiddleware(_Recorder(), limiter=InMemoryRateLimiter())
    # Non-API paths and health endpoints pass through untouched...
    for path in ("/", "/live", "/ready", "/metrics", "/favicon.ico"):
        status, _ = _run(mw, path)
        assert status == 200
    # ...and so do CORS preflights.
    status, _ = _run(mw, "/api/questions", method="OPTIONS")
    assert status == 200
    # The /api budget is still fully available.
    for _ in range(3):
        status, _ = _run(mw, "/api/questions")
        assert status == 200


def test_limit_zero_disables_the_middleware(monkeypatch):
    _set_limit(monkeypatch, 0)
    mw = ApiRateLimitMiddleware(_Recorder(), limiter=InMemoryRateLimiter())
    for _ in range(10):
        status, _ = _run(mw, "/api/questions")
        assert status == 200
    assert mw.app.calls == 10


def test_limit_is_per_ip(monkeypatch):
    _set_limit(monkeypatch, 3)
    mw = ApiRateLimitMiddleware(_Recorder(), limiter=InMemoryRateLimiter())
    for _ in range(3):
        status, _ = _run(mw, "/api/questions", ip="1.1.1.1")
        assert status == 200
    # A different client has its own window...
    status, _ = _run(mw, "/api/questions", ip="2.2.2.2")
    assert status == 200
    # ...while the first client is over its budget.
    status, _ = _run(mw, "/api/questions", ip="1.1.1.1")
    assert status == 429


def test_middleware_is_registered_in_create_app(monkeypatch):
    """The seam the unit tests bypass: create_app must actually mount the
    middleware, and it must resolve the limiter through
    dependencies.get_rate_limiter (overridable)."""
    import app.dependencies as deps
    from app.main import create_app

    _set_limit(monkeypatch, 3)
    monkeypatch.setattr(deps, "get_rate_limiter", lambda: InMemoryRateLimiter())
    client = TestClient(create_app())
    # Unauthenticated requests consume the budget (they still reach the app,
    # which answers 401) until the window trips...
    statuses = [client.get("/api/domains").status_code for _ in range(4)]
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429
    # ...while non-API paths stay unaffected.
    assert client.get("/live").status_code == 200
