from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RoleName(str, enum.Enum):
    DONOR = "DONOR"
    REQUESTER = "REQUESTER"
    COORDINATOR = "COORDINATOR"
    RECIPIENT = "RECIPIENT"
    DOCTOR = "DOCTOR"
    HOSPITAL_STAFF = "HOSPITAL_STAFF"
    ADMIN = "ADMIN"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOCKED = "LOCKED"
    DELETED = "DELETED"


class DonorStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    MEDICAL_EVALUATED = "MEDICAL_EVALUATED"
    VERIFIED_DONOR_PROFILE = "VERIFIED_DONOR_PROFILE"
    UNAVAILABLE = "UNAVAILABLE"
    WITHDRAWN = "WITHDRAWN"
    INACTIVE = "INACTIVE"


class ConsentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"


class DonationMode(str, enum.Enum):
    LIVING_RELATED = "LIVING_RELATED"
    DECEASED_PLEDGE_REGISTRY = "DECEASED_PLEDGE_REGISTRY"
    DECEASED_ALLOCATION_EVENT = "DECEASED_ALLOCATION_EVENT"


class MatchingStatus(str, enum.Enum):
    PENDING = "PENDING"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    COORDINATION_STARTED = "COORDINATION_STARTED"
    CLOSED = "CLOSED"


class AppointmentStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"


class VerificationStatus(str, enum.Enum):
    SELF_REPORTED = "SELF_REPORTED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class RuleSetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name", native_enum=False), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class Permission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", native_enum=False), nullable=False, default=UserStatus.ACTIVE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lockout_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role: Mapped[Role] = relationship(back_populates="users")
    donor: Mapped["Donor | None"] = relationship(back_populates="user")
    recipient: Mapped["Recipient | None"] = relationship(back_populates="user")
    doctor: Mapped["Doctor | None"] = relationship(back_populates="user")
    hospital_staff: Mapped["HospitalStaff | None"] = relationship(back_populates="user")

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_role_id", "role_id"),
    )


class Hospital(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "hospitals"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    services: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    doctors: Mapped[list["Doctor"]] = relationship(back_populates="hospital")
    staff: Mapped[list["HospitalStaff"]] = relationship(back_populates="hospital")
    recipients: Mapped[list["Recipient"]] = relationship(back_populates="hospital")

    __table_args__ = (
        Index("ix_hospitals_city", "city"),
        Index("ix_hospitals_name", "name"),
    )


class Donor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "donors"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    donor_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    organ: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[DonorStatus] = mapped_column(
        Enum(DonorStatus, name="donor_status", native_enum=False), nullable=False, default=DonorStatus.PENDING
    )
    donation_mode: Mapped[DonationMode | None] = mapped_column(
        Enum(DonationMode, name="donation_mode", native_enum=False), nullable=True
    )
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geohash: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consent_status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status", native_enum=False), nullable=False, default=ConsentStatus.PENDING
    )
    is_matchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    travel_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)

    user: Mapped[User] = relationship(back_populates="donor")
    medical_profile: Mapped["MedicalProfile | None"] = relationship(back_populates="donor")
    organ_preferences: Mapped[list["OrganPreference"]] = relationship(back_populates="donor")
    emergency_contacts: Mapped[list["EmergencyContact"]] = relationship(back_populates="donor")
    consents: Mapped[list["Consent"]] = relationship(back_populates="donor")
    consent_events: Mapped[list["ConsentEvent"]] = relationship(back_populates="donor")
    field_verifications: Mapped[list["FieldVerification"]] = relationship(back_populates="donor")
    availability: Mapped["Availability | None"] = relationship(back_populates="donor")
    locations: Mapped[list["Location"]] = relationship(back_populates="donor")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="donor")

    __table_args__ = (
        Index("ix_donors_blood_group", "blood_group"),
        Index("ix_donors_city", "city"),
        Index("ix_donors_geohash", "geohash"),
        Index("ix_donors_organ", "organ"),
        Index("ix_donors_status", "status"),
        CheckConstraint("date_of_birth IS NULL OR date_of_birth <= CURRENT_DATE", name="ck_donors_date_of_birth"),
    )


class Recipient(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recipients"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    recipient_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")

    user: Mapped[User] = relationship(back_populates="recipient")
    hospital: Mapped[Hospital | None] = relationship(back_populates="recipients")
    organ_requirements: Mapped[list["OrganRequirement"]] = relationship(back_populates="recipient")

    __table_args__ = (
        Index("ix_recipients_blood_group", "blood_group"),
        Index("ix_recipients_city", "city"),
        Index("ix_recipients_status", "status"),
    )


class Doctor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "doctors"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    licence_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user: Mapped[User] = relationship(back_populates="doctor")
    hospital: Mapped[Hospital | None] = relationship(back_populates="doctors")


class HospitalStaff(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "hospital_staff"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    user: Mapped[User] = relationship(back_populates="hospital_staff")
    hospital: Mapped[Hospital] = relationship(back_populates="staff")


class MedicalProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "medical_profiles"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), unique=True, nullable=False)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    medical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    donor: Mapped[Donor] = relationship(back_populates="medical_profile")
    field_verifications: Mapped[list["FieldVerification"]] = relationship(back_populates="medical_profile")

    __table_args__ = (
        CheckConstraint("weight_kg IS NULL OR weight_kg > 0", name="ck_medical_profiles_weight_kg"),
        CheckConstraint("height_cm IS NULL OR height_cm > 0", name="ck_medical_profiles_height_cm"),
    )


