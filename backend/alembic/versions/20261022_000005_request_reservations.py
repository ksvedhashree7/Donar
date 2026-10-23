"""Add unit reservations and repeated server-managed outreach stages."""

from alembic import op
from app.models import Base

revision = "20261022_000005"
down_revision = "20261022_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE outreach_batches "
        "DROP CONSTRAINT IF EXISTS uq_outreach_batch_request_stage"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_outreach_batches_request_stage_status "
        "ON outreach_batches (request_id, stage, status)"
    )
    op.drop_constraint("ck_blood_requests_current_stage", "blood_requests", type_="check")
    op.create_check_constraint(
        "ck_blood_requests_current_stage",
        "blood_requests",
        "current_stage >= -1 AND current_stage <= 4",
    )
    op.alter_column(
        "request_status_history",
        "actor_user_id",
        nullable=True,
    )
    Base.metadata.tables["blood_request_reservations"].create(
        op.get_bind(),
        checkfirst=True,
    )


def downgrade() -> None:
    raise RuntimeError("Request reservation history cannot be safely downgraded")
