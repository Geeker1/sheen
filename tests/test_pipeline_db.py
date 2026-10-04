"""End-to-end validation against PostGIS with a tiny synthetic geography.

Two square "states" side by side, Rivers split into two LGAs:

    5.5N +-----------+-----------+-----------+
         |  Bayelsa  |  Degema   |  Okrika   |
         |  (BY)     |  (RI)     |  (RI)     |
    4.5N +-----------+-----------+-----------+
         5.5E        6.5E        7.0E        7.5E
"""

import json
from pathlib import Path
from typing import Any

import pytest

from sheen.db import connect

pytestmark = pytest.mark.db


def _square(x0: float, y0: float, x1: float, y1: float) -> str:
    return json.dumps(
        {
            "type": "MultiPolygon",
            "coordinates": [[[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]],
        }
    )


@pytest.fixture(scope="module")
def geography(database_url: str) -> None:
    areas = [
        ("NG006", 1, "Bayelsa", None, "BY", _square(5.5, 4.5, 6.5, 5.5)),
        ("NG033", 1, "Rivers", None, "RI", _square(6.5, 4.5, 7.5, 5.5)),
        ("NG006001", 2, "Yenagoa", "NG006", "BY", _square(5.5, 4.5, 6.5, 5.5)),
        ("NG033001", 2, "Degema", "NG033", "RI", _square(6.5, 4.5, 7.0, 5.5)),
        ("NG033002", 2, "Okrika", "NG033", "RI", _square(7.0, 4.5, 7.5, 5.5)),
    ]
    with connect() as conn:
        conn.execute("TRUNCATE ref.admin_areas CASCADE")
        conn.cursor().executemany(
            """INSERT INTO ref.admin_areas (pcode, level, name, parent_pcode, state_code, geom)
               VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))""",
            areas,
        )


def _grid(lon: float, lat: float, srid: int) -> tuple[str, str]:
    """Express a WGS84 point in a projected CRS, as an operator might report it."""
    with connect() as conn:
        row = conn.execute(
            """SELECT ST_X(p) AS x, ST_Y(p) AS y
               FROM ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s) p""",
            (lon, lat, srid),
        ).fetchone()
    assert row
    return f"{row['y']:.2f}", f"{row['x']:.2f}"  # (latitude field, longitude field)


def _record(id: str, **kw: Any) -> dict[str, Any]:
    base = {
        "id": id,
        "status": "confirmed",
        "company": "OPCO",
        "incidentdate": "2018-06-01",
        "contaminant": "cr",
        "estimatedquantity": "10",
        "cause": "eqf",
        "spillareahabitat": "la",
        "statesaffected": "RI",
    }
    return {**base, **kw}


@pytest.fixture(scope="module")
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
        # 'Degema West' must not match 'Degema East' style twins; here it should
        # still match 'Degema' (no direction on the boundary side).
        _record("6", latitude="5.0", longitude="6.6", lga="Degema West"),
        # Likely duplicate of #1: same operator, ~100 m, next day.
        _record("7", latitude="5.0009", longitude="7.25", incidentdate="2018-06-02", lga="Okrika"),
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

    with connect() as conn:
        spills = {
            r["spill_id"]: dict(r)
            for r in conn.execute(
                """SELECT s.spill_id, s.geom_method, s.analysable, a.name AS lga
                   FROM clean.spills s LEFT JOIN ref.admin_areas a ON a.pcode = s.lga_pcode"""
            )
        }
        for r in conn.execute("SELECT spill_id, code, details FROM clean.spill_issues"):
            spills[r["spill_id"]].setdefault("issues", {})[r["code"]] = r["details"]
    return spills


def issues(spills: dict[str, dict[str, Any]], id: str) -> set[str]:
    return set(spills[id].get("issues", {}))


def test_reported_point_used_as_is(validated: dict[str, dict[str, Any]]) -> None:
    s = validated["1"]
    assert (s["geom_method"], s["lga"], s["analysable"]) == ("reported", "Okrika", True)


def test_grid_metres_reprojected_with_the_corroborated_crs(validated: dict[str, dict[str, Any]]) -> None:
    s = validated["2"]
    assert (s["geom_method"], s["lga"]) == ("reprojected", "Okrika")
    assert s["issues"]["COORD_REPROJECTED"]["srid"] == 26392


def test_uncorroborated_correction_is_not_applied(validated: dict[str, dict[str, Any]]) -> None:
    s = validated["3"]
    assert s["geom_method"] == "none"
    assert not s["analysable"]
    assert "COORD_UNRESOLVED" in issues(validated, "3")


def test_state_mismatch_is_a_warning_not_an_error(validated: dict[str, dict[str, Any]]) -> None:
    assert "COORD_STATE_MISMATCH" in issues(validated, "4")
    assert validated["4"]["analysable"]


def test_lga_mismatch(validated: dict[str, dict[str, Any]]) -> None:
    assert "COORD_LGA_MISMATCH" in issues(validated, "5")


def test_lga_name_with_extra_direction_still_matches_plain_name(validated: dict[str, dict[str, Any]]) -> None:
    assert "COORD_LGA_MISMATCH" not in issues(validated, "6")


def test_duplicate_points_back_to_earlier_report(validated: dict[str, dict[str, Any]]) -> None:
    assert validated["7"]["issues"]["LIKELY_DUPLICATE"]["duplicate_of"] == "1"
    assert "LIKELY_DUPLICATE" not in issues(validated, "1")


def test_not_a_spill_is_excluded(validated: dict[str, dict[str, Any]]) -> None:
    assert not validated["8"]["analysable"]


def test_out_of_window_records_are_dropped(validated: dict[str, dict[str, Any]]) -> None:
    assert "9" not in validated


def test_packed_dms(validated: dict[str, dict[str, Any]]) -> None:
    s = validated["10"]
    assert (s["geom_method"], s["lga"]) == ("dms", "Okrika")


def test_far_point_is_outside_nigeria(validated: dict[str, dict[str, Any]]) -> None:
    assert "COORD_OUTSIDE_NIGERIA" in issues(validated, "11")


def test_lga_name_similarity_function(database_url: str) -> None:
    with connect() as conn:
        rows = conn.execute(
            """SELECT a, b, ref.lga_name_similarity(a, b) AS s FROM (VALUES
                 ('Ukwa West', 'Ukwa East'), ('UKWA-WEST', 'Saki West'),
                 ('Ukwa West LGA', 'Ukwa West'), ('DEYEMA', 'Degema'),
                 ('Asari Toru', 'Akuku Toru')) v(a, b)"""
        ).fetchall()
    sims = {(r["a"], r["b"]): r["s"] for r in rows}
    assert sims[("Ukwa West", "Ukwa East")] == 0
    assert sims[("UKWA-WEST", "Saki West")] == 0
    assert sims[("Ukwa West LGA", "Ukwa West")] == 1
    assert sims[("DEYEMA", "Degema")] >= 0.4
    assert sims[("Asari Toru", "Akuku Toru")] < 0.4


def test_every_run_is_recorded(validated: dict[str, dict[str, Any]]) -> None:
    with connect() as conn:
        runs = conn.execute("SELECT stage, status FROM ops.pipeline_runs ORDER BY started_at").fetchall()
    assert [(r["stage"], r["status"]) for r in runs][-2:] == [
        ("ingest", "succeeded"),
        ("validate", "succeeded"),
    ]
