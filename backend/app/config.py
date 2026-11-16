"""App settings loaded from environment variables and the project's .env file.

Keeping secrets (DB password, JWT key) out of the code means they never end
up in git, and each environment (laptop, CI, server) can use its own values.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo root (three levels up from this file), so .env is found no matter
# which folder the server is started from.
ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Typed, validated configuration for the whole backend.

    Fields without a default are required: the app refuses to start if one is
    missing, which is better than failing later in the middle of a request.
    """

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    # 5433 is the port Docker exposes on the host, which avoids clashing with
    # a locally installed Postgres on the default 5432.
    postgres_host_port: int = 5433
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # extra="ignore" lets .env hold variables other tools need (e.g. pgAdmin)
    # without pydantic rejecting them as unknown fields.
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")


# One shared instance, created at import time, that the rest of the app imports.
settings = Settings()
