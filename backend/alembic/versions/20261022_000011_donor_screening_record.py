"""Record institutional donor-screening completion without determining eligibility."""

from alembic import op

revision = "20261022_000011"
down_revision = "20261022_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE blood_donors "
        "ADD COLUMN IF NOT EXISTS screening_completed_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE blood_donors "
        "ADD COLUMN IF NOT EXISTS screening_completed_by_user_id UUID"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_donors'::regclass
                  AND conname = 'fk_blood_donors_screening_completed_by_user_id_users'
            ) THEN
                ALTER TABLE blood_donors
                    ADD CONSTRAINT fk_blood_donors_screening_completed_by_user_id_users
                    FOREIGN KEY (screening_completed_by_user_id) REFERENCES users (id);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_donors'::regclass
                  AND conname = 'ck_blood_donors_screening_requires_verified_blood_group'
            ) THEN
                ALTER TABLE blood_donors
                    ADD CONSTRAINT
                    ck_blood_donors_screening_requires_verified_blood_group
                    CHECK (
                        screening_completed_at IS NULL
                        OR blood_group_verified_at IS NOT NULL
                    );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_blood_donors_screening_requires_verified_blood_group",
        "blood_donors",
        type_="check",
    )
    op.drop_column("blood_donors", "screening_completed_by_user_id")
    op.drop_column("blood_donors", "screening_completed_at")
