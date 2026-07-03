from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
