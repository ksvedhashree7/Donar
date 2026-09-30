"""Phase 1 initial schema

Revision ID: 20260930_000001
Revises:
Create Date: 2026-09-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260930_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id UUID PRIMARY KEY,
            name VARCHAR(32) NOT NULL UNIQUE,
            description VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions (
            id UUID PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            role_id UUID NOT NULL REFERENCES roles(id),
            username VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            phone VARCHAR(50),
            password_hash VARCHAR(255) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_login_at TIMESTAMPTZ,
            totp_secret VARCHAR(255),
            lockout_until TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hospitals (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            code VARCHAR(50) NOT NULL UNIQUE,
            city VARCHAR(100) NOT NULL,
            state VARCHAR(100),
            latitude NUMERIC(9,6),
            longitude NUMERIC(9,6),
            services TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS donors (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL UNIQUE REFERENCES users(id),
            hospital_id UUID REFERENCES hospitals(id),
            donor_code VARCHAR(50) NOT NULL UNIQUE,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            date_of_birth TIMESTAMPTZ,
            gender VARCHAR(20),
            blood_group VARCHAR(10),
            organ VARCHAR(50),
            status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
            donation_mode VARCHAR(50),
            city VARCHAR(100),
            geohash VARCHAR(20),
            consent_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
            is_matchable BOOLEAN NOT NULL DEFAULT TRUE,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            verification_expires_at TIMESTAMPTZ,
            travel_mode VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK (date_of_birth IS NULL OR date_of_birth <= CURRENT_DATE)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recipients (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL UNIQUE REFERENCES users(id),
            hospital_id UUID REFERENCES hospitals(id),
            recipient_code VARCHAR(50) NOT NULL UNIQUE,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            blood_group VARCHAR(10),
            city VARCHAR(100),
            urgency VARCHAR(50),
            status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS doctors (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL UNIQUE REFERENCES users(id),
            hospital_id UUID REFERENCES hospitals(id),
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            licence_number VARCHAR(80),
            specialization VARCHAR(120),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hospital_staff (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL UNIQUE REFERENCES users(id),
            hospital_id UUID NOT NULL REFERENCES hospitals(id),
            role VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS medical_profiles (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL UNIQUE REFERENCES donors(id),
            blood_group VARCHAR(10),
            height_cm INTEGER,
            weight_kg INTEGER,
            allergies TEXT,
            conditions TEXT,
            medical_notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK (weight_kg IS NULL OR weight_kg > 0),
            CHECK (height_cm IS NULL OR height_cm > 0)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS field_verifications (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            medical_profile_id UUID REFERENCES medical_profiles(id),
            field_name VARCHAR(80) NOT NULL,
            value TEXT,
            status VARCHAR(32) NOT NULL DEFAULT 'SELF_REPORTED',
            verified_by UUID REFERENCES doctors(id),
            hospital_id UUID REFERENCES hospitals(id),
            verified_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            previous_value_hash VARCHAR(128),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS medical_reports (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            report_type VARCHAR(80) NOT NULL,
            storage_key VARCHAR(255) NOT NULL,
            mime_type VARCHAR(120),
            status VARCHAR(50) NOT NULL DEFAULT 'UPLOADED',
            expiry_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_versions (
            id UUID PRIMARY KEY,
            resource_type VARCHAR(80) NOT NULL,
            resource_id UUID NOT NULL,
            version_number INTEGER NOT NULL,
            object_key VARCHAR(255) NOT NULL,
            uploaded_by UUID REFERENCES users(id),
            checksum_sha256 VARCHAR(128),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (resource_type, resource_id, version_number)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS organ_preferences (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            organ VARCHAR(50) NOT NULL,
            preference_rank INTEGER,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (donor_id, organ)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS organ_requirements (
            id UUID PRIMARY KEY,
            recipient_id UUID NOT NULL REFERENCES recipients(id),
            hospital_id UUID REFERENCES hospitals(id),
            organ VARCHAR(50) NOT NULL,
            blood_group VARCHAR(10),
            urgency VARCHAR(50),
            size_params JSONB,
            location VARCHAR(100),
            status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_sets (
            id UUID PRIMARY KEY,
            version VARCHAR(50) NOT NULL UNIQUE,
            config JSONB NOT NULL,
            approved_by UUID REFERENCES users(id),
            effective_from TIMESTAMPTZ,
            status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS potential_matches (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            recipient_id UUID REFERENCES recipients(id),
            rule_set_id UUID REFERENCES rule_sets(id),
            score INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
            factors JSONB,
            hard_filter_results JSONB,
            disclaimer TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS match_reviews (
            id UUID PRIMARY KEY,
            potential_match_id UUID NOT NULL REFERENCES potential_matches(id),
            reviewer_id UUID REFERENCES users(id),
            review_action VARCHAR(50) NOT NULL,
            comments TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS coordination_cases (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            recipient_id UUID REFERENCES recipients(id),
            hospital_id UUID REFERENCES hospitals(id),
            status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
            summary TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            doctor_id UUID REFERENCES doctors(id),
            hospital_id UUID REFERENCES hospitals(id),
            scheduled_for TIMESTAMPTZ,
            status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS locations (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            city VARCHAR(100),
            geohash VARCHAR(20),
            latitude NUMERIC(9,6),
            longitude NUMERIC(9,6),
            is_exact BOOLEAN NOT NULL DEFAULT FALSE,
            is_visible_to_hospitals BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS availability (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL UNIQUE REFERENCES donors(id),
            status VARCHAR(50) NOT NULL DEFAULT 'AVAILABLE',
            city VARCHAR(100),
            travel_mode VARCHAR(50),
            available_from TIMESTAMPTZ,
            available_to TIMESTAMPTZ,
            last_updated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY,
            donor_id UUID REFERENCES donors(id),
            user_id UUID REFERENCES users(id),
            notification_type VARCHAR(80) NOT NULL,
            channel VARCHAR(40) NOT NULL DEFAULT 'IN_APP',
            subject VARCHAR(255),
            message TEXT,
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            scheduled_for TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS consents (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            purpose VARCHAR(80) NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
            consent_text TEXT,
            withdrawn_at TIMESTAMPTZ,
            is_withdrawable BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (donor_id, purpose, version)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS consent_events (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            purpose VARCHAR(80) NOT NULL,
            action VARCHAR(50) NOT NULL,
            details TEXT,
            is_voluntary BOOLEAN NOT NULL DEFAULT TRUE,
            no_payment BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS access_grants (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            granted_to_user_id UUID REFERENCES users(id),
            granted_to_role VARCHAR(50),
            purpose VARCHAR(80) NOT NULL,
            reason TEXT,
            valid_until TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY,
            actor_id UUID REFERENCES users(id),
            actor_role VARCHAR(50) NOT NULL,
            action VARCHAR(80) NOT NULL,
            resource_type VARCHAR(80) NOT NULL,
            resource_id VARCHAR(100),
            purpose VARCHAR(120),
            ip_address VARCHAR(45),
            user_agent VARCHAR(255),
            success BOOLEAN NOT NULL DEFAULT TRUE,
            prev_hash VARCHAR(128) NOT NULL DEFAULT '',
            row_hash VARCHAR(128) NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            name VARCHAR(120) NOT NULL,
            relation VARCHAR(80),
            phone VARCHAR(50) NOT NULL,
            email VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS verification_records (
            id UUID PRIMARY KEY,
            donor_id UUID NOT NULL REFERENCES donors(id),
            source_name VARCHAR(120) NOT NULL,
            source_type VARCHAR(80) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
            reference_id VARCHAR(120),
            verified_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS deceased_donor_events (
            id UUID PRIMARY KEY,
            hospital_id UUID REFERENCES hospitals(id),
            donor_code VARCHAR(50) NOT NULL,
            organ VARCHAR(50) NOT NULL,
            consent_status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
            event_time TIMESTAMPTZ,
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS organ_offers (
            id UUID PRIMARY KEY,
            deceased_event_id UUID REFERENCES deceased_donor_events(id),
            hospital_id UUID REFERENCES hospitals(id),
            organ VARCHAR(50) NOT NULL,
            recipient_id UUID REFERENCES recipients(id),
            status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only and cannot be updated or deleted';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_donors_organ ON donors (organ);
        CREATE INDEX IF NOT EXISTS ix_donors_blood_group ON donors (blood_group);
        CREATE INDEX IF NOT EXISTS ix_donors_city ON donors (city);
        CREATE INDEX IF NOT EXISTS ix_donors_status ON donors (status);
        CREATE INDEX IF NOT EXISTS ix_donors_geohash ON donors (geohash);
        CREATE INDEX IF NOT EXISTS ix_organ_requirements_organ ON organ_requirements (organ);
        CREATE INDEX IF NOT EXISTS ix_organ_requirements_blood_group ON organ_requirements (blood_group);
        CREATE INDEX IF NOT EXISTS ix_organ_requirements_status ON organ_requirements (status);
        CREATE INDEX IF NOT EXISTS ix_locations_city ON locations (city);
        CREATE INDEX IF NOT EXISTS ix_locations_geohash ON locations (geohash);
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")
    op.execute("DROP TABLE IF EXISTS organ_offers;")
    op.execute("DROP TABLE IF EXISTS deceased_donor_events;")
    op.execute("DROP TABLE IF EXISTS verification_records;")
    op.execute("DROP TABLE IF EXISTS emergency_contacts;")
    op.execute("DROP TABLE IF EXISTS audit_logs;")
    op.execute("DROP TABLE IF EXISTS access_grants;")
    op.execute("DROP TABLE IF EXISTS consent_events;")
    op.execute("DROP TABLE IF EXISTS consents;")
    op.execute("DROP TABLE IF EXISTS notifications;")
    op.execute("DROP TABLE IF EXISTS availability;")
    op.execute("DROP TABLE IF EXISTS locations;")
    op.execute("DROP TABLE IF EXISTS appointments;")
    op.execute("DROP TABLE IF EXISTS coordination_cases;")
    op.execute("DROP TABLE IF EXISTS match_reviews;")
    op.execute("DROP TABLE IF EXISTS potential_matches;")
    op.execute("DROP TABLE IF EXISTS rule_sets;")
    op.execute("DROP TABLE IF EXISTS organ_requirements;")
    op.execute("DROP TABLE IF EXISTS organ_preferences;")
    op.execute("DROP TABLE IF EXISTS document_versions;")
    op.execute("DROP TABLE IF EXISTS medical_reports;")
    op.execute("DROP TABLE IF EXISTS field_verifications;")
    op.execute("DROP TABLE IF EXISTS medical_profiles;")
    op.execute("DROP TABLE IF EXISTS hospital_staff;")
    op.execute("DROP TABLE IF EXISTS doctors;")
    op.execute("DROP TABLE IF EXISTS recipients;")
    op.execute("DROP TABLE IF EXISTS donors;")
    op.execute("DROP TABLE IF EXISTS hospitals;")
    op.execute("DROP TABLE IF EXISTS users;")
    op.execute("DROP TABLE IF EXISTS permissions;")
    op.execute("DROP TABLE IF EXISTS roles;")
