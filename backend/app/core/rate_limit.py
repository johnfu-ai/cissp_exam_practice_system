"""General per-IP rate limit across all /api/* routes (edge hardening #8).

The dedicated auth-endpoint limiter (#10) only covers register/login/reset;
everything else — practice delivery, exam upserts, ETL preview, analytics —
was unlimited. This middleware is a generous abuse backstop (default
600 req/min/IP), NOT capacity management: a classroom behind one NAT stays
far under it, and legitimate single users make a handful of requests per
screen. Set ``API_RATE_LIMIT_PER_MINUTE=0`` to disable.

Exemptions: non-/api paths, the health/metrics endpoints, and CORS
preflights (OPTIONS). Auth routes keep their tighter dedicated limits.
"""

from __future__ import annotations

import json
import logging

from app.core.config import settings
from app.core.security import RateLimiter

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = {"/live", "/ready", "/health", "/metrics"}


class ApiRateLimitMiddleware:
    """Pure ASGI middleware so it runs before routing and dependency trees.

    The limiter resolves lazily from ``app.dependencies.get_rate_limiter``
    (Redis-backed, fixed-window, shared with the auth limiter); tests inject
    an ``InMemoryRateLimiter`` via the constructor instead.
    """

    def __init__(self, app, *, limiter: RateLimiter | None = None) -> None:
        self.app = app
        self._limiter = limiter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = settings.api_rate_limit_per_minute
        path: str = scope.get("path", "")
        if (
            limit <= 0
            or not path.startswith("/api/")
            or path in _EXEMPT_PATHS
            or scope.get("method") == "OPTIONS"
        ):
            await self.app(scope, receive, send)
            return

        if self._limiter is None:
            # Imported lazily to avoid a circular import at module load.
            from app.dependencies import get_rate_limiter

            self._limiter = get_rate_limiter()

        client = scope.get("client")
        ip = client[0] if client else "unknown"
        if self._limiter.allow(f"api:{ip}", limit=limit, window_seconds=60):
            await self.app(scope, receive, send)
            return

        logger.warning("api rate limit exceeded for %s on %s", ip, path)
        body = json.dumps({"detail": "too many requests"}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"retry-after", b"60"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
