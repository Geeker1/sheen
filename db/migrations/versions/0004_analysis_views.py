"""analysis outputs: per-spill exposure and regional / operator summaries

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DROP TABLE analysis.spill_exposure;
    CREATE TABLE analysis.spill_exposure (
        spill_id             text PRIMARY KEY REFERENCES clean.spills(spill_id) ON DELETE CASCADE,
        run_id               uuid NOT NULL REFERENCES ops.pipeline_runs(run_id),
        mangrove_year        smallint NOT NULL,   -- GMW extent closest to the incident
        mangrove_ha_1km      numeric NOT NULL,
        settlements_2km      integer,             -- NULL when no settlement layer is loaded
        nearest_settlement_m numeric
    );

    -- Totals for each area. Spill counts only use usable reports; the
    -- missing-data columns use every report that can be placed in the area.
    CREATE MATERIALIZED VIEW analysis.lga_summary AS
    WITH placed AS (
        SELECT s.*, e.mangrove_ha_1km, e.settlements_2km
        FROM clean.spills s LEFT JOIN analysis.spill_exposure e USING (spill_id)
        WHERE s.lga_pcode IS NOT NULL
    ),
    mangroves AS (
        SELECT a.pcode,
               sum(ST_Area(ST_Intersection(m.geom_utm, a.geom_utm))) FILTER (WHERE m.year = 2007) / 1e4 AS ha_2007,
               sum(ST_Area(ST_Intersection(m.geom_utm, a.geom_utm))) FILTER (WHERE m.year = 2020) / 1e4 AS ha_2020
        FROM ref.admin_areas a JOIN ref.mangroves m ON ST_Intersects(m.geom_utm, a.geom_utm)
        WHERE a.level = 2
        GROUP BY a.pcode
    )
    SELECT a.pcode, a.name, st.name AS state, st.state_code,
           round((ST_Area(a.geom_utm) / 1e6)::numeric, 1) AS area_km2,
           count(*) FILTER (WHERE p.analysable)                            AS spills,
           round(sum(p.quantity_bbl) FILTER (WHERE p.analysable), 1)       AS reported_bbl,
           count(*) FILTER (WHERE p.analysable AND p.cause_code = 'sab')   AS spills_sabotage,
           count(*) FILTER (WHERE p.analysable AND p.cause_code IN ('eqf', 'cor', 'ome'))
                                                                           AS spills_operational,
           round(sum(p.mangrove_ha_1km) FILTER (WHERE p.analysable), 1)   AS mangrove_ha_within_1km_total,
           round(coalesce(mg.ha_2007, 0)::numeric, 1)                      AS mangrove_ha_2007,
           round(coalesce(mg.ha_2020, 0)::numeric, 1)                      AS mangrove_ha_2020,
           count(p.spill_id)                                               AS reports_placed,
           round(avg((p.quantity_bbl IS NULL)::int) FILTER (WHERE p.spill_id IS NOT NULL), 3)
                                                                           AS share_missing_quantity,
           a.geom
    FROM ref.admin_areas a
    JOIN ref.admin_areas st ON st.pcode = a.parent_pcode
    LEFT JOIN placed p ON p.lga_pcode = a.pcode
    LEFT JOIN mangroves mg ON mg.pcode = a.pcode
    WHERE a.level = 2
    GROUP BY a.pcode, a.name, st.name, st.state_code, a.geom, a.geom_utm, mg.ha_2007, mg.ha_2020;
    CREATE UNIQUE INDEX ON analysis.lga_summary (pcode);

    -- How much each company leaves out. This uses every report, because
    -- missing data is exactly what it measures.
    CREATE MATERIALIZED VIEW analysis.operator_quality AS
    SELECT s.operator,
           count(*)                                                        AS reports,
           count(*) FILTER (WHERE s.analysable)                            AS analysable,
           round(avg((s.geom IS NULL)::int), 3)                            AS share_unplaceable,
           round(avg((s.quantity_bbl IS NULL)::int), 3)                    AS share_missing_quantity,
           round(avg((s.cause_code IS NULL)::int), 3)                      AS share_missing_cause,
           round(avg((s.jiv_date IS NULL)::int), 3)                        AS share_missing_jiv,
           round(avg((s.cause_code = 'sab')::int) FILTER (WHERE s.cause_code IS NOT NULL), 3)
                                                                           AS share_sabotage_of_known_cause,
           round(sum(s.quantity_bbl) FILTER (WHERE s.analysable), 1)       AS reported_bbl
    FROM clean.spills s
    WHERE s.operator IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM clean.spill_issues i
                      WHERE i.spill_id = s.spill_id AND i.code IN ('NOT_A_SPILL', 'STATUS_INVALID'))
    GROUP BY s.operator;
    CREATE UNIQUE INDEX ON analysis.operator_quality (operator);
    """)


def downgrade() -> None:
    op.execute("""
    DROP MATERIALIZED VIEW analysis.operator_quality;
    DROP MATERIALIZED VIEW analysis.lga_summary;
    """)
