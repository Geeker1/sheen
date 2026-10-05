from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHEEN_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://sheen:sheen@localhost:5433/sheen"

    nosdra_url: str = "https://oilspillmonitor.ng/api/spill-data.php?dataset=nosdra&format=json"

    # Reports in this period are analysed. Earlier ones are left out.
    window_start: date = date(2005, 1, 1)
    window_end: date = Field(default_factory=date.today)

    ruleset_path: Path = Path("rules/v1.yaml")
    data_dir: Path = Path("data")

    log_json: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