class FieldVerification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "field_verifications"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    medical_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("medical_profiles.id"), nullable=True)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", native_enum=False),
        nullable=False,
        default=VerificationStatus.SELF_REPORTED,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_value_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    donor: Mapped[Donor] = relationship(back_populates="field_verifications")
    medical_profile: Mapped[MedicalProfile | None] = relationship(back_populates="field_verifications")

    __table_args__ = (
        Index("ix_field_verifications_donor_id", "donor_id"),
        Index("ix_field_verifications_field_name", "field_name"),
        Index("ix_field_verifications_status", "status"),
    )


class MedicalReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "medical_reports"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="UPLOADED")
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_versions"

    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        UniqueConstraint("resource_type", "resource_id", "version_number", name="uq_document_versions_resource_version"),
        Index("ix_document_versions_resource_id", "resource_id"),
    )


class OrganPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organ_preferences"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    organ: Mapped[str] = mapped_column(String(50), nullable=False)
    preference_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    donor: Mapped[Donor] = relationship(back_populates="organ_preferences")

    __table_args__ = (
        Index("ix_organ_preferences_organ", "organ"),
        UniqueConstraint("donor_id", "organ", name="uq_donor_organ_preference"),
    )


class OrganRequirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organ_requirements"

    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recipients.id"), nullable=False)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    organ: Mapped[str] = mapped_column(String(50), nullable=False)
    blood_group: Mapped[str | None] = mapped_column(String(10), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size_params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")

    recipient: Mapped[Recipient] = relationship(back_populates="organ_requirements")

    __table_args__ = (
        Index("ix_organ_requirements_organ", "organ"),
        Index("ix_organ_requirements_blood_group", "blood_group"),
        Index("ix_organ_requirements_status", "status"),
    )


class PotentialMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "potential_matches"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("recipients.id"), nullable=True)
    rule_set_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rule_sets.id"), nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[MatchingStatus] = mapped_column(
        Enum(MatchingStatus, name="matching_status", native_enum=False),
        nullable=False,
        default=MatchingStatus.PENDING,
    )
    factors: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    hard_filter_results: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_potential_matches_donor_id", "donor_id"),
        Index("ix_potential_matches_recipient_id", "recipient_id"),
        Index("ix_potential_matches_status", "status"),
    )


class MatchReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "match_reviews"

    potential_match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("potential_matches.id"), nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_action: Mapped[str] = mapped_column(String(50), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoordinationCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "coordination_cases"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("recipients.id"), nullable=True)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class Appointment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "appointments"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status", native_enum=False),
        nullable=False,
        default=AppointmentStatus.REQUESTED,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_appointments_donor_id", "donor_id"),
        Index("ix_appointments_status", "status"),
    )


class Location(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "locations"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geohash: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    is_exact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_visible_to_hospitals: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    donor: Mapped[Donor] = relationship(back_populates="locations")

    __table_args__ = (
        Index("ix_locations_city", "city"),
        Index("ix_locations_geohash", "geohash"),
        Index("ix_locations_donor_id", "donor_id"),
    )


class Availability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "availability"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="AVAILABLE")
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    travel_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    available_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    donor: Mapped[Donor] = relationship(back_populates="availability")

    __table_args__ = (
        Index("ix_availability_status", "status"),
        Index("ix_availability_city", "city"),
    )


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    donor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, default="IN_APP")
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    donor: Mapped[Donor | None] = relationship(back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_type", "notification_type"),
        Index("ix_notifications_is_read", "is_read"),
    )


class Consent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consents"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status_enum", native_enum=False),
        nullable=False,
        default=ConsentStatus.ACTIVE,
    )
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_withdrawable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    donor: Mapped[Donor] = relationship(back_populates="consents")

    __table_args__ = (
        UniqueConstraint("donor_id", "purpose", "version", name="uq_consent_donor_purpose_version"),
        Index("ix_consents_status", "status"),
    )


class ConsentEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "consent_events"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_voluntary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    no_payment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    donor: Mapped[Donor] = relationship(back_populates="consent_events")


class AccessGrant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "access_grants"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    granted_to_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    granted_to_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    prev_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    row_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    __table_args__ = (
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_success", "success"),
    )


class EmergencyContact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "emergency_contacts"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    relation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    donor: Mapped[Donor] = relationship(back_populates="emergency_contacts")


class VerificationRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "verification_records"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    reference_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_verification_records_donor_id", "donor_id"),
        Index("ix_verification_records_status", "status"),
    )


class RuleSet(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rule_sets"

    version: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RuleSetStatus] = mapped_column(
        Enum(RuleSetStatus, name="rule_set_status", native_enum=False),
        nullable=False,
        default=RuleSetStatus.DRAFT,
    )

    __table_args__ = (
        UniqueConstraint("version", name="uq_rule_sets_version"),
        Index("ix_rule_sets_status", "status"),
    )


class DeceasedDonorEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deceased_donor_events"

    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    donor_code: Mapped[str] = mapped_column(String(50), nullable=False)
    organ: Mapped[str] = mapped_column(String(50), nullable=False)
    consent_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("ix_deceased_donor_events_organ", "organ"),
        Index("ix_deceased_donor_events_donor_code", "donor_code"),
    )


class OrganOffer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organ_offers"

    deceased_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("deceased_donor_events.id"), nullable=True)
    hospital_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)
    organ: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("recipients.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_organ_offers_organ", "organ"),
        Index("ix_organ_offers_status", "status"),
    )
