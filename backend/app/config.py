from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_host_port: int = 5433

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")


settings = Settings()