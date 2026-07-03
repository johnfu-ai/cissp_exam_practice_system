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
    cors_origins: str = "http://localhost:3000"
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = ""

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
