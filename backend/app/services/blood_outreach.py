from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BloodDonationRecord,
    BloodDonorMatch,
    BloodDonorProfile,
    BloodNotification,
    BloodNotificationResponse,
    BloodOutreachBatch,
    BloodRequest,
    BloodRequestReservation,
    BloodRequestStatusHistory,
    BloodRequestVerification,
    RoleName,
    User,
)
from app.services.blood_compatibility import compatible_donor_groups, is_rbc_group_compatible

RADIUS_STAGES = ((0, 5, 120), (5, 10, 120), (10, 15, 120), (15, 20, 120), (20, 20016, 120))
RESERVATION_GRACE_PERIOD = timedelta(minutes=2)
AVAILABILITY_MAX_AGE = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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


def _set_status(
    db: Session,
    request: BloodRequest,
    actor: User | None,
    new_status: str,
    reason: str | None = None,
) -> None:
    previous_status = request.status
    request.status = new_status
    db.add(
        BloodRequestStatusHistory(
            request_id=request.id,
            actor_user_id=actor.id if actor else None,
            previous_status=previous_status,
            status=new_status,
            reason=reason,
        )
    )
    _audit(
        db,
        actor.id if actor else None,
        f"REQUEST_{new_status}",
        "blood_request",
        request.public_id,
    )


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


def _active_reservation_count(db: Session, request_id: UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(BloodRequestReservation)
            .where(
                BloodRequestReservation.request_id == request_id,
                BloodRequestReservation.status == "ACTIVE",
            )
        )
        or 0
    )


def _start_stage(db: Session, request: BloodRequest, actor: User | None, stage: int) -> int:
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
    if actor is not None and actor.role.name != RoleName.GENERAL_DONOR:
        request.assigned_staff_user_id = actor.id
    request.status = "OUTREACH_ACTIVE"
    donor_groups = compatible_donor_groups(request.blood_group, request.component)
    if not donor_groups:
        return 0
    donor_query = select(BloodDonorProfile).where(
        BloodDonorProfile.blood_group.in_(donor_groups),
        BloodDonorProfile.blood_group_verified_at.is_not(None),
        BloodDonorProfile.screening_completed_at.is_not(None),
        BloodDonorProfile.availability == "AVAILABLE",
        BloodDonorProfile.notification_consent.is_(True),
        BloodDonorProfile.last_confirmed_at >= now - AVAILABILITY_MAX_AGE,
        BloodDonorProfile.approx_latitude.is_not(None),
        BloodDonorProfile.approx_longitude.is_not(None),
    )
    if request.organisation_id is not None:
        donor_query = donor_query.where(
            BloodDonorProfile.blood_group_verification_organisation_id == request.organisation_id
        )
    donors = db.scalars(donor_query).all()
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
        notification = BloodNotification(
            request_id=request.id,
            donor_id=donor.id,
            donor_blood_group=donor.blood_group,
            batch_id=batch.id,
            status="SENT",
            sent_at=now,
        )
        db.add_all((match, notification))
        sent_count += 1
    db.flush()
    _audit(
        db,
        actor.id if actor else None,
        "OUTREACH_STAGE_STARTED",
        "blood_request",
        request.public_id,
    )
    return sent_count


def verify_request(db: Session, request: BloodRequest, actor: User, decision: str, notes: str | None) -> None:
    if request.status != "PENDING_VERIFICATION":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request is not awaiting verification")
    db.add(BloodRequestVerification(request_id=request.id, reviewer_user_id=actor.id, decision=decision, notes=notes))
    request.assigned_staff_user_id = actor.id
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
    if request.component != "RED_CELLS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Component-specific donor matching is not configured for this component",
        )
    if _as_utc(request.required_by) <= _now():
        _set_status(db, request, actor, "EXPIRED", "Required-by time has passed")
        return 0
    _set_status(db, request, actor, "OUTREACH_ACTIVE")
    return _start_stage(db, request, actor, 0)


