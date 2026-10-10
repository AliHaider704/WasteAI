# File: server/app/config.py
"""Application settings, loaded from environment / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_version: str = "1.0.0"
    model_path: str = ""
    azure_vision_endpoint: str = ""
    azure_vision_key: str = ""
    reciclapi_key: str = ""
    log_level: str = "INFO"
    llm_tiebreaker_enabled: bool = False
    azure_caption: bool = False  # A38: also ask Azure for a caption (env AZURE_CAPTION)
    llm_daily_cap: int = 20
    # Source weights (D-031). Renormalized over the sources that answer.
    w_local: float = Field(0.6, gt=0, le=1)
    w_azure: float = Field(0.4, gt=0, le=1)
    w_reciclapi: float = Field(0.2, gt=0, le=1)
    w_llm: float = Field(0.3, gt=0, le=1)
    w_clip: float = Field(0.3, gt=0, le=1)  # A40, used only when CLIP_ENABLED=true
    clip_enabled: bool = False
    # Per-client /classify limit per minute (event mode raises it, A34). Default unchanged.
    rate_classify_per_min: int = Field(10, ge=1, le=600)
    max_image_bytes: int = 2 * 1024 * 1024
    contract_dir: Path = REPO_ROOT / "contract"
    content_dir: Path = REPO_ROOT / "content"


@lru_cache
def get_settings() -> Settings:
    return Settings()
