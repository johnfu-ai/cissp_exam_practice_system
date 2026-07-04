"""Tests for security response headers (P0 #4 / NFR-SEC-07)."""
from fastapi.testclient import TestClient

from app.main import create_app


def test_security_headers_present_on_health():
    app = create_app()
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    lower = {k.lower(): v for k, v in r.headers.items()}
    assert "content-security-policy" in lower
    assert "default-src 'self'" in lower["content-security-policy"]
    assert lower["x-content-type-options"] == "nosniff"
    assert lower["x-frame-options"] == "DENY"
    assert lower["referrer-policy"] == "strict-origin-when-cross-origin"
    # HSTS is only sent over TLS; TestClient uses http -> absent
    assert "strict-transport-security" not in lower


def test_hsts_present_over_tls():
    app = create_app()
    c = TestClient(app)
    r = c.get("/health", headers={"X-Forwarded-Proto": "https"})
    lower = {k.lower(): v for k, v in r.headers.items()}
    assert "strict-transport-security" in lower
    assert "max-age=31536000" in lower["strict-transport-security"]
