"""Tier 2 #26: per-request observability glue - request ID + metrics + access log.

`RequestContextMiddleware` runs on every request to:
  * honor or mint an `X-Request-ID` and bind it to a contextvar so every
    structured log line for the request carries it (see app/core/logging.py);
  * record Prometheus counters/histograms (see app/core/metrics.py);
  * emit one structured access-log line per request.

Route templates are normalized (matched route path, or raw path with UUID /
numeric segments collapsed to `:id`) so label cardinality stays bounded.
"""
from __future__ import annotations

import re
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import get_logger
from app.core.metrics import http_request_duration_seconds, http_requests_total

# Bound by RequestContextMiddleware; read by the logging request_id processor.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_UUID_SEG = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I
)
_NUMERIC_SEG = re.compile(r"/\d+")


def route_template(request: Request) -> str:
    """Low-cardinality route label: the matched route's path template if the
    router already populated `scope["route"]`, else the raw path with UUID /
    numeric segments collapsed to `/:id`."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    path = request.url.path
    path = _UUID_SEG.sub("/:id", path)
    return _NUMERIC_SEG.sub("/:id", path)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        request.state.request_id = rid
        start = time.perf_counter()
        status = 500
        route = "unmatched"
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        except Exception:
            get_logger("app.request").exception(
                "unhandled", method=request.method, path=request.url.path
            )
            raise
        finally:
            duration = time.perf_counter() - start
            route = route_template(request)
            # Metrics must never break a request.
            try:
                http_requests_total.labels(request.method, route, str(status)).inc()
                http_request_duration_seconds.labels(request.method, route).observe(
                    duration
                )
            except Exception:  # pragma: no cover - defensive
                pass
            request_id_var.reset(token)
            get_logger("app.request").info(
                "request",
                method=request.method,
                route=route,
                path=request.url.path,
                status=status,
                duration_ms=round(duration * 1000, 2),
            )
