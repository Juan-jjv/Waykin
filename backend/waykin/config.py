"""Runtime configuration, read from environment variables (B6)."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from waykin import constants as C

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    EXPOSURE_SOURCE: Literal["synthetic", "eps"] = "synthetic"
    DATA_DIR: Path = Path("./data")
    LOAD_RADII: str = "100"                      # comma-separated, e.g. "50,100,200"
    DEFAULT_RADIUS_M: int = C.DEFAULT_RADIUS_M
    DEMO_MODE: bool = False
    RELAY_PLAINTEXT: bool = False
    ADMIN_TOKEN: str = Field(default_factory=lambda: secrets.token_urlsafe(16))
    JOURNEY_TTL_MIN: int = C.JOURNEY_TTL_MIN_DEFAULT
    WAYKIN_MOCK: bool = False
    CITY_FEED: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"

    # A4-internal knobs (not part of B6, sensible defaults)
    FRONTEND_DIST: Path = REPO_ROOT / "frontend" / "dist"
    SERVE_FRONTEND: bool = False                 # also serve the SPA outside demo mode (production build)
    MOCK_HAZARD_DELAY_S: float = 15.0
    SWEEP_INTERVAL_S: float = 15.0

    @property
    def load_radii(self) -> list[int]:
        return [int(x) for x in self.LOAD_RADII.split(",") if x.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]

    @property
    def relay_mode(self) -> Literal["e2ee", "plaintext"]:
        return "plaintext" if self.RELAY_PLAINTEXT else "e2ee"

    @property
    def build_dir(self) -> Path:
        return self.DATA_DIR / "build"

    @property
    def serve_frontend(self) -> bool:
        return (self.DEMO_MODE or self.SERVE_FRONTEND) and (self.FRONTEND_DIST / "index.html").is_file()


@lru_cache
def get_settings() -> Settings:
    return Settings()
