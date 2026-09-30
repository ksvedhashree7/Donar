from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models import (
    BloodDonorMatch,
    BloodDonorProfile,
    BloodNotification,
    BloodNotificationResponse,
    BloodOutreachBatch,
    BloodRequest,
    RoleName,
    User,
)
from app.schemas.blood import (
    BloodRequestCreate,
    BloodRequestResponse,
    DashboardStats,
    DonorEmergencyAlertResponse,
    DonorAvailabilityUpdate,
    DonorMatchResponse,
    DonorProfileCreate,
    DonorProfileResponse,
    MessageResponse,
    OutreachResponse,
    VerificationDecision,
)
from app.services import blood_outreach

router = APIRouter(tags=["blood coordination"])
COORDINATOR_ROLES = (RoleName.COORDINATOR, RoleName.ADMIN)


def _get_request(db: Session, request_id: UUID, actor: User) -> BloodRequest:
    request = db.get(BloodRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if actor.role.name not in COORDINATOR_ROLES and request.requester_user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def _request_response(request: BloodRequest) -> BloodRequestResponse:
    return BloodRequestResponse(
        id=request.id,
        public_id=request.public_id,
        facility=request.facility,
        locality=request.locality,
        blood_group=request.blood_group,
        required_donors=request.required_donors,
        required_by=request.required_by,
        urgency=request.urgency,
        status=request.status,
        current_stage=request.current_stage,
        outreach_active=request.outreach_active,
        coordinator_user_id=request.coordinator_user_id,
        verified_by_user_id=request.verified_by_user_id,
        verified_at=request.verified_at,
        fulfilled_at=request.fulfilled_at,
    )


def _donor_profile(db: Session, user_id: UUID) -> BloodDonorProfile:
    profile = db.scalar(select(BloodDonorProfile).where(BloodDonorProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Donor profile not found")
    return profile


@router.post("/donors/profile", response_model=DonorProfileResponse, status_code=status.HTTP_201_CREATED)
def create_blood_donor_profile(
    payload: DonorProfileCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.DONOR))],
) -> DonorProfileResponse:
    if db.scalar(select(BloodDonorProfile.id).where(BloodDonorProfile.user_id == user.id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Donor profile already exists")
    now = datetime.now(timezone.utc)
    profile = BloodDonorProfile(
        user_id=user.id,
        blood_group=payload.blood_group,
        locality=payload.locality,
        approx_latitude=payload.approx_latitude,
        approx_longitude=payload.approx_longitude,
        availability=payload.availability,
        notification_consent=payload.notification_consent,
        urgent_contact_consent=payload.urgent_contact_consent,
        last_confirmed_at=now if payload.availability == "AVAILABLE" else None,
    )
    db.add(profile)
    db.flush()
    blood_outreach._audit(db, user.id, "DONOR_PROFILE_CREATED", "blood_donor", str(profile.id))
    db.commit()
    return DonorProfileResponse.model_validate(profile, from_attributes=True)


@router.get("/donors/profile", response_model=DonorProfileResponse)
def read_blood_donor_profile(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.DONOR))],
) -> DonorProfileResponse:
    return DonorProfileResponse.model_validate(_donor_profile(db, user.id), from_attributes=True)


@router.patch("/donors/availability", response_model=DonorProfileResponse)
def update_blood_donor_availability(
    payload: DonorAvailabilityUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.DONOR))],
) -> DonorProfileResponse:
    profile = _donor_profile(db, user.id)
    profile.availability = payload.availability
    if payload.notification_consent is not None:
        profile.notification_consent = payload.notification_consent
    if payload.urgent_contact_consent is not None:
        profile.urgent_contact_consent = payload.urgent_contact_consent
    profile.last_confirmed_at = datetime.now(timezone.utc) if payload.availability == "AVAILABLE" else profile.last_confirmed_at
    blood_outreach._audit(db, user.id, "DONOR_AVAILABILITY_UPDATED", "blood_donor", str(profile.id))
    db.commit()
    return DonorProfileResponse.model_validate(profile, from_attributes=True)


@router.post("/requests", response_model=BloodRequestResponse, status_code=status.HTTP_201_CREATED)
def create_blood_request(
    payload: BloodRequestCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.REQUESTER))],
) -> BloodRequestResponse:
    if payload.required_by.tzinfo is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="required_by must include a timezone")
    if payload.required_by <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="required_by must be in the future")
    request = BloodRequest(
        public_id=f"UTH-{uuid4().hex[:8].upper()}",
        requester_user_id=user.id,
        facility=payload.facility,
        locality=payload.locality,
        approx_latitude=payload.approx_latitude,
        approx_longitude=payload.approx_longitude,
        blood_group=payload.blood_group,
        required_donors=payload.required_donors,
        required_by=payload.required_by,
        urgency=payload.urgency,
        facility_reference=payload.facility_reference,
        additional_information=payload.additional_information,
        status="PENDING_VERIFICATION",
    )
    db.add(request)
    db.flush()
    db.add(BloodRequestStatusHistory(request_id=request.id, actor_user_id=user.id, status="PENDING_VERIFICATION", reason="Request submitted"))
    blood_outreach._audit(db, user.id, "REQUEST_SUBMITTED", "blood_request", request.public_id)
    db.commit()
    return _request_response(request)


