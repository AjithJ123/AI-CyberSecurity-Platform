"""Application settings, loaded from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env — resolved absolutely so it works regardless of the CWD uvicorn
# is launched from (project root, backend/, or elsewhere).
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Runtime configuration pulled from the environment."""

    google_safe_browsing_api_key: str = ""
    virustotal_api_key: str = ""
    phishtank_api_key: str = ""
    groq_api_key: str = ""

    redis_url: str = "redis://localhost:6379"
    environment: Literal["dev", "staging", "prod"] = "dev"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:5500"

    model_config = SettingsConfigDict(env_file=str(_ENV_PATH), extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
