"""Snapshot donor blood group on each notification for historical reporting."""

from alembic import op

revision = "20261022_000009"
down_revision = "20261022_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE blood_notifications "
        "ADD COLUMN IF NOT EXISTS donor_blood_group VARCHAR(3)"
    )
    op.execute(
        """
        UPDATE blood_notifications AS notification
        SET donor_blood_group = donor.blood_group
        FROM blood_donors AS donor
        WHERE notification.donor_id = donor.id
          AND notification.donor_blood_group IS NULL
        """
    )
    op.execute(
        "ALTER TABLE blood_notifications "
        "ALTER COLUMN donor_blood_group SET NOT NULL"
    )


def downgrade() -> None:
    raise RuntimeError("Historical notification group snapshots cannot be safely removed")
