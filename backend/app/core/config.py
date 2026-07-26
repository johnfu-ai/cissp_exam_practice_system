from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_ENVS = {"development", "dev", "test"}
_WEAK_SECRETS = {"change-me", "dev-only-change-me"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://cissp:cissp@localhost:5432/cissp"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14
    password_reset_token_ttl_minutes: int = 15
    bcrypt_rounds: int = 12
    login_lockout_threshold: int = 5
    login_lockout_window_minutes: int = 15
    # #10: per-IP rate limit on unauthenticated auth endpoints (login/register/
    # reset-password) — caps credential-stuffing from a single IP. Per-email
    # lockout alone never trips for password-spray against many accounts.
    login_rate_limit: int = 30
    login_rate_window_seconds: int = 60
    cors_origins: str = "http://localhost:3000"
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = ""
    # Tier 2 #24: uvicorn process model. The entrypoint execs uvicorn with
    # --workers N (default 1 = current behavior) + --timeout-graceful-shutdown
    # so in-flight exam submits finish on SIGTERM/deploy instead of being killed.
    uvicorn_workers: int = 1
    uvicorn_graceful_shutdown_seconds: int = 30
    # Tier 2 #26: observability. log_level is the root stdlib level; sentry_dsn
    # gates Sentry init (empty = disabled, no SDK overhead). traces_sample_rate
    # controls performance transaction sampling (0 = none).
    log_level: str = "info"
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0
    # FR-IMP-01 / #35: root directory for uploaded import files (CSV/XLSX/JSON).
    # Each upload materializes as ``<etl_upload_root>/<dataset_slug>/questions.<ext>``
    # so DatasetReader can auto-detect + re-read it at commit (drift detection).
    # Dev defaults to the bind-mounted ``docs/questions`` so uploads sit next to
    # seeded datasets; prod should point this at a persistent volume.
    etl_upload_root: str = "docs/questions"
    # P2: SQLAlchemy connection-pool tuning. Defaults match psycopg's pool; prod
    # with N uvicorn workers multiplies these (workers*N connections). pool_recycle
    # stays under Postgres' default idle timeout so connections are never reused
    # after a server-side close.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 1800

    def cors_origin_list(self) -> list[str]:
        """Parsed CORS origin list, trimmed. P2: a wildcard ('*') is forbidden
        with credentials (allow_credentials=True) - it would let any site make
        credentialed requests. Refuse to start in that case rather than silently
        degrading to an insecure CORS policy."""
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if "*" in origins:
            raise ValueError(
                "cors_origins='*' is not allowed with credentials. List the "
                "exact allowed origins (e.g. 'https://app.example.com')."
            )
        return origins

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        # In non-dev environments refuse to start with a default/weak secret —
        # a known jwt_secret lets anyone forge access tokens. Dev/test keep the
        # default so local setup and the test suite work out of the box.
        if self.app_env.lower() not in _DEV_ENVS:
            if self.jwt_secret in _WEAK_SECRETS or len(self.jwt_secret) < 32:
                raise ValueError(
                    "jwt_secret must be set to a strong value (>= 32 chars, not "
                    "the default 'change-me'/'dev-only-change-me') when app_env is "
                    "not a development environment. Set JWT_SECRET in the environment."
                )
        return self


settings = Settings()
