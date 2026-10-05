import base64
import dataclasses
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import strawberry
from psycopg.rows import DictRow
from strawberry.scalars import JSON
from strawberry.types import Info

from sheen.api import db
from sheen.api.loaders import Loaders
from sheen.config import get_settings

MAX_PAGE = 200

SPILL_SELECT = """
    SELECT s.*, ST_Y(s.geom) AS lat, ST_X(s.geom) AS lon,
           cause.label AS cause_label, cont.label AS contaminant_label,
           ARRAY(SELECT coalesce(h.label, hc) FROM unnest(s.habitat_codes) hc
                 LEFT JOIN ref.codes h ON h.field = 'habitat' AND h.code = hc) AS habitat_labels
    FROM clean.spills s
    LEFT JOIN ref.codes cause ON cause.field = 'cause' AND cause.code = s.cause_code
    LEFT JOIN ref.codes cont ON cont.field = 'contaminant' AND cont.code = s.contaminant_code
"""


def _loaders(info: Info) -> Loaders:
    return info.context["loaders"]  # type: ignore[no-any-return]


def _float(v: Any) -> float | None:
    return None if v is None else float(v)


@strawberry.type
class Issue:
    code: str
    severity: str
    field: str | None
    message: str
    details: JSON

    @staticmethod
    def of(r: DictRow) -> "Issue":
        return Issue(
            code=r["code"],
            severity=r["severity"],
            field=r["field"],
            message=r["message"],
            details=r["details"],
        )


@strawberry.type
class Exposure:
    mangrove_year: int
    mangrove_ha_1km: float
    settlements_2km: int | None = strawberry.field(
        description="OSM places within 2 km. A lower bound: OSM village coverage in the Delta is incomplete."
    )
    nearest_settlement_m: float | None


@strawberry.type
class AdminArea:
    pcode: str
    name: str
    state_name: str | None


@strawberry.type
class Spill:
    id: strawberry.ID
    status: str | None
    operator: str | None
    incident_number: str | None
    incident_date: date | None
    cause_code: str | None
    cause_label: str | None
    cause_detail: str | None
    contaminant_code: str | None
    contaminant_label: str | None
    habitats: list[str]
    quantity_bbl: float | None
    state_code: str | None
    lga_reported: str | None = strawberry.field(description="LGA name as written in the report.")
    site_name: str | None
    jiv_date: date | None = strawberry.field(description="Date of the Joint Investigation Visit.")
    latitude: float | None
    longitude: float | None
    location_method: str = strawberry.field(
        description="reported | swapped | reprojected | decimal_shift | dms | none"
    )
    analysable: bool
    ruleset_version: str
    lga_pcode: strawberry.Private[str | None]

    @strawberry.field
    async def issues(self, info: Info) -> list[Issue]:
        return [Issue.of(r) for r in await _loaders(info).issues.load(str(self.id))]

    @strawberry.field
    async def exposure(self, info: Info) -> Exposure | None:
        r = await _loaders(info).exposure.load(str(self.id))
        if r is None:
            return None
        return Exposure(
            mangrove_year=r["mangrove_year"],
            mangrove_ha_1km=float(r["mangrove_ha_1km"]),
            settlements_2km=r["settlements_2km"],
            nearest_settlement_m=_float(r["nearest_settlement_m"]),
        )

    @strawberry.field(description="The LGA the point falls in (computed, not as reported).")
    async def lga(self, info: Info) -> AdminArea | None:
        if self.lga_pcode is None:
            return None
        r = await _loaders(info).areas.load(self.lga_pcode)
        return AdminArea(pcode=r["pcode"], name=r["name"], state_name=r["state_name"]) if r else None

    @staticmethod
    def of(r: DictRow) -> "Spill":
        return Spill(
            id=strawberry.ID(r["spill_id"]),
            status=r["status"],
            operator=r["operator"],
            incident_number=r["incident_number"],
            incident_date=r["incident_date"],
            cause_code=r["cause_code"],
            cause_label=r["cause_label"],
            cause_detail=r["cause_detail"],
            contaminant_code=r["contaminant_code"],
            contaminant_label=r["contaminant_label"],
            habitats=r["habitat_labels"],
            quantity_bbl=_float(r["quantity_bbl"]),
            state_code=r["state_code"],
            lga_reported=r["lga_reported"],
            site_name=r["site_name"],
            jiv_date=r["jiv_date"],
            latitude=r["lat"],
            longitude=r["lon"],
            location_method=r["geom_method"],
            analysable=r["analysable"],
            ruleset_version=r["ruleset_version"],
            lga_pcode=r["lga_pcode"],
        )


