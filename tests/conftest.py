"""Shared fixtures. DB tests run against a throwaway PostGIS container."""

import json
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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


# --- A tiny synthetic geography and a validated snapshot over it -------------
#
#     5.5N +-----------+-----------+-----------+
#          |  Bayelsa  |  Degema   |  Okrika   |
#          |  (BY)     |  (RI)     |  (RI)     |
#     4.5N +-----------+-----------+-----------+
#          5.5E        6.5E        7.0E        7.5E


def _square(x0: float, y0: float, x1: float, y1: float) -> str:
    return json.dumps(
        {
            "type": "MultiPolygon",
            "coordinates": [[[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]],
        }
    )


@pytest.fixture(scope="session")
def geography(database_url: str) -> None:
    areas = [
        ("NG006", 1, "Bayelsa", None, "BY", _square(5.5, 4.5, 6.5, 5.5)),
        ("NG033", 1, "Rivers", None, "RI", _square(6.5, 4.5, 7.5, 5.5)),
        ("NG006001", 2, "Yenagoa", "NG006", "BY", _square(5.5, 4.5, 6.5, 5.5)),
        ("NG033001", 2, "Degema", "NG033", "RI", _square(6.5, 4.5, 7.0, 5.5)),
        ("NG033002", 2, "Okrika", "NG033", "RI", _square(7.0, 4.5, 7.5, 5.5)),
    ]
    from sheen.db import connect

    with connect() as conn:
        conn.execute("TRUNCATE ref.admin_areas CASCADE")
        conn.cursor().executemany(
            """INSERT INTO ref.admin_areas (pcode, level, name, parent_pcode, state_code, geom)
               VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))""",
            areas,
        )


def _grid(lon: float, lat: float, srid: int) -> tuple[str, str]:
    """Express a WGS84 point in a projected CRS, as an operator might report it."""
    from sheen.db import connect

    with connect() as conn:
        row = conn.execute(
            """SELECT ST_X(p) AS x, ST_Y(p) AS y
               FROM ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s) p""",
            (lon, lat, srid),
        ).fetchone()
    assert row
    return f"{row['y']:.2f}", f"{row['x']:.2f}"  # (latitude field, longitude field)


def _record(id: str, **kw: Any) -> dict[str, Any]:
    # Distinct months per record so unrelated records are never "duplicates"
    # of each other; #7 overrides its date to duplicate #1 on purpose.
    base = {
        "id": id,
        "status": "confirmed",
        "company": "OPCO",
        "incidentdate": f"2018-{int(id):02d}-01",
        "contaminant": "cr",
        "estimatedquantity": "10",
        "cause": "eqf",
        "spillareahabitat": "la",
        "statesaffected": "RI",
    }
    return {**base, **kw}


@pytest.fixture(scope="session")
def validated(geography: None, tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    from sheen.ingest import nosdra
    from sheen.validation import engine

    grid_rivers = _grid(7.25, 5.0, 26392)  # Okrika, in the Mid Belt
    records = [
        # Reported coordinates in Okrika: used as-is.
        _record("1", latitude="5.0", longitude="7.25", lga="Okrika"),
        # Grid metres whose Mid Belt reading lands in the reported state.
        _record("2", latitude=grid_rivers[0], longitude=grid_rivers[1], lga="Okrika"),
        # Same metres, but reported in Bayelsa: no reading corroborates it.
        _record("3", latitude=grid_rivers[0], longitude=grid_rivers[1], statesaffected="BY"),
        # Point in Bayelsa, reported as Rivers -> state mismatch warning.
        _record("4", latitude="5.0", longitude="6.0", lga="Yenagoa"),
        # Reported LGA 'Okrika' but point in Degema, far from the border.
        _record("5", latitude="5.0", longitude="6.6", lga="Okrika"),
        # 'Degema West' still matches plain 'Degema': compass words only
        # conflict when both names carry one (Ukwa West vs Ukwa East).
        _record("6", latitude="5.0", longitude="6.6", lga="Degema West"),
        # Likely duplicate of #1: same operator, ~100 m, next day.
        _record("7", latitude="5.0009", longitude="7.25", incidentdate="2018-01-02", lga="Okrika"),
        # Not a spill.
        _record("8", latitude="5.0", longitude="7.3", contaminant="no", lga="Okrika"),
        # Outside the analysis window: dropped from clean entirely.
        _record("9", latitude="5.0", longitude="7.3", incidentdate="2025-03-01"),
        # Packed DMS: 5°00'00"N 7°15'00"E.
        _record("10", latitude="0500000", longitude="0071500", lga="Okrika"),
        # Nowhere near Nigeria.
        _record("11", latitude="20.0", longitude="16.0"),
    ]
    snapshot = tmp_path_factory.mktemp("snap") / "spills.json"
    snapshot.write_text(json.dumps(records))

    nosdra.archive = lambda *a, **k: None  # type: ignore[assignment]  # no S3 in tests
    nosdra.ingest(Path(snapshot))
    engine.validate()

    from sheen.db import connect

    with connect() as conn:
        spills = {
            r["spill_id"]: dict(r)
            for r in conn.execute(
                """SELECT s.spill_id, s.geom_method, s.analysable, a.name AS lga
                   FROM clean.spills s LEFT JOIN ref.admin_areas a ON a.pcode = s.lga_pcode"""
            )
        }
        for r in conn.execute("SELECT spill_id, code, details FROM clean.spill_issues ORDER BY id"):
            spills[r["spill_id"]].setdefault("issues", {}).setdefault(r["code"], []).append(r["details"])
    return spills
