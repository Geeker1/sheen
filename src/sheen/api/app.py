import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

import structlog
from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from sheen.api import db
from sheen.api.loaders import make_loaders
from sheen.api.schema import schema
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
