"""Validate the latest raw snapshot into clean.spills and clean.spill_issues.

Runs as one transaction, so readers never see a half-validated table.
"""

import time
import uuid
from typing import Any

import structlog
from psycopg.types.json import Jsonb

from sheen.config import get_settings
from sheen.db import connect
from sheen.runs import latest_successful, pipeline_run
from sheen.validation import rules as rules_mod
from sheen.validation import spatial
from sheen.validation.normalize import NormalizedSpill, normalize

log = structlog.get_logger()


def validate() -> str:
    s = get_settings()
    rules = rules_mod.load(s.ruleset_path)
    raw_run_id = latest_successful("ingest")
    if raw_run_id is None:
        raise RuntimeError("No successful ingest; run `sheen ingest spills` first")

    with pipeline_run("validate", ruleset_version=rules.version, parent_run_id=raw_run_id) as run:
        with connect() as conn:
            states = {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM ref.states")}
            raws = conn.execute(
                "SELECT payload FROM raw.spill_reports WHERE run_id = %s", (raw_run_id,)
            ).fetchall()
        run.rows_in = len(raws)

        spills: list[NormalizedSpill] = []
        out_of_window = 0
        for r in raws:
            n = normalize(r["payload"], rules, states, (s.window_start, s.window_end))
            if n.in_window:
                spills.append(n)
            else:
                out_of_window += 1

        with connect() as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE clean.spills CASCADE")
            _write_spills(cur, spills, run.run_id, raw_run_id, rules.version)

            params = {
                "offshore_max_lat": rules.coordinates.offshore_max_latitude,
                "offshore_max_m": rules.coordinates.offshore_max_distance_km * 1000,
                "offshore_min_lon": rules.coordinates.offshore_lon_range[0],
                "offshore_max_lon": rules.coordinates.offshore_lon_range[1],
                "state_tolerance_m": rules.state_match.border_tolerance_m,
                "lga_min_similarity": rules.lga_match.min_similarity,
                "lga_tie_break_m": rules.lga_match.tie_break_km * 1000,
                "reused_min": rules.coordinates.reused_min_incidents,
                "dup_radius_m": rules.duplicates.radius_m,
                "dup_window_days": rules.duplicates.window_days,
            }
            timings: dict[str, float] = {}
            for name, sql in spatial.STEPS:
                t0 = time.monotonic()
                cur.execute(sql, params)
                timings[name] = round(time.monotonic() - t0, 2)
                log.info("validate.step", step=name, rows=cur.rowcount, duration_s=timings[name])
            # The steps changed geom and analysable; refresh stats for the analyse stage.
            cur.execute("ANALYZE clean.spills")

            counts = cur.execute(
                "SELECT code, count(*) AS n FROM clean.spill_issues GROUP BY code ORDER BY n DESC"
            ).fetchall()
            analysable = cur.execute(
                "SELECT count(*) FILTER (WHERE analysable) AS n FROM clean.spills"
            ).fetchone()

        run.rows_out = len(spills)
        run.details.update(
            out_of_window=out_of_window,
            analysable=analysable["n"] if analysable else 0,
            issues={c["code"]: c["n"] for c in counts},
            step_seconds=timings,
        )
        return str(run.run_id)


def _write_spills(
    cur: Any, spills: list[NormalizedSpill], run_id: uuid.UUID, raw_run_id: uuid.UUID, version: str
) -> None:
    with cur.copy(
        """COPY clean.spills (spill_id, run_id, raw_run_id, ruleset_version, status, operator,
               incident_number, incident_date, cause_code, cause_detail, contaminant_code,
               habitat_codes, quantity_bbl, state_code, lga_reported, site_name, jiv_date,
               geom_method, analysable)
           FROM STDIN"""
    ) as copy:
        for n in spills:
            copy.write_row(
                (
                    n.spill_id,
                    run_id,
                    raw_run_id,
                    version,
                    n.status,
                    n.operator,
                    n.incident_number,
                    n.incident_date,
                    n.cause_code,
                    n.cause_detail,
                    n.contaminant_code,
                    n.habitat_codes,
                    n.quantity_bbl,
                    n.state_code,
                    n.lga_reported,
                    n.site_name,
                    n.jiv_date,
                    "none",
                    False,
                )
            )

    with cur.copy(
        "COPY clean.spill_issues (spill_id, code, severity, field, message, details) FROM STDIN"
    ) as copy:
        for n in spills:
            for i in n.issues:
                copy.write_row((n.spill_id, i.code, i.severity.value, i.field, i.message, Jsonb(i.details)))

    # Candidates come in mixed CRSs as EWKT; PostGIS reprojects them to WGS 84.
    cur.execute("""
        CREATE TEMP TABLE cands_src (
            spill_id text, method text, priority smallint, srid integer, geom geometry
        ) ON COMMIT DROP""")
    with cur.copy("COPY cands_src (spill_id, method, priority, srid, geom) FROM STDIN") as copy:
        for n in spills:
            for c in n.coord_candidates:
                copy.write_row(
                    (
                        n.spill_id,
                        c.method,
                        spatial.METHOD_PRIORITY[c.method],
                        c.srid,
                        f"SRID={c.srid};POINT({c.x} {c.y})",
                    )
                )
    cur.execute("""
        CREATE TEMP TABLE cands ON COMMIT DROP AS
        SELECT spill_id, method, priority, srid,
               ST_Transform(geom, 4326)::geometry(Point, 4326) AS geom
        FROM cands_src""")
    cur.execute("CREATE INDEX ON cands (spill_id)")
    # Fresh planner statistics after the bulk load.
    for table in ("cands", "clean.spills", "clean.spill_issues"):
        cur.execute(f"ANALYZE {table}")
