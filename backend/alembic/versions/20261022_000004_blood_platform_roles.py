"""Consolidate the canonical application to its three blood-platform roles."""

from alembic import op

revision = "20261022_000004"
down_revision = "20260930_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            old_name TEXT;
            new_name TEXT;
            old_role_id UUID;
            new_role_id UUID;
        BEGIN
            IF to_regclass('blood_coordinators') IS NOT NULL
               AND to_regclass('blood_bank_staff') IS NULL THEN
                ALTER TABLE blood_coordinators RENAME TO blood_bank_staff;
            END IF;

            IF to_regclass('ix_blood_coordinators_organisation') IS NOT NULL
               AND to_regclass('ix_blood_bank_staff_organisation') IS NULL THEN
                ALTER INDEX ix_blood_coordinators_organisation
                    RENAME TO ix_blood_bank_staff_organisation;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'blood_requests'
                  AND column_name = 'coordinator_user_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'blood_requests'
                  AND column_name = 'assigned_staff_user_id'
            ) THEN
                ALTER TABLE blood_requests
                    RENAME COLUMN coordinator_user_id TO assigned_staff_user_id;
            END IF;
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_requests'::regclass
                  AND conname = 'fk_blood_requests_coordinator_user_id_users'
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_requests'::regclass
                  AND conname = 'fk_blood_requests_assigned_staff_user_id_users'
            ) THEN
                ALTER TABLE blood_requests
                    RENAME CONSTRAINT fk_blood_requests_coordinator_user_id_users
                    TO fk_blood_requests_assigned_staff_user_id_users;
            END IF;

            FOR old_name, new_name IN
                SELECT * FROM (VALUES
                    ('DONOR', 'GENERAL_DONOR'),
                    ('REQUESTER', 'GENERAL_DONOR'),
                    ('RECIPIENT', 'GENERAL_DONOR'),
                    ('COORDINATOR', 'BLOOD_BANK'),
                    ('DOCTOR', 'BLOOD_BANK'),
                    ('HOSPITAL_STAFF', 'BLOOD_BANK')
                ) AS role_map(old_name, new_name)
            LOOP
                SELECT id INTO old_role_id FROM roles WHERE name = old_name;
                IF old_role_id IS NOT NULL THEN
                    SELECT id INTO new_role_id FROM roles WHERE name = new_name;
                    IF new_role_id IS NULL THEN
                        UPDATE roles SET name = new_name WHERE id = old_role_id;
                    ELSE
                        UPDATE users SET role_id = new_role_id WHERE role_id = old_role_id;
                        DELETE FROM roles WHERE id = old_role_id;
                    END IF;
                END IF;
                old_role_id := NULL;
                new_role_id := NULL;
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS institution_type VARCHAR(80)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS representative_name VARCHAR(160)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS official_phone VARCHAR(50)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS address VARCHAR(300)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS district VARCHAR(100)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS state VARCHAR(100)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS pincode VARCHAR(10)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS registration_number VARCHAR(100)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS issuing_authority VARCHAR(160)"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS license_expires_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS verification_status VARCHAR(24) NOT NULL DEFAULT 'PENDING'"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS verification_notes TEXT"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS verified_by_user_id UUID"
    )
    op.execute(
        "ALTER TABLE blood_organisations "
        "ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_organisations'::regclass
                  AND conname = 'ck_blood_organisations_blood_organisation_verification_status'
            ) THEN
                ALTER TABLE blood_organisations
                    ADD CONSTRAINT ck_blood_organisations_blood_organisation_verification_status
                    CHECK (
                        verification_status IN (
                            'PENDING', 'VERIFIED', 'REJECTED', 'SUSPENDED', 'EXPIRED'
                        )
                    );
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_organisations'::regclass
                  AND conname = 'uq_blood_organisation_registration_number'
            ) THEN
                ALTER TABLE blood_organisations
                    ADD CONSTRAINT uq_blood_organisation_registration_number
                    UNIQUE (registration_number);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'blood_organisations'::regclass
                  AND conname = 'fk_blood_organisations_verified_by_user_id_users'
            ) THEN
                ALTER TABLE blood_organisations
                    ADD CONSTRAINT fk_blood_organisations_verified_by_user_id_users
                    FOREIGN KEY (verified_by_user_id) REFERENCES users (id);
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_blood_organisations_verification_status "
        "ON blood_organisations (verification_status)"
    )
    op.execute(
        "UPDATE blood_organisations SET is_active = FALSE "
        "WHERE verification_status <> 'VERIFIED'"
    )


def downgrade() -> None:
    raise RuntimeError(
        "The role consolidation migration is not reversible without losing role history"
    )
