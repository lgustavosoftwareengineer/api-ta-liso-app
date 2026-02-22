from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    login_token_ttl_seconds: int = 600
    aws_region: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    ses_from_email: str
    environment: str = "development"
    debug: bool = False
    allowed_origins: list[str] = []

@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
