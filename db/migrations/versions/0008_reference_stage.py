"""record reference-layer loads under their own stage

Boundary and layer loads used to be recorded as 'ingest', so "latest
successful ingest" could pick one of them instead of a spill snapshot.

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    UPDATE ops.pipeline_runs r SET stage = 'reference'
    WHERE stage = 'ingest'
      AND NOT EXISTS (SELECT 1 FROM raw.spill_reports s WHERE s.run_id = r.run_id);
    """)


def downgrade() -> None:
    op.execute("UPDATE ops.pipeline_runs SET stage = 'ingest' WHERE stage = 'reference';")
