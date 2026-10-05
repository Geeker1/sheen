"""Record-level checks. No database needed: normalize() is pure."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from sheen.validation import rules as rules_mod
from sheen.validation.normalize import CoordCandidate, normalize

RULES = rules_mod.load(Path("rules/v1.yaml"))
STATES = {"RI": "Rivers", "BY": "Bayelsa", "KD": "Kaduna", "CR": "Cross River", "FC": "FCT"}
WINDOW = (date(2005, 1, 1), date(2026, 10, 5))

BASE = {
    "id": "1",
    "status": "confirmed",
    "company": "SPDC",
    "incidentdate": "2019-03-04",
    "contaminant": "cr",
    "estimatedquantity": "12.5",
    "cause": "eqf",
    "spillareahabitat": "la",
    "statesaffected": "RI",
    "latitude": "4.75",
    "longitude": "7.00",
}


def run(**overrides: Any):  # type: ignore[no-untyped-def]
    return normalize({**BASE, **overrides}, RULES, STATES, WINDOW)


def codes(**overrides: Any) -> set[str]:
    return {i.code for i in run(**overrides).issues}


def test_clean_record_has_no_issues() -> None:
    n = run()
    assert n.issues == []
    assert n.quantity_bbl == Decimal("12.5")
    # The swapped reading also falls inside the box, so it's offered too.
    # PostGIS keeps the reported point whenever it makes sense.
    assert n.coord_candidates[0] == CoordCandidate("reported", 7.0, 4.75)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("contaminant", "no", "NOT_A_SPILL"),
        ("status", "invalid", "STATUS_INVALID"),
        ("incidentdate", None, "DATE_MISSING"),
        ("incidentdate", "2019-13-40", "DATE_UNPARSEABLE"),
        ("incidentdate", "1902-05-01", "DATE_IMPLAUSIBLE"),
        ("estimatedquantity", None, "QUANTITY_MISSING"),
        ("estimatedquantity", "about 20", "QUANTITY_UNPARSEABLE"),
        ("estimatedquantity", "-3", "QUANTITY_NEGATIVE"),
        ("estimatedquantity", "900000", "QUANTITY_IMPLAUSIBLE"),
        ("cause", None, "CAUSE_MISSING"),
        ("cause", "xyz", "CAUSE_UNKNOWN_CODE"),
        ("company", None, "OPERATOR_MISSING"),
        ("latitude", None, "COORD_PARTIAL"),
        ("latitude", "NaN", "COORD_INVALID"),
    ],
)
def test_single_field_issues(field: str, value: Any, code: str) -> None:
    assert code in codes(**{field: value})


def test_missing_both_coordinates() -> None:
    assert codes(latitude=None, longitude=None) == {"COORD_MISSING"}


def test_zero_zero_is_invalid_not_a_location() -> None:
    assert "COORD_INVALID" in codes(latitude="0.0000000", longitude="0.0000000")


def test_jiv_before_incident() -> None:
    assert "JIV_BEFORE_INCIDENT" in codes(incidentdate="2019-03-04", jivdate="2019-03-01")


def test_quantity_with_thousands_separator() -> None:
    assert run(estimatedquantity="1,250").quantity_bbl == Decimal("1250")


@pytest.mark.parametrize(
    ("raw", "code", "detail"),
    [
        ("sab", "sab", None),
        ("other: mys", "mys", None),
        ("other: BLAST", "other", "BLAST"),
        ("other:", "other", None),
    ],
)
def test_cause_parsing(raw: str, code: str, detail: str | None) -> None:
    n = run(cause=raw)
    assert (n.cause_code, n.cause_detail) == (code, detail)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("cr", "cr"), ("re(PMS)", "re"), ("other:(oily water)", "other"), ("CON", "con")],
)
def test_contaminant_parsing(raw: str, expected: str) -> None:
    assert run(contaminant=raw).contaminant_code == expected


@pytest.mark.parametrize(
    ("raw", "code", "issue"),
    [
        ("RI", "RI", None),
        ("FCT", "FC", None),
        ("KADUNA", "KD", None),
        ("KADUNA-NORTH", "KD", None),
        ("C R O S S  R I V E R", "CR", None),
        ("RI,undefined", "RI", None),
        ("RI,BY", "RI", "STATE_MULTIPLE"),
        ("RI,RI", "RI", None),
        ("GUSAU", None, "STATE_UNRECOGNISED"),  # a city, not a state
        ("N/A", None, None),
    ],
)
def test_state_normalisation(raw: str, code: str | None, issue: str | None) -> None:
    n = run(statesaffected=raw)
    assert n.state_code == code
    state_issues = {i.code for i in n.issues if i.field == "statesaffected"}
    assert state_issues == ({issue} if issue else set())


def test_habitats_are_split_and_deduplicated() -> None:
    assert run(spillareahabitat="la,SW,la").habitat_codes == ["la", "sw"]


class TestCoordinateCandidates:
    def test_projected_metres_try_every_crs_and_axis_order(self) -> None:
        n = run(latitude="68449.17", longitude="511781.05")
        assert {c.method for c in n.coord_candidates} == {"reprojected"}
        assert len(n.coord_candidates) == len(RULES.coordinates.projected_candidate_srids) * 2
        assert CoordCandidate("reprojected", 511781.05, 68449.17, 26392) in n.coord_candidates

    def test_misplaced_decimal_point(self) -> None:
        n = run(latitude="50.3850000", longitude="60.6933333")
        assert n.coord_candidates == [CoordCandidate("decimal_shift", 6.06933333, 5.0385)]

    def test_swap_is_offered_alongside_reported_when_both_fit(self) -> None:
        # 3.9N 6.8E is a real offshore location; the swapped reading is also
        # inside the box. Both go to PostGIS, which prefers the reported one.
        n = run(latitude="3.8991667", longitude="6.7916944")
        methods = [c.method for c in n.coord_candidates]
        assert methods == ["reported", "swapped"]

    @pytest.mark.parametrize(
        ("lat", "lon", "expected"),
        [
            ("04505482", "006281269", (4.848561, 6.470192)),  # DDMMSSss, two implied decimals
            ("050122.6", "0063326.8", (5.022944, 6.557444)),  # DDMMSS.s
        ],
    )
    def test_packed_degrees_minutes_seconds(self, lat: str, lon: str, expected: tuple[float, float]) -> None:
        (c,) = run(latitude=lat, longitude=lon).coord_candidates
        assert c.method == "dms"
        assert (round(c.y, 6), round(c.x, 6)) == expected

    def test_dms_requires_valid_minutes_and_seconds(self) -> None:
        # 75 minutes isn't valid, so it's treated as grid coordinates instead.
        methods = {c.method for c in run(latitude="04755482", longitude="006281269").coord_candidates}
        assert "dms" not in methods

    def test_far_away_degrees_are_kept_for_reporting(self) -> None:
        n = run(latitude="20.3783", longitude="16.8817")
        assert n.coord_candidates == [CoordCandidate("reported", 16.8817, 20.3783)]


class TestAnalysisWindow:
    def test_inside(self) -> None:
        assert run(incidentdate="2026-10-05").in_window

    def test_future_date_is_an_error_not_dropped(self) -> None:
        n = run(incidentdate="2099-01-01")
        assert n.in_window
        assert "DATE_IMPLAUSIBLE" in {i.code for i in n.issues}

    def test_before_window_is_excluded(self) -> None:
        assert not run(incidentdate="2004-06-01").in_window

    def test_bad_dates_stay_in_so_quality_stats_are_complete(self) -> None:
        assert run(incidentdate=None).in_window
        assert run(incidentdate="1902-01-01").in_window
