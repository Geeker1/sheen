"""End-to-end validation against PostGIS with a tiny synthetic geography.

Two square "states" side by side, Rivers split into two LGAs:

    5.5N +-----------+-----------+-----------+
         |  Bayelsa  |  Degema   |  Okrika   |
         |  (BY)     |  (RI)     |  (RI)     |
    4.5N +-----------+-----------+-----------+
         5.5E        6.5E        7.0E        7.5E
"""

from pathlib import Path
from typing import Any

import pytest

from sheen.db import connect

pytestmark = pytest.mark.db


def issues(spills: dict[str, dict[str, Any]], id: str) -> set[str]:
    return set(spills[id].get("issues", {}))


def test_reported_point_used_as_is(validated: dict[str, dict[str, Any]]) -> None:
    s = validated["1"]
    assert (s["geom_method"], s["lga"], s["analysable"]) == ("reported", "Okrika", True)


def test_grid_coordinates_use_the_grid_that_matches_the_report(validated: dict[str, dict[str, Any]]) -> None:
    s = validated["2"]
    assert (s["geom_method"], s["lga"]) == ("reprojected", "Okrika")
    assert s["issues"]["COORD_REPROJECTED"][0]["srid"] == 26392


def test_fix_that_disagrees_with_the_report_is_not_used(validated: dict[str, dict[str, Any]]) -> None:
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
    assert [d["duplicate_of"] for d in validated["7"]["issues"]["LIKELY_DUPLICATE"]] == ["1"]
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
        runs = {
            (r["stage"], r["status"]) for r in conn.execute("SELECT stage, status FROM ops.pipeline_runs")
        }
    assert {("ingest", "succeeded"), ("validate", "succeeded")} <= runs


def test_unchanged_download_is_skipped(validated: dict[str, dict[str, Any]], snapshot: Path) -> None:
    from sheen.ingest import nosdra

    assert nosdra.ingest(snapshot) is None  # same file as the fixture loaded
    assert nosdra.ingest(snapshot, force=True) is not None
    with connect() as conn:
        statuses = [
            r["status"]
            for r in conn.execute(
                "SELECT status FROM ops.pipeline_runs WHERE stage = 'ingest' ORDER BY started_at DESC LIMIT 2"
            )
        ]
    assert statuses == ["succeeded", "skipped"]


def test_mangrove_figures_are_only_worked_out_once(validated: dict[str, dict[str, Any]]) -> None:
    from sheen.analysis import exposure

    def saved() -> int:
        with connect() as conn:
            row = conn.execute("SELECT count(*) AS n FROM analysis.point_mangroves").fetchone()
        return row["n"] if row else 0

    exposure.analyse()
    first = saved()
    exposure.analyse()
    assert first > 0
    assert saved() == first
