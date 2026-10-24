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


class BloodDonorTrackingSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blood_donor_tracking_sessions"

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blood_requests.id"), nullable=False
    )
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blood_request_reservations.id"),
        unique=True,
        nullable=False,
    )
    donor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blood_donors.id"), nullable=False
    )

    # WAITING_FOR_SHARING, SHARING, PAUSED, ARRIVED, STOPPED, CANCELLED
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="WAITING_FOR_SHARING"
    )
    consent_granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Destination snapshot
    destination_facility: Mapped[str] = mapped_column(String(200), nullable=False)
    destination_locality: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    destination_longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Live donor coordinates (populated only while sharing)
    current_latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    current_longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    current_accuracy_meters: Mapped[float | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    last_location_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Calculated Road Routing & ETA
    estimated_distance_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_arrival_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    route_distance_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route_duration_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encoded_polyline: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lifecycle milestones
    arrived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stop_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('WAITING_FOR_SHARING', 'SHARING', 'PAUSED', 'ARRIVED', 'STOPPED', 'CANCELLED')",
            name="ck_tracking_session_status",
        ),
        Index("ix_donor_tracking_request_id", "request_id"),
        Index("ix_donor_tracking_donor_id", "donor_id"),
        Index("ix_donor_tracking_status", "status"),
    )


class BloodTrackingNotification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blood_tracking_notifications"

    tracking_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blood_donor_tracking_sessions.id"),
        nullable=False,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blood_requests.id"), nullable=False
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_tracking_notif_recipient", "recipient_user_id", "is_read"),
        Index("ix_tracking_notif_request", "request_id"),
    )