@router.get("/requests", response_model=list[BloodRequestResponse])
def list_blood_requests(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[BloodRequestResponse]:
    query = select(BloodRequest).order_by(BloodRequest.created_at.desc())
    if user.role.name == RoleName.REQUESTER:
        query = query.where(BloodRequest.requester_user_id == user.id)
    elif user.role.name not in COORDINATOR_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return [_request_response(request) for request in db.scalars(query).all()]


@router.get("/requests/{request_id}", response_model=BloodRequestResponse)
def read_blood_request(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BloodRequestResponse:
    return _request_response(_get_request(db, request_id, user))


@router.post("/requests/{request_id}/assign", response_model=BloodRequestResponse)
def assign_blood_request(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    request.coordinator_user_id = user.id
    blood_outreach._audit(db, user.id, "REQUEST_COORDINATOR_ASSIGNED", "blood_request", request.public_id)
    db.commit()
    return _request_response(request)


@router.post("/requests/{request_id}/verify", response_model=BloodRequestResponse)
def verify_blood_request(
    request_id: UUID,
    payload: VerificationDecision,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    blood_outreach.verify_request(db, request, user, payload.decision, payload.notes)
    db.commit()
    return _request_response(request)


def _outreach_response(db: Session, request: BloodRequest, sent: int = 0) -> OutreachResponse:
    accepted, declined, no_response = blood_outreach._response_counts(db, request.id)
    pending = db.scalar(select(func.count()).select_from(BloodNotification).where(BloodNotification.request_id == request.id, BloodNotification.status == "SENT")) or 0
    stage = max(request.current_stage, 0)
    minimum, maximum, duration = blood_outreach.RADIUS_STAGES[stage]
    return OutreachResponse(
        request_id=request.id,
        stage=stage,
        radius_min_km=minimum,
        radius_max_km=maximum,
        duration_seconds=duration,
        notifications_sent=sent or pending + accepted + declined + no_response,
        accepted=accepted,
        declined=declined,
        no_response=no_response,
        remaining=max(0, request.required_donors - accepted),
        outreach_active=request.outreach_active,
        status=request.status,
    )


@router.post("/requests/{request_id}/start-outreach", response_model=OutreachResponse)
def start_blood_outreach(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES))],
) -> OutreachResponse:
    request = blood_outreach._request_or_404(db, request_id)
    sent = blood_outreach.start_outreach(db, request, user)
    db.commit()
    return _outreach_response(db, request, sent)


@router.get("/requests/{request_id}/matches", response_model=list[DonorMatchResponse])
def list_blood_matches(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES))],
) -> list[DonorMatchResponse]:
    request = blood_outreach._request_or_404(db, request_id)
    del request
    matches = db.execute(
        select(BloodDonorMatch, BloodDonorProfile, BloodNotification, BloodNotificationResponse)
        .join(BloodDonorProfile, BloodDonorProfile.id == BloodDonorMatch.donor_id)
        .join(BloodNotification, (BloodNotification.request_id == BloodDonorMatch.request_id) & (BloodNotification.donor_id == BloodDonorMatch.donor_id))
        .outerjoin(BloodNotificationResponse, BloodNotificationResponse.notification_id == BloodNotification.id)
        .where(BloodDonorMatch.request_id == request_id)
        .order_by(BloodDonorMatch.stage, BloodDonorMatch.created_at)
    ).all()
    blood_outreach._audit(db, user.id, "MATCHES_VIEWED", "blood_request", str(request_id))
    db.commit()
    return [
        DonorMatchResponse(
            donor_code=f"DNR-{str(profile.id).split('-')[0].upper()}",
            blood_group=profile.blood_group,
            locality=profile.locality,
            distance_km=float(match.distance_km) if match.distance_km is not None else None,
            availability_confirmed_at=profile.last_confirmed_at,
            notification_consent=profile.notification_consent,
            response=response.response if response else notification.status,
        )
        for match, profile, notification, response in matches
    ]