@strawberry.input
class SpillFilter:
    operator: str | None = None
    state_code: str | None = None
    lga_pcode: str | None = None
    cause_code: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    analysable: bool | None = None
    issue_code: str | None = strawberry.field(default=None, description="Only spills with this issue.")


@strawberry.type
class SpillPage:
    items: list[Spill]
    total_count: int
    end_cursor: str | None
    has_next_page: bool


@strawberry.type
class ExplainStep:
    step: str
    outcome: str


@strawberry.type
class Explanation:
    spill: Spill
    steps: list[ExplainStep]
    raw_record: JSON = strawberry.field(description="Exactly what NOSDRA published.")
    source_sha256: str | None
    fetched_at: datetime | None


@strawberry.type
class OperatorQuality:
    operator: str
    reports: int
    analysable: int
    share_unplaceable: float
    share_missing_quantity: float
    share_missing_cause: float
    share_missing_jiv: float
    share_sabotage_of_known_cause: float | None
    reported_bbl: float | None


@strawberry.type
class Summary:
    reports_in_window: int
    analysable: int
    reported_bbl: float
    window_start: date
    window_end: date


def _from_row[T](cls: type[T], r: DictRow) -> T:
    """Build a type from a view row, converting NUMERIC (Decimal) columns to float.

    Only constructor fields are read from the row; computed fields such as
    LgaSummary.mangrove_change_pct are resolved by Strawberry.
    """
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):  # type: ignore[arg-type]
        if not f.init:
            continue
        v = r[f.name]
        kwargs[f.name] = float(v) if isinstance(v, Decimal) else v
    return cls(**kwargs)


def _cursor(spill_id: str) -> str:
    return base64.urlsafe_b64encode(spill_id.encode()).decode()


def _uncursor(cursor: str) -> int:
    return int(base64.urlsafe_b64decode(cursor.encode()).decode())


def _where(f: SpillFilter | None) -> tuple[str, dict[str, Any]]:
    # The SQL pieces are fixed; values from the user are only passed as parameters.
    clauses, params = ["TRUE"], {}
    if f:
        for attr, clause in [
            ("operator", "s.operator = %(operator)s"),
            ("state_code", "s.state_code = %(state_code)s"),
            ("lga_pcode", "s.lga_pcode = %(lga_pcode)s"),
            ("cause_code", "s.cause_code = %(cause_code)s"),
            ("date_from", "s.incident_date >= %(date_from)s"),
            ("date_to", "s.incident_date <= %(date_to)s"),
            ("analysable", "s.analysable = %(analysable)s"),
            (
                "issue_code",
                "EXISTS (SELECT 1 FROM clean.spill_issues i "
                "WHERE i.spill_id = s.spill_id AND i.code = %(issue_code)s)",
            ),
        ]:
            value = getattr(f, attr)
            if value is not None:
                clauses.append(clause)
                params[attr] = value
    return " AND ".join(clauses), params


