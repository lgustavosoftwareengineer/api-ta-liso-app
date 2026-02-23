import json
import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.secrets import get_aws_secrets

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict()

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    login_token_ttl_seconds: int = 600
    aws_region: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    ses_from_email: str
    api_key: str
    environment: str = "development"
    debug: bool = False
    allowed_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    secrets = get_aws_secrets()
    
    for key, value in secrets.items():
        env_key = key.upper()
        if env_key not in os.environ:
            os.environ[env_key] = value if isinstance(value, str) else json.dumps(value)

    return Settings()  # type: ignore[call-arg]
