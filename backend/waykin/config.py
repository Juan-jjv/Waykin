import secrets
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from waykin import constants as C


class Settings(BaseSettings):
    """Every environment variable in spec B6. List-valued variables are comma-separated strings."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    EXPOSURE_SOURCE: str = "synthetic"
    DATA_DIR: Path = Path("../data")
    LOAD_RADII: str = "100"
    DEFAULT_RADIUS_M: int = C.DEFAULT_RADIUS_M
    DEMO_MODE: bool = False
    RELAY_PLAINTEXT: bool = False
    ADMIN_TOKEN: str = Field(default_factory=lambda: secrets.token_urlsafe(16))
    JOURNEY_TTL_MIN: int = C.JOURNEY_TTL_MIN_DEFAULT
    WAYKIN_MOCK: bool = False
    CITY_FEED: bool = False
    ALLOW_PUBLIC_EPS: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"
    DEMO_PASSWORD: str = "waykin-demo"  # for the demo account and family DEMO_MODE creates (waykin/demo/people.json)
    ACCOUNTS_DB: str = ""            # SQLite path for accounts and families; empty = DATA_DIR/app.sqlite, ":memory:" in mock mode

    @property
    def accounts_db_path(self) -> str:
        if self.ACCOUNTS_DB:
            return self.ACCOUNTS_DB
        return ":memory:" if self.WAYKIN_MOCK else str(self.DATA_DIR / "app.sqlite")

    @property
    def load_radii(self) -> list[int]:
        return [int(x) for x in self.LOAD_RADII.split(",") if x.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]

    @property
    def relay_mode(self) -> str:
        return "plaintext" if self.RELAY_PLAINTEXT else "e2ee"

    @property
    def build_dir(self) -> Path:
        return self.DATA_DIR / "build"