@strawberry.type
class Query:
    @strawberry.field
    async def spills(
        self, filter: SpillFilter | None = None, first: int = 50, after: str | None = None
    ) -> SpillPage:
        first = max(1, min(first, MAX_PAGE))
        where, params = _where(filter)
        total = await db.fetch_one(f"SELECT count(*) AS n FROM clean.spills s WHERE {where}", params)
        page_params = {**params, "limit": first + 1, "after": _uncursor(after) if after else -1}
        rows = await db.fetch(
            f"""{SPILL_SELECT} WHERE {where} AND s.spill_id::bigint > %(after)s
                ORDER BY s.spill_id::bigint LIMIT %(limit)s""",
            page_params,
        )
        has_next = len(rows) > first
        rows = rows[:first]
        return SpillPage(
            items=[Spill.of(r) for r in rows],
            total_count=total["n"] if total else 0,
            end_cursor=_cursor(rows[-1]["spill_id"]) if rows else None,
            has_next_page=has_next,
        )

    @strawberry.field
    async def spill(self, id: strawberry.ID) -> Spill | None:
        r = await db.fetch_one(f"{SPILL_SELECT} WHERE s.spill_id = %s", (str(id),))
        return Spill.of(r) if r else None

    @strawberry.field(description="Every step taken with one report, from what was published to the result.")
    async def explain_spill(self, info: Info, id: strawberry.ID) -> Explanation | None:
        r = await db.fetch_one(f"{SPILL_SELECT} WHERE s.spill_id = %s", (str(id),))
        if r is None:
            return None
        src = await db.fetch_one(
            """SELECT raw.payload, run.source_sha256, run.started_at
               FROM raw.spill_reports raw JOIN ops.pipeline_runs run ON run.run_id = raw.run_id
               WHERE raw.run_id = %s AND raw.source_id = %s""",
            (r["raw_run_id"], r["spill_id"]),
        )
        spill = Spill.of(r)
        issues = await _loaders(info).issues.load(r["spill_id"])
        exposure = await _loaders(info).exposure.load(r["spill_id"])
        area = await _loaders(info).areas.load(r["lga_pcode"]) if r["lga_pcode"] else None
        return Explanation(
            spill=spill,
            steps=_explain_steps(r, issues, exposure, area),
            raw_record=src["payload"] if src else None,
            source_sha256=src["source_sha256"] if src else None,
            fetched_at=src["started_at"] if src else None,
        )

    @strawberry.field
    async def operators(self, min_reports: int = 20) -> list[OperatorQuality]:
        rows = await db.fetch(
            "SELECT * FROM analysis.operator_quality WHERE reports >= %s ORDER BY reports DESC",
            (min_reports,),
        )
        return [_from_row(OperatorQuality, r) for r in rows]

    @strawberry.field
    async def summary(self) -> Summary:
        r = await db.fetch_one(
            """SELECT count(*) AS n, count(*) FILTER (WHERE analysable) AS a,
                      coalesce(sum(quantity_bbl) FILTER (WHERE analysable), 0) AS bbl
               FROM clean.spills"""
        )
        s = get_settings()
        return Summary(
            reports_in_window=r["n"] if r else 0,
            analysable=r["a"] if r else 0,
            reported_bbl=float(r["bbl"]) if r else 0.0,
            window_start=s.window_start,
            window_end=s.window_end,
        )


def _explain_steps(
    r: DictRow, issues: list[DictRow], exposure: DictRow | None, area: DictRow | None
) -> list[ExplainStep]:
    by_code = {i["code"]: i for i in issues}
    steps = [
        ExplainStep(
            step="source",
            outcome=f"NOSDRA report {r['spill_id']}, checked with rules {r['ruleset_version']}",
        )
    ]

    method = r["geom_method"]
    if method == "none":
        reason = next(
            (
                by_code[c]["message"]
                for c in (
                    "COORD_MISSING",
                    "COORD_PARTIAL",
                    "COORD_INVALID",
                    "COORD_UNRESOLVED",
                    "COORD_OUTSIDE_NIGERIA",
                )
                if c in by_code
            ),
            "no usable coordinates",
        )
        steps.append(ExplainStep(step="location", outcome=f"Not placed: {reason}"))
    elif method == "reported":
        steps.append(ExplainStep(step="location", outcome="Reported coordinates used as-is"))
    else:
        code = {
            "reprojected": "COORD_REPROJECTED",
            "decimal_shift": "COORD_DECIMAL_SHIFTED",
            "swapped": "COORD_SWAPPED",
            "dms": "COORD_DMS_PARSED",
        }.get(method)
        outcome = by_code[code]["message"] if code in by_code else f"Location method: {method}"
        steps.append(ExplainStep(step="location", outcome=outcome))

    if area:
        steps.append(ExplainStep(step="area", outcome=f"Falls in {area['name']} LGA, {area['state_name']}"))
    elif method != "none":
        steps.append(ExplainStep(step="area", outcome="Offshore: not inside any LGA"))
    for code in ("COORD_STATE_MISMATCH", "COORD_LGA_MISMATCH", "HABITAT_MISMATCH"):
        if code in by_code:
            steps.append(ExplainStep(step="consistency", outcome=by_code[code]["message"]))

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    if r["analysable"]:
        steps.append(ExplainStep(step="analysis", outcome=f"Included ({len(warnings)} warning(s))"))
    else:
        why = ", ".join(i["code"] for i in errors) or "no location"
        steps.append(ExplainStep(step="analysis", outcome=f"Excluded: {why}"))
    if exposure:
        ha = float(exposure["mangrove_ha_1km"])
        steps.append(
            ExplainStep(
                step="exposure",
                outcome=f"{ha:.1f} ha of mangrove within 1 km (GMW {exposure['mangrove_year']})",
            )
        )
    return steps


schema = strawberry.Schema(query=Query)
