"""Add institution-confirmed completion records for donor reservations."""

from alembic import op
from app.models import Base

revision = "20261022_000006"
down_revision = "20261022_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.tables["blood_donation_records"].create(
        op.get_bind(),
        checkfirst=True,
    )


def downgrade() -> None:
    raise RuntimeError("Verified completion history cannot be safely downgraded")
