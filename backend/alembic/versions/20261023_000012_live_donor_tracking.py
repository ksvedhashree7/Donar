"""Add live donor tracking sessions and tracking notifications."""

from alembic import op

from app.models import Base

revision = "20261023_000012"
down_revision = "20261022_000011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "blood_donor_tracking_sessions" in Base.metadata.tables:
        Base.metadata.tables["blood_donor_tracking_sessions"].create(
            bind,
            checkfirst=True,
        )
    if "blood_tracking_notifications" in Base.metadata.tables:
        Base.metadata.tables["blood_tracking_notifications"].create(
            bind,
            checkfirst=True,
        )


def downgrade() -> None:
    op.drop_table("blood_tracking_notifications")
    op.drop_table("blood_donor_tracking_sessions")
