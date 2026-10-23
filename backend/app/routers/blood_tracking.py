from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models import BloodTrackingNotification, RoleName, User
from app.schemas.blood_tracking import (
    LocationUpdateRequest,
    StartTrackingRequest,
    StopTrackingRequest,
    TrackingNotificationResponse,
    TrackingSessionResponse,
)
from app.services import blood_tracking

router = APIRouter(prefix="/requests/{request_id}/tracking", tags=["blood donor tracking"])


@router.get("", response_model=TrackingSessionResponse)
def get_donor_tracking_status(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TrackingSessionResponse:
    """Retrieve live tracking status and ETA for an authorized blood request.

    Accessible by:
    - The request creator (requester)
    - The assigned/accepted donor
    - Verified blood bank staff for the request organisation
    - System administrators
    """
    return blood_tracking.get_tracking_session_for_user(db, request_id, user)


@router.post("/start", response_model=TrackingSessionResponse)
def start_donor_location_sharing(
    request_id: UUID,
    payload: StartTrackingRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> TrackingSessionResponse:
    """Donor starts live location sharing after explicit consent."""
    blood_tracking.start_location_sharing(db, request_id, user, payload)
    db.commit()
    return blood_tracking.get_tracking_session_for_user(db, request_id, user)


@router.post("/location", response_model=TrackingSessionResponse)
def update_donor_location(
    request_id: UUID,
    payload: LocationUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> TrackingSessionResponse:
    """Donor sends periodic GPS coordinate updates."""
    blood_tracking.update_donor_location(db, request_id, user, payload)
    db.commit()
    return blood_tracking.get_tracking_session_for_user(db, request_id, user)


@router.post("/stop", response_model=TrackingSessionResponse)
def stop_donor_location_sharing(
    request_id: UUID,
    payload: StopTrackingRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> TrackingSessionResponse:
    """Donor halts live location sharing."""
    blood_tracking.stop_location_sharing(db, request_id, user, payload.reason)
    db.commit()
    return blood_tracking.get_tracking_session_for_user(db, request_id, user)


@router.post("/arrive", response_model=TrackingSessionResponse)
def mark_donor_arrived(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR, RoleName.BLOOD_BANK, RoleName.ADMIN))],
) -> TrackingSessionResponse:
    """Mark donor as arrived at destination hospital."""
    blood_tracking.mark_donor_arrived(db, request_id, user)
    db.commit()
    return blood_tracking.get_tracking_session_for_user(db, request_id, user)


@router.get("/notifications", response_model=list[TrackingNotificationResponse])
def list_tracking_notifications(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[TrackingNotificationResponse]:
    """Fetch tracking notifications for this request and authenticated recipient."""
    notifications = db.scalars(
        select(BloodTrackingNotification)
        .where(
            BloodTrackingNotification.request_id == request_id,
            BloodTrackingNotification.recipient_user_id == user.id,
        )
        .order_by(BloodTrackingNotification.created_at.desc())
    ).all()
    return [
        TrackingNotificationResponse.model_validate(n, from_attributes=True)
        for n in notifications
    ]