def _respond_to_notification(notification_id: UUID, db: Session, user: User, response: str) -> MessageResponse:
    notification = db.get(BloodNotification, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    blood_outreach.record_response(db, notification, user, response)
    db.commit()
    return MessageResponse(message="Response recorded" if response == "ACCEPTED" else "Decline recorded")


@router.get("/notifications", response_model=list[DonorEmergencyAlertResponse])
def list_donor_emergency_alerts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.DONOR))],
) -> list[DonorEmergencyAlertResponse]:
    profile = _donor_profile(db, user.id)
    rows = db.execute(
        select(BloodNotification, BloodRequest, BloodDonorMatch, BloodOutreachBatch)
        .join(BloodRequest, BloodRequest.id == BloodNotification.request_id)
        .join(BloodDonorMatch, (BloodDonorMatch.request_id == BloodNotification.request_id) & (BloodDonorMatch.donor_id == BloodNotification.donor_id))
        .join(BloodOutreachBatch, BloodOutreachBatch.id == BloodNotification.batch_id)
        .where(
            BloodNotification.donor_id == profile.id,
            BloodNotification.status == "SENT",
            BloodRequest.outreach_active.is_(True),
            BloodRequest.status == "OUTREACH_ACTIVE",
            BloodOutreachBatch.expires_at > datetime.now(timezone.utc),
        )
        .order_by(BloodNotification.sent_at.desc())
    ).all()
    blood_outreach._audit(db, user.id, "DONOR_ALERTS_VIEWED", "blood_notification", None)
    db.commit()
    return [
        DonorEmergencyAlertResponse(
            notification_id=notification.id,
            request_id=request.id,
            public_id=request.public_id,
            facility=request.facility,
            locality=request.locality,
            blood_group=request.blood_group,
            distance_km=float(match.distance_km) if match.distance_km is not None else None,
            required_by=request.required_by,
            response_deadline=batch.expires_at,
        )
        for notification, request, match, batch in rows
    ]


@router.post("/notifications/{notification_id}/accept", response_model=MessageResponse)
def accept_blood_notification(
    notification_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.DONOR))],
) -> MessageResponse:
    return _respond_to_notification(notification_id, db, user, "ACCEPTED")


@router.post("/notifications/{notification_id}/decline", response_model=MessageResponse)
def decline_blood_notification(
    notification_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.DONOR))],
) -> MessageResponse:
    return _respond_to_notification(notification_id, db, user, "DECLINED")


@router.post("/requests/{request_id}/expand-radius", response_model=OutreachResponse)
def expand_blood_outreach(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES))],
) -> OutreachResponse:
    request = blood_outreach._request_or_404(db, request_id)
    sent = blood_outreach.advance_outreach(db, request, user)
    db.commit()
    return _outreach_response(db, request, sent)


@router.post("/requests/{request_id}/stop-outreach", response_model=BloodRequestResponse)
def stop_blood_outreach(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    blood_outreach.stop_outreach(db, request, user, "OUTREACH_STOPPED", "Stopped by coordinator")
    db.commit()
    return _request_response(request)


@router.post("/requests/{request_id}/fulfil", response_model=BloodRequestResponse)
def fulfil_blood_request(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    blood_outreach.stop_outreach(db, request, user, "FULFILLED", "Fulfilment recorded by coordinator")
    db.commit()
    return _request_response(request)


@router.post("/requests/{request_id}/cancel", response_model=BloodRequestResponse)
def cancel_blood_request(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES, RoleName.REQUESTER))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    if user.role.name == RoleName.REQUESTER and request.requester_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    blood_outreach.stop_outreach(db, request, user, "CANCELLED", "Cancelled by request owner or coordinator")
    db.commit()
    return _request_response(request)


@router.get("/dashboard/stats", response_model=DashboardStats)
def blood_dashboard_stats(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*COORDINATOR_ROLES))],
) -> DashboardStats:
    del user
    now = datetime.now(timezone.utc)
    recent = now - blood_outreach.AVAILABILITY_MAX_AGE
    return DashboardStats(
        contactable_donors=db.scalar(select(func.count()).select_from(BloodDonorProfile).where(BloodDonorProfile.availability == "AVAILABLE", BloodDonorProfile.notification_consent.is_(True), BloodDonorProfile.last_confirmed_at >= recent)) or 0,
        donors_needing_confirmation=db.scalar(select(func.count()).select_from(BloodDonorProfile).where(BloodDonorProfile.availability == "NEEDS_CONFIRMATION")) or 0,
        active_requests=db.scalar(select(func.count()).select_from(BloodRequest).where(BloodRequest.status.in_(("VERIFIED", "OUTREACH_ACTIVE", "COORDINATION")))) or 0,
        pending_verification=db.scalar(select(func.count()).select_from(BloodRequest).where(BloodRequest.status == "PENDING_VERIFICATION")) or 0,
        fulfilled_today=db.scalar(select(func.count()).select_from(BloodRequest).where(BloodRequest.status == "FULFILLED", BloodRequest.fulfilled_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))) or 0,
        alerts_cancelled=db.scalar(select(func.count()).select_from(BloodNotification).where(BloodNotification.status == "CANCELLED")) or 0,
    )