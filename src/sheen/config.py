from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHEEN_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://sheen:sheen@localhost:5433/sheen"

    # Raw snapshots are archived here before anything else touches them.
    s3_bucket: str = "sheen-raw"
    s3_endpoint_url: str | None = None  # set for MinIO locally; unset on AWS

    nosdra_url: str = "https://oilspillmonitor.ng/api/spill-data.php?dataset=nosdra&format=json"

    # Analysis window. Incidents outside it are kept in raw/clean but flagged
    # and excluded from analysis, so the published numbers cover whole years.
    window_start: date = date(2005, 1, 1)
    window_end: date = date(2024, 12, 31)

    ruleset_path: Path = Path("rules/v1.yaml")
    data_dir: Path = Path("data")

    log_json: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
