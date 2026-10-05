import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Literal

import structlog
from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from sheen.api import db
from sheen.api.loaders import make_loaders
from sheen.api.schema import schema
from sheen.config import get_settings
from sheen.logging import configure_logging

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await db.open_pool()
    yield
    await db.close_pool()


app = FastAPI(title="Sheen", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


@app.middleware("http")
async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    structlog.contextvars.bind_contextvars(request_id=request_id)
    t0 = time.monotonic()
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.unbind_contextvars("request_id")
    response.headers["x-request-id"] = request_id
    if request.url.path != "/healthz":
        log.info(
            "http.request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.monotonic() - t0) * 1000, 1),
        )
    return response


async def _context() -> dict[str, Any]:
    return {"loaders": make_loaders()}


app.include_router(GraphQLRouter(schema, context_getter=_context), prefix="/graphql")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    await db.fetch_one("SELECT 1")
    return {"status": "ok"}


def _geojson(rows: list[Any]) -> Response:
    # Geometry is already GeoJSON text from PostGIS; splice it in rather than
    # parsing and re-serialising thousands of coordinates.
    features = ",".join(
        '{"type":"Feature","geometry":'
        + r["geometry"]
        + ',"properties":'
        + json.dumps(r["properties"], default=str)
        + "}"
        for r in rows
    )
    return Response(
        f'{{"type":"FeatureCollection","features":[{features}]}}', media_type="application/geo+json"
    )


@app.get("/geojson/spills")
async def spills_geojson(
    state_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_flagged: bool = Query(True, description="Include analysable spills that have warnings."),
) -> Response:
    """Analysable spills as points, for the map. Geometry built by PostGIS."""
    rows = await db.fetch(
        """SELECT ST_AsGeoJSON(s.geom, 5) AS geometry,
                  jsonb_build_object(
                      'id', s.spill_id, 'operator', s.operator, 'date', s.incident_date,
                      'cause', s.cause_code, 'bbl', s.quantity_bbl, 'method', s.geom_method,
                      'warnings', (SELECT count(*) FROM clean.spill_issues i
                                   WHERE i.spill_id = s.spill_id AND i.severity = 'warning'),
                      'mangrove_ha_1km', round(e.mangrove_ha_1km, 1)) AS properties
           FROM clean.spills s LEFT JOIN analysis.spill_exposure e USING (spill_id)
           WHERE s.analysable
             AND (%(state)s::text IS NULL OR s.state_code = %(state)s)
             AND (%(from)s::date IS NULL OR s.incident_date >= %(from)s)
             AND (%(to)s::date IS NULL OR s.incident_date <= %(to)s)
             AND (%(flagged)s OR NOT EXISTS (SELECT 1 FROM clean.spill_issues i
                                             WHERE i.spill_id = s.spill_id AND i.severity = 'warning'))""",
        {"state": state_code, "from": date_from, "to": date_to, "flagged": include_flagged},
    )
    return _geojson(rows)


@app.get("/geojson/lgas")
async def lgas_geojson(state_code: str | None = None) -> Response:
    """LGA polygons (simplified) with their summary numbers, for the choropleth."""
    rows = await db.fetch(
        """SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.002), 4) AS geometry,
                  jsonb_build_object('pcode', pcode, 'name', name, 'state', state,
                                     'spills', spills, 'reported_bbl', reported_bbl,
                                     'mangrove_ha_2007', mangrove_ha_2007,
                                     'mangrove_ha_2020', mangrove_ha_2020) AS properties
           FROM analysis.lga_summary
           WHERE (%(state)s::text IS NULL OR state_code = %(state)s)
             AND (spills > 0 OR mangrove_ha_2020 > 0)""",
        {"state": state_code},
    )
    return _geojson(rows)


TREND_NOTE = (
    "Counts are usable spill reports in the NOSDRA register, not every spill that happened, "
    "and reporting practice has changed over time. Volumes are what operators reported; "
    "compare reported_bbl with spills_with_volume before reading much into it."
)


@app.get("/trends")
async def trends(
    lga: str | None = Query(None, description="One or more LGA names or P-codes, comma separated."),
    state: str | None = Query(None, description="Two-letter NOSDRA state code, e.g. RI."),
    operator: str | None = None,
    by: Literal["year", "month"] = "year",
) -> dict[str, Any]:
    """Spills over time for an area or operator, with zero-filled periods."""
    s = get_settings()
    wanted = [x.strip() for x in lga.split(",") if x.strip()] if lga else []
    matched: list[str] = []
    if wanted:
        rows = await db.fetch(
            """SELECT pcode, name FROM ref.admin_areas
               WHERE level = 2 AND (lower(name) = ANY(%(names)s) OR pcode = ANY(%(raw)s))""",
            {"names": [w.lower() for w in wanted], "raw": wanted},
        )
        matched = [r["pcode"] for r in rows]
        found = {r["name"].lower() for r in rows} | {r["pcode"] for r in rows}
        unmatched = [w for w in wanted if w.lower() not in found and w not in found]
    else:
        unmatched = []

    series = await db.fetch(
        """
        WITH area AS (
            SELECT s.* FROM clean.spills s
            LEFT JOIN ref.admin_areas l ON l.pcode = s.lga_pcode
            WHERE s.analysable
              AND (NOT %(filter_lga)s OR s.lga_pcode = ANY(%(pcodes)s))
              AND (%(state)s::text IS NULL OR l.state_code = %(state)s)
              AND (%(operator)s::text IS NULL OR s.operator ILIKE %(operator)s)
        ),
        periods AS (
            SELECT generate_series(date_trunc(%(by)s, %(start)s::date), date_trunc(%(by)s, %(end)s::date),
                                   ('1 ' || %(by)s)::interval)::date AS p
        )
        SELECT to_char(p.p, CASE %(by)s WHEN 'year' THEN 'YYYY' ELSE 'YYYY-MM' END) AS period,
               count(a.spill_id) AS spills,
               count(a.quantity_bbl) AS spills_with_volume,
               coalesce(round(sum(a.quantity_bbl), 1), 0) AS reported_bbl,
               count(*) FILTER (WHERE a.cause_code = 'sab') AS sabotage,
               count(*) FILTER (WHERE a.cause_code IN ('eqf', 'cor', 'ome')) AS operational,
               round(avg(count(a.spill_id)) OVER (ORDER BY p.p ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1)
                   AS spills_rolling_avg_3
        FROM periods p LEFT JOIN area a ON date_trunc(%(by)s, a.incident_date)::date = p.p
        GROUP BY p.p ORDER BY p.p
        """,
        {
            "filter_lga": bool(wanted),
            "pcodes": matched,
            "state": state.upper() if state else None,
            "operator": operator,
            "by": by,
            "start": s.window_start,
            "end": s.window_end,
        },
    )
    points = [
        {k: (float(v) if k in ("reported_bbl", "spills_rolling_avg_3") else v) for k, v in r.items()}
        for r in series
    ]
    if points:
        points[-1]["partial"] = True  # the current year or month isn't over
    return {
        "filter": {"lga": wanted or None, "state": state, "operator": operator, "by": by},
        "unmatched_lgas": unmatched,
        "window": {"start": s.window_start, "end": s.window_end},
        "total_spills": sum(p["spills"] for p in points),
        "note": TREND_NOTE,
        "series": points,
    }
