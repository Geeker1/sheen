from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHEEN_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://sheen:sheen@localhost:5433/sheen"

    # Where raw snapshots are archived.
    s3_bucket: str = "sheen-raw"
    s3_endpoint_url: str | None = None  # LocalStack

    nosdra_url: str = "https://oilspillmonitor.ng/api/spill-data.php?dataset=nosdra&format=json"

    # Analysis window. Raw keeps everything; validation drops records dated outside it.
    window_start: date = date(2005, 1, 1)
    window_end: date = date(2024, 12, 31)

    ruleset_path: Path = Path("rules/v1.yaml")
    data_dir: Path = Path("data")

    log_json: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
