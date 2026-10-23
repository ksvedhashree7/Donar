from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BloodDonorProfile,
    BloodDonorTrackingSession,
    BloodOrganisation,
    BloodRequest,
    BloodRequestReservation,
    BloodTrackingNotification,
    RoleName,
    User,
)
from app.schemas.blood_tracking import (
    LocationUpdateRequest,
    StartTrackingRequest,
    TrackingSessionResponse,
)
from app.services import google_maps
from app.services.audit import record_audit_event

logger = logging.getLogger(__name__)

# Default coordinates if facility coordinates are unspecified (Adyar, Chennai)
DEFAULT_HOSPITAL_LAT = 13.0067
DEFAULT_HOSPITAL_LON = 80.2570

STALE_LOCATION_THRESHOLD_SECONDS = 120.0  # 2 minutes without updates = stale


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    db: Session,
    actor: User | None,
    action: str,
    resource_id: str | None,
) -> None:
    record_audit_event(
        db,
        actor_id=actor.id if actor else None,
        actor_role=actor.role.name.value if actor else "SYSTEM",
        action=action,
        resource_type="blood_donor_tracking",
        resource_id=resource_id,
        purpose="live_donor_tracking",
        ip_address=None,
        user_agent=None,
        success=True,
    )


def create_tracking_notification(
    db: Session,
    tracking_session_id: UUID,
    request_id: UUID,
    recipient_user_id: UUID,
    event_type: str,
    title: str,
    message: str,
) -> BloodTrackingNotification:
    notification = BloodTrackingNotification(
        tracking_session_id=tracking_session_id,
        request_id=request_id,
        recipient_user_id=recipient_user_id,
        event_type=event_type,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notification)
    db.flush()
    return notification


def create_or_get_tracking_session(
    db: Session,
    request: BloodRequest,
    reservation: BloodRequestReservation,
    donor: BloodDonorProfile,
) -> BloodDonorTrackingSession:
    existing = db.scalar(
        select(BloodDonorTrackingSession).where(
            BloodDonorTrackingSession.reservation_id == reservation.id
        )
    )
    if existing is not None:
        return existing

    dest_lat = (
        float(request.approx_latitude)
        if request.approx_latitude is not None
        else DEFAULT_HOSPITAL_LAT
    )
    dest_lon = (
        float(request.approx_longitude)
        if request.approx_longitude is not None
        else DEFAULT_HOSPITAL_LON
    )

    session = BloodDonorTrackingSession(
        request_id=request.id,
        reservation_id=reservation.id,
        donor_id=donor.id,
        status="WAITING_FOR_SHARING",
        destination_facility=request.facility,
        destination_locality=request.locality,
        destination_latitude=dest_lat,
        destination_longitude=dest_lon,
    )
    db.add(session)
    db.flush()

    # Notify the requester that a donor accepted
    create_tracking_notification(
        db=db,
        tracking_session_id=session.id,
        request_id=request.id,
        recipient_user_id=request.requester_user_id,
        event_type="DONOR_ACCEPTED",
        title="Donor accepted request",
        message=f"A willing donor has accepted request {request.public_id}. Waiting for donor to start live location sharing.",
    )

    _audit(db, None, "TRACKING_SESSION_INITIALIZED", str(session.id))
    return session


def _get_active_session_for_donor(
    db: Session, request_id: UUID, donor_user: User
) -> tuple[BloodRequest, BloodDonorTrackingSession, BloodRequestReservation]:
    request = db.get(BloodRequest, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blood request not found"
        )

    donor_profile = db.scalar(
        select(BloodDonorProfile).where(BloodDonorProfile.user_id == donor_user.id)
    )
    if donor_profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Donor profile not found"
        )

    reservation = db.scalar(
        select(BloodRequestReservation).where(
            BloodRequestReservation.request_id == request.id,
            BloodRequestReservation.donor_id == donor_profile.id,
            BloodRequestReservation.status == "ACTIVE",
        )
    )
    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active reservation found for this donor and request",
        )

    session = db.scalar(
        select(BloodDonorTrackingSession).where(
            BloodDonorTrackingSession.reservation_id == reservation.id
        )
    )
    if session is None:
        session = create_or_get_tracking_session(db, request, reservation, donor_profile)

    return request, session, reservation


