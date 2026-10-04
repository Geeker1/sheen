"""Shared fixtures. DB tests run against a throwaway PostGIS container."""

import os
import shutil
from collections.abc import Iterator

import pytest


def _docker_available() -> bool:
    return shutil.which("docker") is not None


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("docker not available")
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgis/postgis:16-3.4", driver=None) as pg:
        url = pg.get_connection_url()
        os.environ["SHEEN_DATABASE_URL"] = url

        from alembic import command
        from alembic.config import Config

        from sheen import db
        from sheen.config import get_settings

        get_settings.cache_clear()
        db.close_pool()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        db.close_pool()
