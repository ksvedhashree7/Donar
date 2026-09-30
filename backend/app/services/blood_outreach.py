from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BloodDonorMatch,
    BloodDonorProfile,
    BloodNotification,
    BloodNotificationResponse,
    BloodOutreachBatch,
    BloodRequest,
    BloodRequestStatusHistory,
    BloodRequestVerification,
    User,
)

RADIUS_STAGES = ((0, 5, 180), (5, 10, 180), (10, 15, 240), (15, 25, 300))
AVAILABILITY_MAX_AGE = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _distance_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    earth_radius_km = 6371.0
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    lat_delta = math.radians(latitude_b - latitude_a)
    lon_delta = math.radians(longitude_b - longitude_a)
    haversine = math.sin(lat_delta / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(lon_delta / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(haversine))


def _audit(db: Session, actor_id: UUID | None, action: str, resource_type: str, resource_id: str | None) -> None:
    from app.services.audit import record_audit_event

    actor = db.get(User, actor_id) if actor_id else None
    record_audit_event(
        db,
        actor_id=actor_id,
        actor_role=actor.role.name.value if actor else "SYSTEM",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        purpose=None,
        ip_address=None,
        user_agent=None,
        success=True,
    )


def _set_status(db: Session, request: BloodRequest, actor: User, new_status: str, reason: str | None = None) -> None:
    previous_status = request.status
    request.status = new_status
    db.add(BloodRequestStatusHistory(request_id=request.id, actor_user_id=actor.id, previous_status=previous_status, status=new_status, reason=reason))
    _audit(db, actor.id, f"REQUEST_{new_status}", "blood_request", request.public_id)


def _request_or_404(db: Session, request_id: UUID) -> BloodRequest:
    request = db.get(BloodRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def _response_counts(db: Session, request_id: UUID) -> tuple[int, int, int]:
    responses = db.execute(
        select(BloodNotificationResponse.response, func.count())
        .join(BloodNotification, BloodNotification.id == BloodNotificationResponse.notification_id)
        .where(BloodNotification.request_id == request_id)
        .group_by(BloodNotificationResponse.response)
    ).all()
    counts = {response: count for response, count in responses}
    return counts.get("ACCEPTED", 0), counts.get("DECLINED", 0), counts.get("NO_RESPONSE", 0)


def _cancel_pending(db: Session, request: BloodRequest) -> None:
    now = _now()
    pending = db.scalars(
        select(BloodNotification).where(
            BloodNotification.request_id == request.id,
            BloodNotification.status.in_(("QUEUED", "SENT")),
        )
    ).all()
    for notification in pending:
        has_response = db.scalar(
            select(BloodNotificationResponse.id).where(BloodNotificationResponse.notification_id == notification.id)
        )
        if not has_response:
            notification.status = "CANCELLED"
            notification.cancelled_at = now
    batches = db.scalars(
        select(BloodOutreachBatch).where(BloodOutreachBatch.request_id == request.id, BloodOutreachBatch.status == "ACTIVE")
    ).all()
    for batch in batches:
        batch.status = "STOPPED"
    request.outreach_active = False


def _start_stage(db: Session, request: BloodRequest, actor: User, stage: int) -> int:
    minimum, maximum, duration = RADIUS_STAGES[stage]
    now = _now()
    batch = BloodOutreachBatch(
        request_id=request.id,
        stage=stage,
        radius_min_km=minimum,
        radius_max_km=maximum,
        duration_seconds=duration,
        started_at=now,
        expires_at=now + timedelta(seconds=duration),
        status="ACTIVE",
    )
    db.add(batch)
    db.flush()
    request.current_stage = stage
    request.outreach_active = True
    request.coordinator_user_id = actor.id
    request.status = "OUTREACH_ACTIVE"
    donors = db.scalars(
        select(BloodDonorProfile).where(
            BloodDonorProfile.blood_group == request.blood_group,
            BloodDonorProfile.availability == "AVAILABLE",
            BloodDonorProfile.notification_consent.is_(True),
            BloodDonorProfile.last_confirmed_at >= now - AVAILABILITY_MAX_AGE,
            BloodDonorProfile.approx_latitude.is_not(None),
            BloodDonorProfile.approx_longitude.is_not(None),
        )
    ).all()
    sent_count = 0
    for donor in donors:
        existing = db.scalar(
            select(BloodNotification.id).where(
                BloodNotification.request_id == request.id,
                BloodNotification.donor_id == donor.id,
            )
        )
        if existing:
            continue
        distance = _distance_km(
            float(request.approx_latitude),
            float(request.approx_longitude),
            float(donor.approx_latitude),
            float(donor.approx_longitude),
        )
        if not minimum <= distance <= maximum:
            continue
        match = BloodDonorMatch(request_id=request.id, donor_id=donor.id, distance_km=round(distance, 2), stage=stage)
        notification = BloodNotification(request_id=request.id, donor_id=donor.id, batch_id=batch.id, status="SENT", sent_at=now)
        db.add_all((match, notification))
        sent_count += 1
    _audit(db, actor.id, "OUTREACH_STAGE_STARTED", "blood_request", request.public_id)
    return sent_count


def verify_request(db: Session, request: BloodRequest, actor: User, decision: str, notes: str | None) -> None:
    if request.status != "PENDING_VERIFICATION":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request is not awaiting verification")
    db.add(BloodRequestVerification(request_id=request.id, reviewer_user_id=actor.id, decision=decision, notes=notes))
    request.coordinator_user_id = actor.id
    if decision == "VERIFY":
        request.verified_by_user_id = actor.id
        request.verified_at = _now()
        _set_status(db, request, actor, "VERIFIED", notes)
    elif decision == "REJECT":
        _set_status(db, request, actor, "REJECTED", notes)
    else:
        _set_status(db, request, actor, "CLARIFICATION_REQUIRED", notes)


def start_outreach(db: Session, request: BloodRequest, actor: User) -> int:
    if request.status != "VERIFIED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only verified requests can start outreach")
    if request.required_by <= _now():
        _set_status(db, request, actor, "EXPIRED", "Required-by time has passed")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request has expired")
    _set_status(db, request, actor, "OUTREACH_ACTIVE")
    return _start_stage(db, request, actor, 0)


def record_response(db: Session, notification: BloodNotification, actor: User, response: str) -> None:
    request = _request_or_404(db, notification.request_id)
    donor = db.get(BloodDonorProfile, notification.donor_id)
    if donor is None or donor.user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if not request.outreach_active or notification.status != "SENT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This alert is no longer active")
    batch = db.get(BloodOutreachBatch, notification.batch_id)
    if batch is None or batch.expires_at <= _now():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The response window has closed")
    notification.status = response
    db.add(BloodNotificationResponse(notification_id=notification.id, response=response))
    db.flush()
    _audit(db, actor.id, f"DONOR_{response}", "blood_notification", str(notification.id))
    if response == "ACCEPTED":
        accepted, _, _ = _response_counts(db, request.id)
        if accepted >= request.required_donors:
            _cancel_pending(db, request)
            request.status = "COORDINATION"
            _audit(db, actor.id, "OUTREACH_STOPPED_THRESHOLD", "blood_request", request.public_id)


def advance_outreach(db: Session, request: BloodRequest, actor: User) -> int:
    if not request.outreach_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Outreach is not active")
    current = db.scalar(
        select(BloodOutreachBatch).where(BloodOutreachBatch.request_id == request.id, BloodOutreachBatch.stage == request.current_stage)
    )
    if current is None or current.expires_at > _now():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current response window has not ended")
    accepted, _, _ = _response_counts(db, request.id)
    if accepted >= request.required_donors:
        _cancel_pending(db, request)
        request.status = "COORDINATION"
        return 0
    _cancel_pending(db, request)
    current.status = "COMPLETED"
    next_stage = request.current_stage + 1
    if next_stage >= len(RADIUS_STAGES):
        _set_status(db, request, actor, "OUTREACH_EXHAUSTED", "All configured radius stages completed")
        return 0
    return _start_stage(db, request, actor, next_stage)


def stop_outreach(db: Session, request: BloodRequest, actor: User, final_status: str, reason: str | None = None) -> None:
    if request.status in {"FULFILLED", "CANCELLED", "EXPIRED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request is already closed")
    _cancel_pending(db, request)
    _set_status(db, request, actor, final_status, reason)
    if final_status == "FULFILLED":
        request.fulfilled_at = _now()