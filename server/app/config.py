# server/app/config.py
"""Application settings, loaded from environment / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "1.0.0"
    model_path: str = ""
    azure_vision_endpoint: str = ""
    azure_vision_key: str = ""
    reciclapi_key: str = ""
    max_image_bytes: int = 2 * 1024 * 1024
    contract_dir: Path = REPO_ROOT / "contract"
    content_dir: Path = REPO_ROOT / "content"


@lru_cache
def get_settings() -> Settings:
    return Settings()
