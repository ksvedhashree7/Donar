"""Associate donor blood-group verification with a selected blood bank."""

from alembic import op

revision = "20261022_000010"
down_revision = "20261022_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE blood_donors "
        "ADD COLUMN IF NOT EXISTS blood_group_verification_organisation_id UUID"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_donors'::regclass
                  AND conname = 'fk_blood_donors_verification_bank'
            ) THEN
                ALTER TABLE blood_donors
                    ADD CONSTRAINT fk_blood_donors_verification_bank
                    FOREIGN KEY (blood_group_verification_organisation_id)
                    REFERENCES blood_organisations (id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_column("blood_donors", "blood_group_verification_organisation_id")
