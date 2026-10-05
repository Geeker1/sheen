"""split static per-LGA mangrove area out of the per-run LGA summary

It only changes when the mangrove data changes, but it was being worked out
again on every analysis run, which took about 70 seconds. Now it has its own
view, updated by `sheen ingest layers`.

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

LGA_SUMMARY = """
    CREATE MATERIALIZED VIEW analysis.lga_summary AS
    WITH placed AS (
        SELECT s.*, e.mangrove_ha_1km, e.settlements_2km
        FROM clean.spills s LEFT JOIN analysis.spill_exposure e USING (spill_id)
        WHERE s.lga_pcode IS NOT NULL
    )
    SELECT a.pcode, a.name, st.name AS state, st.state_code,
           round((ST_Area(a.geom_utm) / 1e6)::numeric, 1) AS area_km2,
           count(*) FILTER (WHERE p.analysable)                            AS spills,
           round(sum(p.quantity_bbl) FILTER (WHERE p.analysable), 1)       AS reported_bbl,
           count(*) FILTER (WHERE p.analysable AND p.cause_code = 'sab')   AS spills_sabotage,
           count(*) FILTER (WHERE p.analysable AND p.cause_code IN ('eqf', 'cor', 'ome'))
                                                                           AS spills_operational,
           round(sum(p.mangrove_ha_1km) FILTER (WHERE p.analysable), 1)   AS mangrove_ha_within_1km_total,
           coalesce(mg.ha_2007, 0)                                         AS mangrove_ha_2007,
           coalesce(mg.ha_2020, 0)                                         AS mangrove_ha_2020,
           count(p.spill_id)                                               AS reports_placed,
           round(avg((p.quantity_bbl IS NULL)::int) FILTER (WHERE p.spill_id IS NOT NULL), 3)
                                                                           AS share_missing_quantity,
           a.geom
    FROM ref.admin_areas a
    JOIN ref.admin_areas st ON st.pcode = a.parent_pcode
    LEFT JOIN placed p ON p.lga_pcode = a.pcode
    LEFT JOIN ref.lga_mangroves mg ON mg.pcode = a.pcode
    WHERE a.level = 2
    GROUP BY a.pcode, a.name, st.name, st.state_code, a.geom, a.geom_utm, mg.ha_2007, mg.ha_2020;
    CREATE UNIQUE INDEX ON analysis.lga_summary (pcode);
"""


def upgrade() -> None:
    op.execute("""
    DROP MATERIALIZED VIEW analysis.lga_summary;

    CREATE MATERIALIZED VIEW ref.lga_mangroves AS
    SELECT a.pcode,
           round((sum(ST_Area(ST_Intersection(m.geom_utm, a.geom_utm)))
                  FILTER (WHERE m.year = 2007) / 1e4)::numeric, 1) AS ha_2007,
           round((sum(ST_Area(ST_Intersection(m.geom_utm, a.geom_utm)))
                  FILTER (WHERE m.year = 2020) / 1e4)::numeric, 1) AS ha_2020
    FROM ref.admin_areas a JOIN ref.mangroves m ON ST_Intersects(m.geom_utm, a.geom_utm)
    WHERE a.level = 2
    GROUP BY a.pcode;
    CREATE UNIQUE INDEX ON ref.lga_mangroves (pcode);
    """ + LGA_SUMMARY)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW analysis.lga_summary; DROP MATERIALIZED VIEW ref.lga_mangroves;")
