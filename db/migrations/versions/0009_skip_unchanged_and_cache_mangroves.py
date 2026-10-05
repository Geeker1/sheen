"""skipped runs, and saved mangrove figures per location

A download that hasn't changed since the last one is recorded as 'skipped'
and nothing else runs. Mangrove area within 1 km is saved per location and
map year, so later runs only work it out for new locations.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE ops.pipeline_runs DROP CONSTRAINT pipeline_runs_status_check;
    ALTER TABLE ops.pipeline_runs ADD CONSTRAINT pipeline_runs_status_check
        CHECK (status IN ('running', 'succeeded', 'skipped', 'failed'));

    CREATE TABLE analysis.point_mangroves (
        point_key   text NOT NULL,      -- md5 of the point, so it can be a key
        year        smallint NOT NULL,  -- which mangrove map
        ha_1km      numeric NOT NULL,
        PRIMARY KEY (point_key, year)
    );
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE analysis.point_mangroves;
    UPDATE ops.pipeline_runs SET status = 'succeeded' WHERE status = 'skipped';
    ALTER TABLE ops.pipeline_runs DROP CONSTRAINT pipeline_runs_status_check;
    ALTER TABLE ops.pipeline_runs ADD CONSTRAINT pipeline_runs_status_check
        CHECK (status IN ('running', 'succeeded', 'failed'));
    """)
