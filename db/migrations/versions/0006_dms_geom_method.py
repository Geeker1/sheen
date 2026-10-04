"""allow 'dms' (packed degrees-minutes-seconds) as a location method

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE clean.spills DROP CONSTRAINT spills_geom_method_check;
    ALTER TABLE clean.spills ADD CONSTRAINT spills_geom_method_check CHECK (geom_method IN
        ('reported', 'swapped', 'reprojected', 'decimal_shift', 'dms', 'none'));
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE clean.spills DROP CONSTRAINT spills_geom_method_check;
    ALTER TABLE clean.spills ADD CONSTRAINT spills_geom_method_check CHECK (geom_method IN
        ('reported', 'swapped', 'reprojected', 'decimal_shift', 'none'));
    """)
