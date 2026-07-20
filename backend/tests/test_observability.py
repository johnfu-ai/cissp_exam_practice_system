"""Tier 2 #26: observability - request ID + /metrics + structured logging."""
from fastapi.testclient import TestClient

from app.main import app


def test_metrics_endpoint_exposes_counters():
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    # The request we just made (and this one) are counted.
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_request_id_is_generated_when_absent():
    client = TestClient(app)
    r = client.get("/live")
    assert r.status_code == 200
    rid = r.headers.get("x-request-id")
    assert rid is not None
    # uuid4().hex - 32 hex chars, no dashes.
    assert len(rid) == 32
    int(rid, 16)  # parses as hex


def test_request_id_is_echoed_when_provided():
    client = TestClient(app)
    r = client.get("/live", headers={"X-Request-ID": "abc-123-trace"})
    assert r.status_code == 200
    assert r.headers["x-request-id"] == "abc-123-trace"


def test_metrics_counts_requests_by_route():
    client = TestClient(app)
    # Make a couple of requests to /live so the route label is non-zero.
    client.get("/live")
    client.get("/live")
    r = client.get("/metrics")
    assert r.status_code == 200
    # The /live route template appears as a label value.
    assert 'route="/live"' in r.text or "route=\"/live\"" in r.text


def test_404_is_counted_without_cardinality_leak():
    client = TestClient(app)
    # A path with a UUID segment should be normalized to /:id, not counted as a
    # distinct label per UUID.
    client.get("/api/nonexistent/550e8400-e29b-41d4-a716-446655440000")
    r = client.get("/metrics")
    assert r.status_code == 200
    # The raw UUID must NOT appear as a route label.
    assert "550e8400-e29b-41d4-a716-446655440000" not in r.text
