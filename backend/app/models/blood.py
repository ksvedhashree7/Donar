from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BloodOrganisation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blood_organisations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    locality: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BloodCoordinator(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blood_coordinators"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_organisations.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_blood_coordinators_organisation", "organisation_id"),)


class BloodDonorProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blood_donors"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    blood_group: Mapped[str] = mapped_column(String(3), nullable=False)
    locality: Mapped[str] = mapped_column(String(120), nullable=False)
    approx_latitude: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    approx_longitude: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False, default="NEEDS_CONFIRMATION")
    notification_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    urgent_contact_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("blood_group IN ('O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-')", name="blood_group"),
        Index("ix_blood_donors_blood_group", "blood_group"),
        Index("ix_blood_donors_availability", "availability"),
    )


class BloodRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blood_requests"

    public_id: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_organisations.id"), nullable=True)
    coordinator_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    facility: Mapped[str] = mapped_column(String(200), nullable=False)
    locality: Mapped[str] = mapped_column(String(120), nullable=False)
    approx_latitude: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    approx_longitude: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    blood_group: Mapped[str] = mapped_column(String(3), nullable=False)
    required_donors: Mapped[int] = mapped_column(Integer, nullable=False)
    required_by: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, default="URGENT")
    facility_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    additional_information: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_VERIFICATION")
    current_stage: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    outreach_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("required_donors > 0 AND required_donors <= 50", name="required_donors"),
        CheckConstraint("current_stage >= -1 AND current_stage <= 3", name="current_stage"),
        Index("ix_blood_requests_status", "status"),
        Index("ix_blood_requests_group_status", "blood_group", "status"),
        Index("ix_blood_requests_required_by", "required_by"),
    )


class BloodRequestVerification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "request_verifications"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_requests.id"), nullable=False)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_request_verifications_request", "request_id"),)


class BloodDonorMatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "donor_matches"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_requests.id"), nullable=False)
    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_donors.id"), nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="MATCHED")

    __table_args__ = (UniqueConstraint("request_id", "donor_id", name="uq_blood_match_request_donor"),)


class BloodOutreachBatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "outreach_batches"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_requests.id"), nullable=False)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    radius_min_km: Mapped[int] = mapped_column(Integer, nullable=False)
    radius_max_km: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

    __table_args__ = (UniqueConstraint("request_id", "stage", name="uq_outreach_batch_request_stage"),)


class BloodNotification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blood_notifications"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_requests.id"), nullable=False)
    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_donors.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("outreach_batches.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("request_id", "donor_id", name="uq_blood_notification_request_donor"),)


class BloodNotificationResponse(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notification_responses"

    notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_notifications.id"), unique=True, nullable=False)
    response: Mapped[str] = mapped_column(String(20), nullable=False)
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BloodRequestStatusHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "request_status_history"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_requests.id"), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_request_status_history_request", "request_id"),)


class BloodConsent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blood_consents"

    donor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("blood_donors.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("donor_id", "purpose", "version", name="uq_blood_consent_donor_purpose_version"),)