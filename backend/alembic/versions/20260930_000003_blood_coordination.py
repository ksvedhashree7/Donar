"""Add blood request, consent, matching, and radius outreach tables.

Revision ID: 20260930_000003
Revises: 20260930_000002
Create Date: 2026-09-30 00:00:00.000000
"""

from alembic import op

from app.models import Base

revision = "20260930_000003"
down_revision = "20260930_000002"
branch_labels = None
depends_on = None

BLOOD_TABLES = {
    "blood_organisations",
    "blood_coordinators",
    "blood_donors",
    "blood_requests",
    "request_verifications",
    "donor_matches",
    "outreach_batches",
    "blood_notifications",
    "notification_responses",
    "request_status_history",
    "blood_consents",
}


def upgrade() -> None:
    connection = op.get_bind()
    for table in Base.metadata.sorted_tables:
        if table.name in BLOOD_TABLES:
            table.create(connection, checkfirst=True)


def downgrade() -> None:
    connection = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in BLOOD_TABLES:
            table.drop(connection, checkfirst=True)