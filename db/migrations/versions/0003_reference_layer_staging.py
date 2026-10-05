"""staging schema, and a record of where reference layers came from

The GDAL script loads mangroves and settlements into `stage`. Then
`sheen ingest layers` checks them, moves them into `ref`, and records where
each one came from in ref.sources.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE SCHEMA stage;

    CREATE TABLE ref.sources (
        layer       text PRIMARY KEY,
        title       text NOT NULL,
        url         text NOT NULL,
        licence     text NOT NULL,
        as_of       date,           -- the date the data describes, not when we fetched it
        loaded_run_id uuid REFERENCES ops.pipeline_runs(run_id),
        notes       text
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE ref.sources; DROP SCHEMA stage CASCADE;")
