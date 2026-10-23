"""Track verified account phone numbers for consent-based contact sharing."""

import sqlalchemy as sa

from alembic import op

revision = "20261022_000007"
down_revision = "20261022_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "phone_verified_at")
