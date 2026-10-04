from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHEEN_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://sheen:sheen@localhost:5433/sheen"
    # On AWS the password comes from Secrets Manager on its own, so the URL is
    # built from these parts when SHEEN_DB_HOST is set.
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "sheen"
    db_user: str = "sheen"
    db_password: str | None = None

    # Where raw snapshots are archived.
    s3_bucket: str = "sheen-raw"
    s3_endpoint_url: str | None = None  # LocalStack in development; unset on AWS

    nosdra_url: str = "https://oilspillmonitor.ng/api/spill-data.php?dataset=nosdra&format=json"

    # Analysis window. Raw keeps everything; validation drops records dated outside it.
    window_start: date = date(2005, 1, 1)
    window_end: date = date(2024, 12, 31)

    ruleset_path: Path = Path("rules/v1.yaml")
    data_dir: Path = Path("data")

    log_json: bool = True

    @model_validator(mode="after")
    def _assemble_database_url(self) -> "Settings":
        if self.db_host:
            password = quote(self.db_password or "", safe="")
            self.database_url = (
                f"postgresql://{self.db_user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
                "?sslmode=require"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
