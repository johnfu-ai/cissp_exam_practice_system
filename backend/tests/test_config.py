"""Tests for Settings security validation (P0 #2)."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _make(**overrides) -> Settings:
    # _env_file=None so a local .env never interferes with the test values.
    return Settings(_env_file=None, **overrides)


def test_prod_rejects_default_jwt_secret():
    with pytest.raises(ValidationError):
        _make(app_env="production", jwt_secret="change-me")


def test_prod_rejects_dev_compose_secret():
    with pytest.raises(ValidationError):
        _make(app_env="production", jwt_secret="dev-only-change-me")


def test_prod_rejects_short_jwt_secret():
    with pytest.raises(ValidationError):
        _make(app_env="production", jwt_secret="a" * 31)


def test_prod_accepts_strong_jwt_secret():
    s = _make(app_env="production", jwt_secret="a" * 32)
    assert s.jwt_secret == "a" * 32


def test_dev_allows_default_jwt_secret():
    s = _make(app_env="development", jwt_secret="change-me")
    assert s.jwt_secret == "change-me"


def test_dev_alias_allows_default_jwt_secret():
    # "dev" (the value used in docker-compose) is also treated as dev
    s = _make(app_env="dev", jwt_secret="dev-only-change-me")
    assert s.jwt_secret == "dev-only-change-me"


def test_test_env_allows_default_jwt_secret():
    s = _make(app_env="test", jwt_secret="change-me")
    assert s.jwt_secret == "change-me"
