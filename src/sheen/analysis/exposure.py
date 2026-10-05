"""What's near each usable spill, and the summaries by area and by company.

This measures what was near a spill, not how much damage it did.
"""

import time

import structlog

from sheen.db import connect
from sheen.runs import latest_successful, pipeline_run

log = structlog.get_logger()

STEPS: list[tuple[str, str]] = [
    ("reset", "TRUNCATE analysis.spill_exposure"),
    (
        "mangroves",
        """
        -- Mangrove area within 1 km of each spill, using the mangrove map closest
        -- in time. Each point is worked out once, even if several reports share it.
        WITH pts AS (
            SELECT DISTINCT geom_utm,
                   CASE WHEN incident_date < DATE '2014-01-01' THEN 2007 ELSE 2020 END AS year
            FROM clean.spills WHERE analysable
        ),
        ha AS (
            SELECT p.geom_utm, p.year,
                   coalesce(sum(CASE WHEN ST_CoveredBy(m.geom_utm, b.disc) THEN ST_Area(m.geom_utm)
                                     ELSE ST_Area(ST_Intersection(m.geom_utm, b.disc)) END), 0) / 1e4
                       AS ha_1km
            FROM pts p
            CROSS JOIN LATERAL (SELECT ST_Buffer(p.geom_utm, 1000, 16) AS disc) b
            LEFT JOIN ref.mangroves m
                   ON m.year = p.year AND ST_DWithin(m.geom_utm, p.geom_utm, 1000)
            GROUP BY p.geom_utm, p.year
        )
        INSERT INTO analysis.spill_exposure (spill_id, run_id, mangrove_year, mangrove_ha_1km)
        SELECT s.spill_id, %(run_id)s, ha.year, ha.ha_1km
        FROM clean.spills s
        JOIN ha ON ha.geom_utm = s.geom_utm
               AND ha.year = CASE WHEN s.incident_date < DATE '2014-01-01' THEN 2007 ELSE 2020 END
        WHERE s.analysable
    """,
    ),
    (
        "settlements",
        """
        UPDATE analysis.spill_exposure e
        SET settlements_2km = (SELECT count(*) FROM ref.settlements t
                               WHERE ST_DWithin(t.geom_utm, s.geom_utm, 2000)),
            nearest_settlement_m = (SELECT round(ST_Distance(t.geom_utm, s.geom_utm))
                                    FROM ref.settlements t
                                    ORDER BY t.geom_utm <-> s.geom_utm LIMIT 1)
        FROM clean.spills s
        WHERE s.spill_id = e.spill_id
          AND EXISTS (SELECT 1 FROM ref.settlements)
    """,
    ),
    ("lga_summary", "REFRESH MATERIALIZED VIEW analysis.lga_summary"),
    ("operator_quality", "REFRESH MATERIALIZED VIEW analysis.operator_quality"),
]


def analyse() -> str:
    validate_run_id = latest_successful("validate")
    if validate_run_id is None:
        raise RuntimeError("No successful validation; run `sheen validate` first")

    with pipeline_run("analyse", parent_run_id=validate_run_id) as run, connect() as conn:
        timings: dict[str, float] = {}
        for name, sql in STEPS:
            t0 = time.monotonic()
            cur = conn.execute(sql, {"run_id": run.run_id})
            timings[name] = round(time.monotonic() - t0, 2)
            log.info("analyse.step", step=name, rows=cur.rowcount, duration_s=timings[name])
            if name == "mangroves":
                run.rows_out = cur.rowcount
        run.details["step_seconds"] = timings
        return str(run.run_id)
