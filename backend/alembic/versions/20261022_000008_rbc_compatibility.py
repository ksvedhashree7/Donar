"""Add request components and verified donor blood-group records."""

from alembic import op

revision = "20261022_000008"
down_revision = "20261022_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE blood_requests "
        "ADD COLUMN IF NOT EXISTS component VARCHAR(24) NOT NULL DEFAULT 'RED_CELLS'"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_requests'::regclass
                  AND conname = 'ck_blood_requests_component'
            ) THEN
                ALTER TABLE blood_requests
                    ADD CONSTRAINT ck_blood_requests_component
                    CHECK (component IN (
                        'RED_CELLS', 'PLASMA', 'PLATELETS', 'WHOLE_BLOOD', 'OTHER'
                    ));
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE blood_donors "
        "ADD COLUMN IF NOT EXISTS blood_group_verified_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE blood_donors "
        "ADD COLUMN IF NOT EXISTS blood_group_verified_by_user_id UUID"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_donors'::regclass
                  AND conname = 'fk_blood_donors_blood_group_verified_by_user_id_users'
            ) THEN
                ALTER TABLE blood_donors
                    ADD CONSTRAINT fk_blood_donors_blood_group_verified_by_user_id_users
                    FOREIGN KEY (blood_group_verified_by_user_id) REFERENCES users (id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    raise RuntimeError("Verified blood-group and component records cannot be safely downgraded")