def record_response(
    db: Session,
    notification: BloodNotification,
    actor: User,
    response: str,
    *,
    contact_shared: bool = False,
) -> BloodRequestReservation | None:
    request = db.scalar(
        select(BloodRequest)
        .where(BloodRequest.id == notification.request_id)
        .with_for_update()
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    notification = db.scalar(
        select(BloodNotification)
        .where(BloodNotification.id == notification.id)
        .with_for_update()
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    donor = db.get(BloodDonorProfile, notification.donor_id)
    if donor is None or donor.user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if not request.outreach_active or notification.status != "SENT":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This alert is no longer active")
    batch = db.get(BloodOutreachBatch, notification.batch_id)
    if batch is None or _as_utc(batch.expires_at) <= _now():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The response window has closed")
    if response == "ACCEPTED" and (
        request.component != "RED_CELLS"
        or donor.blood_group_verified_at is None
        or donor.screening_completed_at is None
        or (
            request.organisation_id is not None
            and donor.blood_group_verification_organisation_id != request.organisation_id
        )
        or not is_rbc_group_compatible(donor.blood_group, request.blood_group)
        or donor.availability != "AVAILABLE"
        or not donor.notification_consent
        or donor.last_confirmed_at is None
        or _as_utc(donor.last_confirmed_at) < _now() - AVAILABILITY_MAX_AGE
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Donor no longer meets the potential-match criteria",
        )
    unit_number = None
    reservation = None
    if response == "ACCEPTED":
        occupied_units = set(
            db.scalars(
                select(BloodRequestReservation.unit_number).where(
                    BloodRequestReservation.request_id == request.id,
                    BloodRequestReservation.status == "ACTIVE",
                )
            ).all()
        )
        unit_number = next(
            (
                candidate
                for candidate in range(1, request.required_donors + 1)
                if candidate not in occupied_units
            ),
            None,
        )
        if unit_number is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="All requested units have already been reserved",
            )
    notification.status = response
    db.add(BloodNotificationResponse(notification_id=notification.id, response=response))
    if response == "ACCEPTED":
        reserved_at = _now()
        reservation = BloodRequestReservation(
            request_id=request.id,
            donor_id=donor.id,
            unit_number=unit_number,
            status="ACTIVE",
            contact_shared=contact_shared,
            reserved_at=reserved_at,
            grace_until=reserved_at + RESERVATION_GRACE_PERIOD,
        )
        db.add(reservation)
    db.flush()
    _audit(db, actor.id, f"DONOR_{response}", "blood_notification", str(notification.id))
    if response == "ACCEPTED":
        accepted = _active_reservation_count(db, request.id)
        if accepted >= request.required_donors:
            _cancel_pending(db, request)
            _set_status(db, request, actor, "COORDINATION", "All requested donor units are reserved")
    db.flush()
    return reservation


def cancel_reservation(db: Session, reservation_id: UUID, actor: User, reason: str) -> None:
    reservation = db.get(BloodRequestReservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    request = db.scalar(
        select(BloodRequest)
        .where(BloodRequest.id == reservation.request_id)
        .with_for_update()
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    reservation = db.scalar(
        select(BloodRequestReservation)
        .where(BloodRequestReservation.id == reservation_id)
        .with_for_update()
    )
    if reservation is None or reservation.donor_id != db.scalar(
        select(BloodDonorProfile.id).where(BloodDonorProfile.user_id == actor.id)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    if reservation.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reservation is no longer active")
    now = _now()
    if _as_utc(reservation.grace_until) <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The cancellation grace period has ended",
        )

    reservation.status = "CANCELLED"
    reservation.cancelled_at = now
    reservation.cancellation_reason = reason
    _audit(db, actor.id, "DONOR_RESERVATION_CANCELLED", "blood_request", request.public_id)
    db.add(
        BloodRequestStatusHistory(
            request_id=request.id,
            actor_user_id=actor.id,
            previous_status=request.status,
            status="OUTREACH_ACTIVE",
            reason="A reserved donor unit was released",
        )
    )
    if _as_utc(request.required_by) <= now:
        _set_status(db, request, actor, "EXPIRED", "Required-by time passed after cancellation")
        _cancel_pending(db, request)
        return
    request.status = "OUTREACH_ACTIVE"
    if not request.outreach_active:
        _start_stage(db, request, actor, max(request.current_stage, 0))


def revoke_contact_sharing(db: Session, reservation_id: UUID, actor: User) -> None:
    reservation = db.get(BloodRequestReservation, reservation_id)
    donor_id = db.scalar(
        select(BloodDonorProfile.id).where(BloodDonorProfile.user_id == actor.id)
    )
    if reservation is None or reservation.donor_id != donor_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    if reservation.contact_shared:
        reservation.contact_shared = False
        _audit(
            db,
            actor.id,
            "DONOR_CONTACT_SHARING_REVOKED",
            "blood_request_reservation",
            str(reservation.id),
        )


def report_completion(
    db: Session,
    request_id: UUID,
    reservation_id: UUID,
    actor: User,
    *,
    component: str,
    quantity_ml: int | None,
) -> BloodDonationRecord:
    request = db.scalar(
        select(BloodRequest).where(BloodRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    reservation = db.scalar(
        select(BloodRequestReservation)
        .where(
            BloodRequestReservation.id == reservation_id,
            BloodRequestReservation.request_id == request_id,
        )
        .with_for_update()
    )
    donor = db.get(BloodDonorProfile, reservation.donor_id) if reservation else None
    if reservation is None or donor is None or donor.user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    if reservation.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reservation is no longer active")
    if request.status not in {"COORDINATION", "COMPLETED_PENDING_VERIFICATION", "OUTREACH_ACTIVE"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request cannot accept a completion report")

    record = db.scalar(
        select(BloodDonationRecord)
        .where(BloodDonationRecord.reservation_id == reservation.id)
        .with_for_update()
    )
    now = _now()
    if record is not None:
        if record.status != "CORRECTION_REQUIRED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A completion report already exists for this reservation",
            )
        record.component = component
        record.quantity_ml = quantity_ml
        record.status = "PENDING_VERIFICATION"
        record.reported_by_user_id = actor.id
        record.reported_at = now
        record.verified_by_user_id = None
        record.verified_at = None
        record.verification_notes = None
    else:
        record = BloodDonationRecord(
            request_id=request.id,
            reservation_id=reservation.id,
            reported_by_user_id=actor.id,
            component=component,
            quantity_ml=quantity_ml,
            status="PENDING_VERIFICATION",
            reported_at=now,
        )
        db.add(record)
    db.flush()

    active_reservations = db.scalars(
        select(BloodRequestReservation).where(
            BloodRequestReservation.request_id == request.id,
            BloodRequestReservation.status == "ACTIVE",
        )
    ).all()
    reported_reservation_ids = set(
        db.scalars(
            select(BloodDonationRecord.reservation_id).where(
                BloodDonationRecord.request_id == request.id,
                BloodDonationRecord.status.in_(("PENDING_VERIFICATION", "VERIFIED")),
            )
        ).all()
    )
    if (
        len(active_reservations) >= request.required_donors
        and all(item.id in reported_reservation_ids for item in active_reservations)
    ):
        _set_status(
            db,
            request,
            actor,
            "COMPLETED_PENDING_VERIFICATION",
            "All reserved donor units reported completion",
        )
    _audit(db, actor.id, "DONATION_COMPLETION_REPORTED", "blood_donation_record", str(record.id))
    return record


def verify_completion(
    db: Session,
    request_id: UUID,
    record_id: UUID,
    actor: User,
    *,
    decision: str,
    notes: str | None,
) -> BloodDonationRecord:
    request = db.scalar(
        select(BloodRequest).where(BloodRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    record = db.scalar(
        select(BloodDonationRecord)
        .where(
            BloodDonationRecord.id == record_id,
            BloodDonationRecord.request_id == request_id,
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Completion report not found")
    if record.status != "PENDING_VERIFICATION":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completion report is not pending")

    reservation = db.get(BloodRequestReservation, record.reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reservation record is missing")
    record.verification_notes = notes
    if decision == "VERIFY":
        record.status = "VERIFIED"
        record.verified_by_user_id = actor.id
        record.verified_at = _now()
        reservation.status = "COMPLETED"
    else:
        record.status = "CORRECTION_REQUIRED"
        _set_status(
            db,
            request,
            actor,
            "COORDINATION",
            "Completion report needs correction",
        )
    db.flush()
    _audit(
        db,
        actor.id,
        f"DONATION_COMPLETION_{decision}",
        "blood_donation_record",
        str(record.id),
    )

    if decision == "VERIFY":
        reservations = db.scalars(
            select(BloodRequestReservation).where(
                BloodRequestReservation.request_id == request.id,
                BloodRequestReservation.status != "CANCELLED",
            )
        ).all()
        if reservations and all(item.status == "COMPLETED" for item in reservations):
            request.fulfilled_at = _now()
            _set_status(
                db,
                request,
                actor,
                "FULFILLED",
                "All recorded donation outcomes were institution-confirmed",
            )
        elif request.status != "COMPLETED_PENDING_VERIFICATION":
            request.status = "COMPLETED_PENDING_VERIFICATION"
    return record


def advance_outreach(db: Session, request: BloodRequest, actor: User | None) -> int:
    if not request.outreach_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Outreach is not active")
    if request.component != "RED_CELLS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Component-specific donor matching is not configured for this component",
        )
    if _as_utc(request.required_by) <= _now():
        _cancel_pending(db, request)
        _set_status(db, request, actor, "EXPIRED", "Required-by time has passed")
        return 0
    current = db.scalar(
        select(BloodOutreachBatch)
        .where(
            BloodOutreachBatch.request_id == request.id,
            BloodOutreachBatch.stage == request.current_stage,
            BloodOutreachBatch.status == "ACTIVE",
        )
        .order_by(BloodOutreachBatch.started_at.desc())
        .limit(1)
    )
    if current is None or _as_utc(current.expires_at) > _now():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current response window has not ended")
    accepted = _active_reservation_count(db, request.id)
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
    if final_status == "FULFILLED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A request cannot be fulfilled without institution-confirmed completion",
        )
    if request.status in {"FULFILLED", "CANCELLED", "EXPIRED"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request is already closed")
    _cancel_pending(db, request)
    _set_status(db, request, actor, final_status, reason)
    if final_status == "FULFILLED":
        request.fulfilled_at = _now()