def start_location_sharing(
    db: Session,
    request_id: UUID,
    user: User,
    payload: StartTrackingRequest,
) -> BloodDonorTrackingSession:
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit donor consent is required before starting live location sharing.",
        )

    request, session, _ = _get_active_session_for_donor(db, request_id, user)

    if session.status in {"ARRIVED", "CANCELLED", "STOPPED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tracking cannot be started because session is in {session.status} state.",
        )

    now = _now()
    session.consent_granted_at = now
    session.status = "SHARING"
    session.stop_reason = None
    session.stopped_at = None

    if payload.latitude is not None and payload.longitude is not None:
        session.current_latitude = payload.latitude
        session.current_longitude = payload.longitude
        session.current_accuracy_meters = payload.accuracy_meters
        session.last_location_at = now

        dest_lat = float(session.destination_latitude or DEFAULT_HOSPITAL_LAT)
        dest_lon = float(session.destination_longitude or DEFAULT_HOSPITAL_LON)
        route = google_maps.calculate_route(
            payload.latitude, payload.longitude, dest_lat, dest_lon
        )
        session.estimated_distance_meters = route.distance_meters
        session.estimated_duration_seconds = route.duration_seconds
        session.estimated_arrival_at = now + timedelta(seconds=route.duration_seconds)
        session.route_distance_text = route.distance_text
        session.route_duration_text = route.duration_text
        session.encoded_polyline = route.encoded_polyline

    create_tracking_notification(
        db=db,
        tracking_session_id=session.id,
        request_id=request.id,
        recipient_user_id=request.requester_user_id,
        event_type="LOCATION_SHARING_STARTED",
        title="Donor is on the way",
        message=f"The donor for request {request.public_id} has started live location sharing.",
    )

    _audit(db, user, "LOCATION_SHARING_STARTED", str(session.id))
    return session


def update_donor_location(
    db: Session,
    request_id: UUID,
    user: User,
    payload: LocationUpdateRequest,
) -> BloodDonorTrackingSession:
    request, session, _ = _get_active_session_for_donor(db, request_id, user)

    if session.status in {"ARRIVED", "CANCELLED", "STOPPED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update location: tracking session is in {session.status} state.",
        )

    now = _now()
    session.current_latitude = payload.latitude
    session.current_longitude = payload.longitude
    session.current_accuracy_meters = payload.accuracy_meters
    session.last_location_at = now
    session.status = "SHARING"

    dest_lat = float(session.destination_latitude or DEFAULT_HOSPITAL_LAT)
    dest_lon = float(session.destination_longitude or DEFAULT_HOSPITAL_LON)

    prev_duration = session.estimated_duration_seconds
    route = google_maps.calculate_route(
        payload.latitude, payload.longitude, dest_lat, dest_lon
    )

    session.estimated_distance_meters = route.distance_meters
    session.estimated_duration_seconds = route.duration_seconds
    session.estimated_arrival_at = now + timedelta(seconds=route.duration_seconds)
    session.route_distance_text = route.distance_text
    session.route_duration_text = route.duration_text
    session.encoded_polyline = route.encoded_polyline

    # If ETA changed materially (>= 5 minutes delta), notify requester
    if prev_duration is not None and abs(route.duration_seconds - prev_duration) >= 300:
        create_tracking_notification(
            db=db,
            tracking_session_id=session.id,
            request_id=request.id,
            recipient_user_id=request.requester_user_id,
            event_type="ETA_CHANGED",
            title="Donor ETA updated",
            message=f"Updated arrival estimate for request {request.public_id}: {route.duration_text} ({route.distance_text} away).",
        )

    return session


def stop_location_sharing(
    db: Session,
    request_id: UUID,
    user: User,
    reason: str | None = None,
) -> BloodDonorTrackingSession:
    request, session, _ = _get_active_session_for_donor(db, request_id, user)

    now = _now()
    session.status = "STOPPED"
    session.stopped_at = now
    session.stop_reason = reason or "Stopped by donor"

    # Privacy protection: clear live coordinate cache upon stop
    session.current_latitude = None
    session.current_longitude = None
    session.current_accuracy_meters = None

    create_tracking_notification(
        db=db,
        tracking_session_id=session.id,
        request_id=request.id,
        recipient_user_id=request.requester_user_id,
        event_type="LOCATION_SHARING_STOPPED",
        title="Live tracking ended",
        message=f"The donor has stopped live location sharing for request {request.public_id}.",
    )

    _audit(db, user, "LOCATION_SHARING_STOPPED", str(session.id))
    return session


