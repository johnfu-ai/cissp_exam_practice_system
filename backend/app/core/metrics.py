"""Tier 2 #26: Prometheus metrics.

Counters/histograms are defined at module scope (shared across one process).
When `PROMETHEUS_MULTIPROC_DIR` is set (multi-worker uvicorn, see the prod
compose), each worker writes its increments to that directory and `/metrics`
aggregates them via `MultiProcessCollector`; otherwise the in-process default
registry is used (single-worker dev). This keeps counts correct under
`--workers N` instead of only reflecting whichever worker served the scrape.

Labels use the normalized route template (see observability.route_template) so
cardinality stays bounded - a per-UUID label set would be an unbounded leak.
"""
from __future__ import annotations

import os

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)

_MULTIPROC = bool(os.environ.get("PROMETHEUS_MULTIPROC_DIR"))

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests by method, normalized route, and status code.",
    ["method", "route", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds, by method and normalized route.",
    ["method", "route"],
)


def metrics_response() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    if _MULTIPROC:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY
    return generate_latest(registry), CONTENT_TYPE_LATEST
