"""Per-record parsing and checks. Pure functions, no database.

For coordinates this doesn't pick a fix: it returns every plausible reading
as a CoordCandidate, and the PostGIS steps choose between them.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sheen.validation import issues as iss
from sheen.validation.issues import Issue
from sheen.validation.rules import Ruleset

# Nigeria's land area sits inside this box; offshore fields extend to ~3N.
LAT_RANGE = (2.0, 14.5)
LON_RANGE = (2.0, 15.0)

KNOWN_CAUSES = {"sab", "eqf", "cor", "ome", "ytd", "mys"}
STATE_ALIASES = {"FCT": "FC"}


@dataclass(frozen=True)
class CoordCandidate:
    method: str  # reported | swapped | reprojected | decimal_shift | dms
    x: float  # longitude, or easting when srid is projected
    y: float
    srid: int = 4326


@dataclass
class NormalizedSpill:
    spill_id: str
    status: str | None
    operator: str | None
    incident_number: str | None
    incident_date: date | None
    cause_code: str | None
    cause_detail: str | None
    contaminant_code: str | None
    habitat_codes: list[str]
    quantity_bbl: Decimal | None
    state_code: str | None
    lga_reported: str | None
    site_name: str | None
    jiv_date: date | None
    coord_candidates: list[CoordCandidate]
    in_window: bool
    issues: list[Issue] = field(default_factory=list)


def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _parse_date(v: Any) -> date | None:
    """Returns None for empty input; raises ValueError for garbage."""
    s = _text(v)
    if s is None:
        return None
    return date.fromisoformat(s[:10])


def _float(v: Any) -> float | None:
    s = _text(v)
    if s is None:
        return None
    try:
        f = float(s)
    except ValueError:
        return math.nan
    return f


def parse_dates(raw: dict[str, Any], rules: Ruleset) -> tuple[date | None, date | None, list[Issue]]:
    out: list[Issue] = []
    try:
        incident = _parse_date(raw.get("incidentdate"))
    except ValueError:
        out.append(
            iss.make("DATE_UNPARSEABLE", f"Couldn't parse {raw.get('incidentdate')!r}", "incidentdate")
        )
        incident = None
    else:
        if incident is None:
            out.append(iss.make("DATE_MISSING", "No incident date", "incidentdate"))
        elif incident < rules.dates.earliest_plausible:
            out.append(
                iss.make(
                    "DATE_IMPLAUSIBLE", f"Incident dated {incident}", "incidentdate", value=str(incident)
                )
            )

    try:
        jiv = _parse_date(raw.get("jivdate"))
    except ValueError:
        jiv = None
    if incident and jiv and jiv < incident:
        out.append(
            iss.make(
                "JIV_BEFORE_INCIDENT",
                f"JIV on {jiv}, incident on {incident}",
                "jivdate",
                jiv_date=str(jiv),
                incident_date=str(incident),
            )
        )
    return incident, jiv, out


def parse_quantity(raw: dict[str, Any], rules: Ruleset) -> tuple[Decimal | None, list[Issue]]:
    s = _text(raw.get("estimatedquantity"))
    if s is None:
        return None, [iss.make("QUANTITY_MISSING", "No estimated quantity", "estimatedquantity")]
    try:
        q = Decimal(s.replace(",", ""))
    except InvalidOperation:
        q = Decimal("NaN")
    if not q.is_finite():
        return None, [iss.make("QUANTITY_UNPARSEABLE", f"Couldn't parse {s!r}", "estimatedquantity", value=s)]
    if q < 0:
        return None, [iss.make("QUANTITY_NEGATIVE", f"Quantity {q} bbl", "estimatedquantity", value=str(q))]
    if q > rules.quantity.max_plausible_bbl:
        return q, [
            iss.make(
                "QUANTITY_IMPLAUSIBLE",
                f"{q} bbl exceeds {rules.quantity.max_plausible_bbl:g} bbl",
                "estimatedquantity",
                value=str(q),
            )
        ]
    return q, []


def parse_cause(raw: dict[str, Any]) -> tuple[str | None, str | None, list[Issue]]:
    """'sab' -> ('sab', None); 'other: mys' -> ('mys', None); 'other:Blast' -> ('other', 'Blast')."""
    s = _text(raw.get("cause"))
    if s is None:
        return None, None, [iss.make("CAUSE_MISSING", "No cause recorded", "cause")]
    code, _, detail = s.partition(":")
    code, detail = code.strip().lower(), detail.strip()
    if code == "other":
        if detail.lower() in KNOWN_CAUSES:
            return detail.lower(), None, []
        return "other", detail or None, []
    if code not in KNOWN_CAUSES:
        return (
            code,
            detail or None,
            [iss.make("CAUSE_UNKNOWN_CODE", f"Unknown cause {s!r}", "cause", value=s)],
        )
    return code, detail or None, []


def parse_contaminant(raw: dict[str, Any]) -> str | None:
    """'cr' -> 'cr'; 're(PMS)' -> 're'; 'other:(oily water)' -> 'other'; 'CON' -> 'con'."""
    s = _text(raw.get("contaminant"))
    if s is None:
        return None
    m = re.match(r"[a-zA-Z]+", s)
    return m.group(0).lower() if m else None


def parse_habitats(raw: dict[str, Any]) -> list[str]:
    s = _text(raw.get("spillareahabitat"))
    if s is None:
        return []
    return sorted({h.strip().lower() for h in s.split(",") if h.strip()})


def parse_state(raw: dict[str, Any], states: dict[str, str]) -> tuple[str | None, list[Issue]]:
    """Map NOSDRA's free-form state field to a two-letter code.

    Seen in the wild: 'RI', 'FCT', 'KADUNA', 'KADUNA-NORTH', 'C R O S S  R I V E R',
    'RI,IM', 'RI,undefined', 'N/A', and city names like 'GUSAU'.
    """
    s = _text(raw.get("statesaffected"))
    if s is None:
        return None, []
    by_name = {re.sub(r"[^A-Z]", "", n.upper()): c for c, n in states.items()}
    found: list[str] = []
    for token in s.split(","):
        t = token.strip().upper()
        t = STATE_ALIASES.get(t, t)
        squashed = re.sub(r"[^A-Z]", "", t)
        code = (
            t
            if t in states
            else by_name.get(squashed)
            or next((c for n, c in by_name.items() if squashed.startswith(n)), None)
        )
        if code and code not in found:
            found.append(code)

    out: list[Issue] = []
    if not found:
        if s.upper() not in {"N/A", "UNDEFINED"}:
            out.append(
                iss.make("STATE_UNRECOGNISED", f"Couldn't match state {s!r}", "statesaffected", value=s)
            )
        return None, out
    if len(found) > 1:
        out.append(
            iss.make(
                "STATE_MULTIPLE",
                f"Lists {', '.join(found)}; using {found[0]}",
                "statesaffected",
                states=found,
            )
        )
    return found[0], out


def _packed_dms(s: str, degree_digits: int) -> float | None:
    """Parse degrees-minutes-seconds written without separators.

    '050122.6' -> 5 deg 01' 22.6"; '04505482' -> 4 deg 50' 54.82" (two implied
    decimals). Only zero-padded values qualify, which separates them from
    plain degrees or grid metres.
    """
    if not re.fullmatch(r"0\d{5,}(\.\d+)?", s):
        return None
    whole, _, frac = s.partition(".")
    if len(whole) < degree_digits + 4:
        return None
    deg, mins = int(whole[:degree_digits]), int(whole[degree_digits : degree_digits + 2])
    sec_digits = whole[degree_digits + 2 :]
    secs = float(f"{sec_digits[:2]}.{sec_digits[2:]}{frac}")
    if mins >= 60 or secs >= 60:
        return None
    return deg + mins / 60 + secs / 3600


def coordinate_candidates(raw: dict[str, Any], rules: Ruleset) -> tuple[list[CoordCandidate], list[Issue]]:
    lat_s, lon_s = _text(raw.get("latitude")), _text(raw.get("longitude"))
    if lat_s is None and lon_s is None:
        return [], [iss.make("COORD_MISSING", "No coordinates", "latitude/longitude")]
    if lat_s is None or lon_s is None:
        return [], [iss.make("COORD_PARTIAL", f"lat={lat_s!r} lon={lon_s!r}", "latitude/longitude")]

    lat, lon = _float(lat_s), _float(lon_s)
    assert lat is not None and lon is not None
    if math.isnan(lat) or math.isnan(lon) or (lat == 0 and lon == 0):
        return [], [iss.make("COORD_INVALID", f"lat={lat_s!r} lon={lon_s!r}", "latitude/longitude")]

    def in_box(y: float, x: float) -> bool:
        return LAT_RANGE[0] <= y <= LAT_RANGE[1] and LON_RANGE[0] <= x <= LON_RANGE[1]

    dms = _packed_dms(lat_s, 2), _packed_dms(lon_s, 3)
    if dms[0] is not None and dms[1] is not None:
        return [CoordCandidate("dms", dms[1], dms[0])], []

    if abs(lat) > 1000 and abs(lon) > 1000:
        # Metres on a projected grid. Try each candidate CRS, both axis orders.
        return [
            CoordCandidate("reprojected", x, y, srid)
            for srid in rules.coordinates.projected_candidate_srids
            for x, y in ((lon, lat), (lat, lon))
        ], []

    cands: list[CoordCandidate] = []
    if in_box(lat, lon):
        cands.append(CoordCandidate("reported", lon, lat))
    if in_box(lon, lat):
        cands.append(CoordCandidate("swapped", lat, lon))
    if not cands:
        # e.g. 50.385, 60.693 -> 5.0385, 6.0693: a decimal point in the wrong place.
        for y, x in ((lat / 10, lon / 10), (lat / 10, lon), (lat, lon / 10)):
            if in_box(y, x):
                cands.append(CoordCandidate("decimal_shift", x, y))
    if not cands:
        # Nowhere near Nigeria; keep it so the issue can say where it is.
        cands.append(CoordCandidate("reported", lon, lat))
    return cands, []


def normalize(
    raw: dict[str, Any], rules: Ruleset, states: dict[str, str], window: tuple[date, date]
) -> NormalizedSpill:
    found: list[Issue] = []

    status = _text(raw.get("status"))
    if status == "invalid":
        found.append(iss.make("STATUS_INVALID", "NOSDRA status is 'invalid'", "status"))

    contaminant = parse_contaminant(raw)
    if contaminant == "no":
        found.append(iss.make("NOT_A_SPILL", "Contaminant recorded as 'no spill'", "contaminant"))

    operator = _text(raw.get("company"))
    if operator is None:
        found.append(iss.make("OPERATOR_MISSING", "No operator recorded", "company"))

    incident, jiv, i = parse_dates(raw, rules)
    found += i
    quantity, i = parse_quantity(raw, rules)
    found += i
    cause, cause_detail, i = parse_cause(raw)
    found += i
    state, i = parse_state(raw, states)
    found += i
    cands, i = coordinate_candidates(raw, rules)
    found += i

    # Bad dates stay in (with an error) so data-quality stats stay complete.
    in_window = (
        incident is None or incident < rules.dates.earliest_plausible or window[0] <= incident <= window[1]
    )

    return NormalizedSpill(
        spill_id=str(raw["id"]),
        status=status,
        operator=operator,
        incident_number=_text(raw.get("incidentnumber")),
        incident_date=incident,
        cause_code=cause,
        cause_detail=cause_detail,
        contaminant_code=contaminant,
        habitat_codes=parse_habitats(raw),
        quantity_bbl=quantity,
        state_code=state,
        lga_reported=_text(raw.get("lga")),
        site_name=_text(raw.get("sitelocationname")),
        jiv_date=jiv,
        coord_candidates=cands,
        in_window=in_window,
        issues=found,
    )