def mark_donor_arrived(
    db: Session,
    request_id: UUID,
    user: User,
) -> BloodDonorTrackingSession:
    request, session, _ = _get_active_session_for_donor(db, request_id, user)

    now = _now()
    session.status = "ARRIVED"
    session.arrived_at = now
    session.estimated_duration_seconds = 0
    session.estimated_distance_meters = 0
    session.route_duration_text = "Arrived"
    session.route_distance_text = "0 m"

    create_tracking_notification(
        db=db,
        tracking_session_id=session.id,
        request_id=request.id,
        recipient_user_id=request.requester_user_id,
        event_type="DONOR_ARRIVED",
        title="Donor has arrived!",
        message=f"The donor has arrived at {session.destination_facility} for request {request.public_id}.",
    )

    _audit(db, user, "DONOR_MARKED_ARRIVED", str(session.id))
    return session


def get_tracking_session_for_user(
    db: Session,
    request_id: UUID,
    user: User,
) -> TrackingSessionResponse:
    request = db.get(BloodRequest, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blood request not found"
        )

    # Authorization verification:
    # 1. Requester of the blood request
    # 2. Staff of verified organisation owning the request
    # 3. System Administrator
    # 4. The accepted donor for an active reservation
    is_requester = request.requester_user_id == user.id
    is_admin = user.role.name == RoleName.ADMIN

    donor_profile = db.scalar(
        select(BloodDonorProfile).where(BloodDonorProfile.user_id == user.id)
    )
    is_donor = False
    if donor_profile is not None:
        donor_reservation = db.scalar(
            select(BloodRequestReservation).where(
                BloodRequestReservation.request_id == request.id,
                BloodRequestReservation.donor_id == donor_profile.id,
            )
        )
        if donor_reservation is not None:
            is_donor = True

    is_bank_staff = False
    if user.role.name == RoleName.BLOOD_BANK and request.organisation_id:
        from app.models import BloodBankStaff

        staff = db.scalar(
            select(BloodBankStaff).where(
                BloodBankStaff.user_id == user.id,
                BloodBankStaff.organisation_id == request.organisation_id,
                BloodBankStaff.is_active.is_(True),
            )
        )
        if staff is not None:
            is_bank_staff = True

    if not (is_requester or is_admin or is_donor or is_bank_staff):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking information not found or access denied.",
        )

    # Fetch active or most recent tracking session
    session = db.scalar(
        select(BloodDonorTrackingSession)
        .where(BloodDonorTrackingSession.request_id == request.id)
        .order_by(BloodDonorTrackingSession.created_at.desc())
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live tracking session exists for this request.",
        )

    reservation = db.get(BloodRequestReservation, session.reservation_id)
    contact_shared = bool(reservation and reservation.contact_shared)

    donor_phone = None
    if contact_shared and (is_requester or is_admin or is_bank_staff):
        donor = db.get(BloodDonorProfile, session.donor_id)
        donor_user_rec = db.get(User, donor.user_id) if donor else None
        if donor_user_rec and donor_user_rec.phone_verified_at:
            donor_phone = donor_user_rec.phone

    donor_code = f"DNR-{str(session.donor_id).split('-')[0].upper()}"

    now = _now()
    is_stale = False
    if session.status == "SHARING" and session.last_location_at:
        delta = (now - session.last_location_at).total_seconds()
        if delta > STALE_LOCATION_THRESHOLD_SECONDS:
            is_stale = True

    _audit(db, user, "TRACKING_SESSION_VIEWED", str(session.id))

    return TrackingSessionResponse(
        session_id=session.id,
        request_id=session.request_id,
        public_request_id=request.public_id,
        status=session.status,
        donor_code=donor_code,
        destination_facility=session.destination_facility,
        destination_locality=session.destination_locality,
        destination_latitude=float(session.destination_latitude)
        if session.destination_latitude is not None
        else None,
        destination_longitude=float(session.destination_longitude)
        if session.destination_longitude is not None
        else None,
        current_latitude=float(session.current_latitude)
        if session.current_latitude is not None
        else None,
        current_longitude=float(session.current_longitude)
        if session.current_longitude is not None
        else None,
        current_accuracy_meters=float(session.current_accuracy_meters)
        if session.current_accuracy_meters is not None
        else None,
        last_location_at=session.last_location_at,
        estimated_distance_meters=session.estimated_distance_meters,
        estimated_duration_seconds=session.estimated_duration_seconds,
        estimated_arrival_at=session.estimated_arrival_at,
        route_distance_text=session.route_distance_text,
        route_duration_text=session.route_duration_text,
        encoded_polyline=session.encoded_polyline,
        is_stale=is_stale,
        is_fallback_routing=False,
        routing_source="google_maps" if session.encoded_polyline else "standard_road_model",
        contact_shared=contact_shared,
        donor_phone=donor_phone,
        arrived_at=session.arrived_at,
        stopped_at=session.stopped_at,
    )
