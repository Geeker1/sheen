"""initial schema

Data flows raw -> clean -> analysis. `raw` is append-only and never edited, so
any cleaned value can be traced back to exactly what the source published.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    CREATE SCHEMA ops;
    CREATE SCHEMA raw;
    CREATE SCHEMA ref;
    CREATE SCHEMA clean;
    CREATE SCHEMA analysis;

    -- One row per stage run; downstream rows carry the run_id.
    CREATE TABLE ops.pipeline_runs (
        run_id          uuid PRIMARY KEY,
        stage           text NOT NULL,          -- ingest | validate | analyse
        source          text,
        source_sha256   text,
        ruleset_version text,
        parent_run_id   uuid REFERENCES ops.pipeline_runs(run_id),
        status          text NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'succeeded', 'failed')),
        rows_in         integer,
        rows_out        integer,
        details         jsonb NOT NULL DEFAULT '{}',
        error           text,
        started_at      timestamptz NOT NULL DEFAULT now(),
        finished_at     timestamptz
    );

    -- Exactly what NOSDRA published, one row per record per snapshot.
    CREATE TABLE raw.spill_reports (
        run_id      uuid NOT NULL REFERENCES ops.pipeline_runs(run_id),
        source_id   text NOT NULL,
        payload     jsonb NOT NULL,
        PRIMARY KEY (run_id, source_id)
    );

    -- Code tables, per field: 'co' is condensate as a contaminant but
    -- coastland as a habitat. Labels come from the Oil Spill Monitor legend.
    CREATE TABLE ref.codes (
        field   text NOT NULL,
        code    text NOT NULL,
        label   text NOT NULL,
        PRIMARY KEY (field, code)
    );

    CREATE TABLE ref.states (
        code    text PRIMARY KEY,               -- NOSDRA's two-letter code
        name    text NOT NULL,
        is_niger_delta boolean NOT NULL DEFAULT false
    );

    CREATE TABLE ref.admin_areas (
        pcode       text PRIMARY KEY,           -- OCHA P-code, e.g. NG033 / NG033012
        level       smallint NOT NULL CHECK (level IN (1, 2)),  -- state, LGA (no Delta ward data)
        name        text NOT NULL,
        parent_pcode text REFERENCES ref.admin_areas(pcode),
        state_code  text REFERENCES ref.states(code),
        geom        geometry(MultiPolygon, 4326) NOT NULL,
        geom_utm    geometry(MultiPolygon, 32632) GENERATED ALWAYS AS
                    (ST_Transform(geom, 32632)) STORED
    );
    CREATE INDEX ON ref.admin_areas USING gist (geom);
    CREATE INDEX ON ref.admin_areas USING gist (geom_utm);
    CREATE INDEX ON ref.admin_areas (level, state_code);
    CREATE INDEX ON ref.admin_areas USING gin (name gin_trgm_ops);

    CREATE TABLE ref.mangroves (
        id      bigserial PRIMARY KEY,
        year    smallint NOT NULL,
        geom_utm geometry(Polygon, 32632) NOT NULL
    );
    CREATE INDEX ON ref.mangroves USING gist (geom_utm);
    CREATE INDEX ON ref.mangroves (year);

    CREATE TABLE ref.settlements (
        id      bigserial PRIMARY KEY,
        name    text,
        kind    text,
        geom_utm geometry(Point, 32632) NOT NULL
    );
    CREATE INDEX ON ref.settlements USING gist (geom_utm);

    -- Latest validation only, replaced in one transaction. Older results can
    -- be rebuilt from raw plus the ruleset version.
    CREATE TABLE clean.spills (
        spill_id        text PRIMARY KEY,       -- NOSDRA record id
        run_id          uuid NOT NULL REFERENCES ops.pipeline_runs(run_id),
        raw_run_id      uuid NOT NULL REFERENCES ops.pipeline_runs(run_id),
        ruleset_version text NOT NULL,
        status          text,                   -- NOSDRA: confirmed/reviewed/invalid/...
        operator        text,
        incident_number text,
        incident_date   date,
        cause_code      text,
        cause_detail    text,                   -- free text after "other:"
        contaminant_code text,
        habitat_codes   text[] NOT NULL DEFAULT '{}',
        quantity_bbl    numeric,
        state_code      text,
        lga_reported    text,
        site_name       text,
        jiv_date        date,
        geom            geometry(Point, 4326),
        geom_utm        geometry(Point, 32632) GENERATED ALWAYS AS
                        (ST_Transform(geom, 32632)) STORED,
        geom_method     text NOT NULL CHECK (geom_method IN
                        ('reported', 'swapped', 'reprojected', 'decimal_shift', 'none')),
        lga_pcode       text REFERENCES ref.admin_areas(pcode),  -- computed from geom
        analysable      boolean NOT NULL        -- no blocking issues
    );
    CREATE INDEX ON clean.spills USING gist (geom);
    CREATE INDEX ON clean.spills USING gist (geom_utm);
    CREATE INDEX ON clean.spills (incident_date);
    CREATE INDEX ON clean.spills (operator);
    CREATE INDEX ON clean.spills (lga_pcode);

    CREATE TABLE clean.spill_issues (
        id          bigserial PRIMARY KEY,
        spill_id    text NOT NULL REFERENCES clean.spills(spill_id) ON DELETE CASCADE,
        code        text NOT NULL,
        severity    text NOT NULL CHECK (severity IN ('error', 'warning', 'info')),
        field       text,
        message     text NOT NULL,
        details     jsonb NOT NULL DEFAULT '{}'
    );
    CREATE INDEX ON clean.spill_issues (spill_id);
    CREATE INDEX ON clean.spill_issues (code);

    CREATE TABLE analysis.spill_exposure (
        spill_id            text PRIMARY KEY REFERENCES clean.spills(spill_id) ON DELETE CASCADE,
        run_id              uuid NOT NULL REFERENCES ops.pipeline_runs(run_id),
        mangrove_ha_1km     numeric NOT NULL,
        mangrove_ha_5km     numeric NOT NULL,
        settlements_2km     integer NOT NULL,
        nearest_settlement_m numeric
    );
    """)


def downgrade() -> None:
    op.execute("DROP SCHEMA analysis, clean, ref, raw, ops CASCADE;")
