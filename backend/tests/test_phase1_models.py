from pathlib import Path

from sqlalchemy import Enum

from app.models import AuditLog, Base


def test_phase1_metadata_contains_required_tables() -> None:
    tables = set(Base.metadata.tables.keys())
    required = {
        "roles",
        "permissions",
        "users",
        "hospitals",
        "donors",
        "recipients",
        "doctors",
        "hospital_staff",
        "medical_profiles",
        "field_verifications",
        "medical_reports",
        "document_versions",
        "organ_preferences",
        "organ_requirements",
        "rule_sets",
        "potential_matches",
        "match_reviews",
        "coordination_cases",
        "appointments",
        "locations",
        "availability",
        "notifications",
        "consents",
        "consent_events",
        "access_grants",
        "audit_logs",
        "emergency_contacts",
        "verification_records",
        "deceased_donor_events",
        "organ_offers",
    }
    assert required.issubset(tables)


def test_audit_log_fields_support_append_only_design() -> None:
    columns = set(AuditLog.__table__.columns.keys())
    assert {"prev_hash", "row_hash", "actor_id", "action", "resource_type"}.issubset(columns)


def test_enum_columns_match_migration_varchar_storage() -> None:
    enum_columns = [
        column
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, Enum)
    ]
    assert enum_columns
    assert all(not column.type.native_enum for column in enum_columns)


def test_migration_contains_append_only_trigger() -> None:
    migration_path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "20260930_000001_phase1_initial_schema.py"
    )
    assert migration_path.exists()
    migration_text = migration_path.read_text(encoding="utf-8")
    assert "audit_logs_append_only" in migration_text
    assert "BEFORE UPDATE OR DELETE" in migration_text
