from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models import (
    BloodBankStaff,
    BloodDonorMatch,
    BloodDonorProfile,
    BloodDonorTrackingSession,
    BloodNotification,
    BloodNotificationResponse,
    BloodOrganisation,
    BloodOutreachBatch,
    BloodRequest,
    BloodRequestReservation,
    BloodRequestStatusHistory,
    RoleName,
    User,
)
from app.schemas.blood import (
    AcceptNotificationRequest,
    AcceptNotificationResponse,
    BloodBankResponse,
    BloodBankVerificationDecision,
    BloodCompatibilityAnalytics,
    BloodGroupRequestCount,
    BloodGroupVerificationQueueItem,
    BloodGroupVerificationRequest,
    BloodRequestCreate,
    BloodRequestResponse,
    CompletionVerificationDecision,
    ContactShareResponse,
    DashboardStats,
    DonationCompletionReport,
    DonationCompletionResponse,
    DonorAvailabilityUpdate,
    DonorBloodGroupUpdate,
    DonorBloodGroupVerificationBankUpdate,
    DonorEmergencyAlertResponse,
    DonorGroupNotificationStats,
    DonorMatchResponse,
    DonorProfileCreate,
    DonorProfileResponse,
    DonorReservationResponse,
    DonorScreeningReviewRequest,
    MessageResponse,
    OutreachResponse,
    ReservationCancellationRequest,
    VerificationDecision,
    VerifiedBloodBankOption,
)
from app.services import blood_outreach
from app.services.blood_compatibility import (
    RBC_BLOOD_GROUPS,
    compatibility_matrix,
    compatible_recipient_groups,
)

router = APIRouter(tags=["blood coordination"])
OPERATIONS_ROLES = (RoleName.BLOOD_BANK, RoleName.ADMIN)


def _blood_bank_for_user(db: Session, user: User) -> BloodOrganisation:
    organisation = db.scalar(
        select(BloodOrganisation)
        .join(BloodBankStaff, BloodBankStaff.organisation_id == BloodOrganisation.id)
        .where(
            BloodBankStaff.user_id == user.id,
            BloodBankStaff.is_active.is_(True),
        )
    )
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blood bank not found")
    return organisation


def _require_verified_blood_bank(db: Session, user: User) -> BloodOrganisation:
    organisation = _blood_bank_for_user(db, user)
    if organisation.verification_status != "VERIFIED" or not organisation.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Blood bank verification is required for this operation",
        )
    return organisation


def _require_request_operations_access(
    db: Session, request: BloodRequest, user: User
) -> None:
    if user.role.name == RoleName.ADMIN:
        return
    organisation = _require_verified_blood_bank(db, user)
    if request.organisation_id != organisation.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")


def _get_request(db: Session, request_id: UUID, actor: User) -> BloodRequest:
    request = db.get(BloodRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if actor.role.name == RoleName.BLOOD_BANK:
        _require_request_operations_access(db, request, actor)
    elif actor.role.name != RoleName.ADMIN and request.requester_user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def _blood_bank_response(organisation: BloodOrganisation) -> BloodBankResponse:
    return BloodBankResponse.model_validate(organisation, from_attributes=True)


@router.get("/blood-banks/me", response_model=BloodBankResponse)
def read_my_blood_bank(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.BLOOD_BANK))],
) -> BloodBankResponse:
    organisation = _blood_bank_for_user(db, user)
    blood_outreach._audit(db, user.id, "BLOOD_BANK_PROFILE_VIEWED", "blood_organisation", str(organisation.id))
    db.commit()
    return _blood_bank_response(organisation)


@router.get("/blood-banks/verified", response_model=list[VerifiedBloodBankOption])
def list_verified_blood_banks(
    db: Annotated[Session, Depends(get_db)],
) -> list[VerifiedBloodBankOption]:
    organisations = db.scalars(
        select(BloodOrganisation)
        .where(
            BloodOrganisation.verification_status == "VERIFIED",
            BloodOrganisation.is_active.is_(True),
        )
        .order_by(BloodOrganisation.city, BloodOrganisation.name)
    ).all()
    return [
        VerifiedBloodBankOption(
            id=organisation.id,
            name=organisation.name,
            locality=organisation.locality,
            city=organisation.city,
        )
        for organisation in organisations
    ]


@router.get("/admin/blood-banks", response_model=list[BloodBankResponse])
def list_blood_banks(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.ADMIN))],
    verification_status: str | None = None,
) -> list[BloodBankResponse]:
    query = select(BloodOrganisation).order_by(BloodOrganisation.created_at.desc())
    if verification_status is not None:
        if verification_status not in {"PENDING", "VERIFIED", "REJECTED", "SUSPENDED", "EXPIRED"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid verification status")
        query = query.where(BloodOrganisation.verification_status == verification_status)
    organisations = db.scalars(query).all()
    blood_outreach._audit(db, user.id, "BLOOD_BANK_DIRECTORY_VIEWED", "blood_organisation", None)
    db.commit()
    return [_blood_bank_response(organisation) for organisation in organisations]


@router.post("/admin/blood-banks/{organisation_id}/verification", response_model=BloodBankResponse)
def review_blood_bank(
    organisation_id: UUID,
    payload: BloodBankVerificationDecision,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.ADMIN))],
) -> BloodBankResponse:
    organisation = db.get(BloodOrganisation, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blood bank not found")
    if payload.decision == "VERIFY":
        if (
            organisation.license_expires_at
            and blood_outreach._as_utc(organisation.license_expires_at)
            <= datetime.now(timezone.utc)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An expired licence cannot be verified",
            )
        organisation.verification_status = "VERIFIED"
        organisation.verified_at = datetime.now(timezone.utc)
        organisation.verified_by_user_id = user.id
        organisation.is_active = True
    elif payload.decision == "REJECT":
        organisation.verification_status = "REJECTED"
        organisation.is_active = False
    elif payload.decision == "SUSPEND":
        organisation.verification_status = "SUSPENDED"
        organisation.is_active = False
    else:
        organisation.verification_status = "PENDING"
        organisation.is_active = False
        organisation.verified_at = None
        organisation.verified_by_user_id = None
    organisation.verification_notes = payload.notes
    blood_outreach._audit(db, user.id, f"BLOOD_BANK_{payload.decision}", "blood_organisation", str(organisation.id))
    db.commit()
    return _blood_bank_response(organisation)


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
        component=request.component,
        status=request.status,
        current_stage=request.current_stage,
        outreach_active=request.outreach_active,
        assigned_staff_user_id=request.assigned_staff_user_id,
        verified_by_user_id=request.verified_by_user_id,
        verified_at=request.verified_at,
        fulfilled_at=request.fulfilled_at,
    )


def _donor_profile(db: Session, user_id: UUID) -> BloodDonorProfile:
    profile = db.scalar(select(BloodDonorProfile).where(BloodDonorProfile.user_id == user_id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Donor profile not found")
    return profile


def _donor_profile_response(profile: BloodDonorProfile) -> DonorProfileResponse:
    return DonorProfileResponse(
        blood_group=profile.blood_group,
        blood_group_verified=profile.blood_group_verified_at is not None,
        blood_group_verification_organisation_id=profile.blood_group_verification_organisation_id,
        screening_completed=profile.screening_completed_at is not None,
        potential_recipient_groups=list(compatible_recipient_groups(profile.blood_group)),
        locality=profile.locality,
        availability=profile.availability,
        notification_consent=profile.notification_consent,
        urgent_contact_consent=profile.urgent_contact_consent,
        last_confirmed_at=profile.last_confirmed_at,
    )


@router.get("/compatibility/rbc", response_model=dict[str, list[str]])
def read_rbc_compatibility() -> dict[str, list[str]]:
    return dict(compatibility_matrix())


@router.post("/donors/profile", response_model=DonorProfileResponse, status_code=status.HTTP_201_CREATED)
def create_blood_donor_profile(
    payload: DonorProfileCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> DonorProfileResponse:
    if db.scalar(select(BloodDonorProfile.id).where(BloodDonorProfile.user_id == user.id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Donor profile already exists")
    now = datetime.now(timezone.utc)
    if payload.blood_group_verification_organisation_id is not None:
        verification_bank = db.get(
            BloodOrganisation, payload.blood_group_verification_organisation_id
        )
        if (
            verification_bank is None
            or verification_bank.verification_status != "VERIFIED"
            or not verification_bank.is_active
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verified blood bank not found",
            )
    profile = BloodDonorProfile(
        user_id=user.id,
        blood_group=payload.blood_group,
        blood_group_verification_organisation_id=payload.blood_group_verification_organisation_id,
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
    return _donor_profile_response(profile)


@router.get("/donors/profile", response_model=DonorProfileResponse)
def read_blood_donor_profile(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> DonorProfileResponse:
    profile = _donor_profile(db, user.id)
    blood_outreach._audit(db, user.id, "DONOR_PROFILE_VIEWED", "blood_donor", str(profile.id))
    db.commit()
    return _donor_profile_response(profile)


@router.patch("/donors/profile/blood-group", response_model=DonorProfileResponse)
def update_blood_donor_group(
    payload: DonorBloodGroupUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> DonorProfileResponse:
    profile = _donor_profile(db, user.id)
    if profile.blood_group != payload.blood_group:
        profile.blood_group = payload.blood_group
        profile.blood_group_verified_at = None
        profile.blood_group_verified_by_user_id = None
        profile.screening_completed_at = None
        profile.screening_completed_by_user_id = None
        blood_outreach._audit(
            db, user.id, "DONOR_BLOOD_GROUP_UPDATED", "blood_donor", str(profile.id)
        )
    db.commit()
    return _donor_profile_response(profile)


@router.patch(
    "/donors/profile/blood-group-verification-bank",
    response_model=DonorProfileResponse,
)
def select_blood_group_verification_bank(
    payload: DonorBloodGroupVerificationBankUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> DonorProfileResponse:
    profile = _donor_profile(db, user.id)
    organisation = db.get(BloodOrganisation, payload.organisation_id)
    if (
        organisation is None
        or organisation.verification_status != "VERIFIED"
        or not organisation.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verified blood bank not found",
        )
    if profile.blood_group_verification_organisation_id != organisation.id:
        profile.blood_group_verification_organisation_id = organisation.id
        profile.blood_group_verified_at = None
        profile.blood_group_verified_by_user_id = None
        profile.screening_completed_at = None
        profile.screening_completed_by_user_id = None
        blood_outreach._audit(
            db, user.id, "DONOR_GROUP_VERIFICATION_BANK_SELECTED", "blood_donor", str(profile.id)
        )
    db.commit()
    return _donor_profile_response(profile)


@router.get(
    "/blood-banks/donors/pending-blood-group-verification",
    response_model=list[BloodGroupVerificationQueueItem],
)
def list_pending_donor_group_verifications(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.BLOOD_BANK))],
) -> list[BloodGroupVerificationQueueItem]:
    organisation = _require_verified_blood_bank(db, user)
    profiles = db.scalars(
        select(BloodDonorProfile)
        .where(
            BloodDonorProfile.blood_group_verification_organisation_id == organisation.id,
            BloodDonorProfile.blood_group_verified_at.is_(None),
        )
        .order_by(BloodDonorProfile.created_at)
    ).all()
    blood_outreach._audit(
        db,
        user.id,
        "DONOR_GROUP_VERIFICATION_QUEUE_VIEWED",
        "blood_organisation",
        str(organisation.id),
    )
    db.commit()
    return [
        BloodGroupVerificationQueueItem(
            donor_profile_id=profile.id,
            blood_group=profile.blood_group,
        )
        for profile in profiles
    ]


@router.get(
    "/blood-banks/donors/pending-screening",
    response_model=list[BloodGroupVerificationQueueItem],
)
def list_pending_donor_screening(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.BLOOD_BANK))],
) -> list[BloodGroupVerificationQueueItem]:
    organisation = _require_verified_blood_bank(db, user)
    profiles = db.scalars(
        select(BloodDonorProfile)
        .where(
            BloodDonorProfile.blood_group_verification_organisation_id == organisation.id,
            BloodDonorProfile.blood_group_verified_at.is_not(None),
            BloodDonorProfile.screening_completed_at.is_(None),
        )
        .order_by(BloodDonorProfile.created_at)
    ).all()
    blood_outreach._audit(
        db,
        user.id,
        "DONOR_SCREENING_QUEUE_VIEWED",
        "blood_organisation",
        str(organisation.id),
    )
    db.commit()
    return [
        BloodGroupVerificationQueueItem(
            donor_profile_id=profile.id,
            blood_group=profile.blood_group,
        )
        for profile in profiles
    ]


@router.post(
    "/donors/{donor_profile_id}/blood-group/verify",
    response_model=DonorProfileResponse,
)
def verify_donor_blood_group(
    donor_profile_id: UUID,
    payload: BloodGroupVerificationRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.BLOOD_BANK))],
) -> DonorProfileResponse:
    organisation = _require_verified_blood_bank(db, user)
    profile = db.get(BloodDonorProfile, donor_profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Donor profile not found")
    if profile.blood_group != payload.confirmed_blood_group:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The confirmed group must match the donor's recorded group",
        )
    if profile.blood_group_verification_organisation_id != organisation.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donor verification request not found",
        )
    profile.blood_group_verified_at = datetime.now(timezone.utc)
    profile.blood_group_verified_by_user_id = user.id
    blood_outreach._audit(
        db, user.id, "DONOR_BLOOD_GROUP_VERIFIED", "blood_donor", str(profile.id)
    )
    db.commit()
    return _donor_profile_response(profile)


@router.post(
    "/blood-banks/donors/{donor_profile_id}/screening-review",
    response_model=DonorProfileResponse,
)
def record_donor_screening_completion(
    donor_profile_id: UUID,
    payload: DonorScreeningReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.BLOOD_BANK))],
) -> DonorProfileResponse:
    organisation = _require_verified_blood_bank(db, user)
    profile = db.get(BloodDonorProfile, donor_profile_id)
    if (
        profile is None
        or profile.blood_group_verification_organisation_id != organisation.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Donor screening record not found",
        )
    if payload.screening_completed and profile.blood_group_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verify the recorded blood group before recording screening completion",
        )
    if payload.screening_completed:
        profile.screening_completed_at = datetime.now(timezone.utc)
        profile.screening_completed_by_user_id = user.id
    else:
        profile.screening_completed_at = None
        profile.screening_completed_by_user_id = None
    blood_outreach._audit(
        db,
        user.id,
        "DONOR_SCREENING_COMPLETION_RECORDED"
        if payload.screening_completed
        else "DONOR_SCREENING_COMPLETION_REVOKED",
        "blood_donor",
        str(profile.id),
    )
    db.commit()
    return _donor_profile_response(profile)


@router.patch("/donors/availability", response_model=DonorProfileResponse)
def update_blood_donor_availability(
    payload: DonorAvailabilityUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
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
    return _donor_profile_response(profile)


@router.post("/requests", response_model=BloodRequestResponse, status_code=status.HTTP_201_CREATED)
def create_blood_request(
    payload: BloodRequestCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR, RoleName.BLOOD_BANK))],
) -> BloodRequestResponse:
    if user.phone_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your phone number before creating a request",
        )
    if payload.required_by.tzinfo is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="required_by must include a timezone")
    if payload.required_by <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="required_by must be in the future")
    organisation_id = None
    if user.role.name == RoleName.BLOOD_BANK:
        organisation_id = _require_verified_blood_bank(db, user).id
    request = BloodRequest(
        public_id=f"UTH-{uuid4().hex[:8].upper()}",
        requester_user_id=user.id,
        organisation_id=organisation_id,
        facility=payload.facility,
        locality=payload.locality,
        approx_latitude=payload.approx_latitude,
        approx_longitude=payload.approx_longitude,
        blood_group=payload.blood_group,
        component=payload.component,
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
    if user.role.name == RoleName.GENERAL_DONOR:
        query = query.where(BloodRequest.requester_user_id == user.id)
    elif user.role.name == RoleName.BLOOD_BANK:
        organisation = _require_verified_blood_bank(db, user)
        query = query.where(BloodRequest.organisation_id == organisation.id)
    elif user.role.name != RoleName.ADMIN:
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
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    _require_request_operations_access(db, request, user)
    request.assigned_staff_user_id = user.id
    blood_outreach._audit(db, user.id, "REQUEST_ASSIGNED_TO_BLOOD_BANK", "blood_request", request.public_id)
    db.commit()
    return _request_response(request)


@router.post("/requests/{request_id}/verify", response_model=BloodRequestResponse)
def verify_blood_request(
    request_id: UUID,
    payload: VerificationDecision,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.ADMIN))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    blood_outreach.verify_request(db, request, user, payload.decision, payload.notes)
    db.commit()
    return _request_response(request)


def _outreach_response(db: Session, request: BloodRequest, sent: int = 0) -> OutreachResponse:
    _, declined, no_response = blood_outreach._response_counts(db, request.id)
    accepted = blood_outreach._active_reservation_count(db, request.id)
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
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES))],
) -> OutreachResponse:
    request = blood_outreach._request_or_404(db, request_id)
    _require_request_operations_access(db, request, user)
    sent = blood_outreach.start_outreach(db, request, user)
    db.commit()
    return _outreach_response(db, request, sent)


@router.get("/requests/{request_id}/matches", response_model=list[DonorMatchResponse])
def list_blood_matches(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES))],
) -> list[DonorMatchResponse]:
    request = blood_outreach._request_or_404(db, request_id)
    _require_request_operations_access(db, request, user)
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
            donor_profile_id=profile.id,
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


def _respond_to_notification(
    notification_id: UUID,
    db: Session,
    user: User,
    response: str,
    *,
    contact_shared: bool = False,
) -> MessageResponse:
    notification = db.get(BloodNotification, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    blood_outreach.record_response(
        db,
        notification,
        user,
        response,
        contact_shared=contact_shared,
    )
    db.commit()
    return MessageResponse(message="Response recorded" if response == "ACCEPTED" else "Decline recorded")


@router.get("/notifications", response_model=list[DonorEmergencyAlertResponse])
def list_donor_emergency_alerts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
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
            component=request.component,
            distance_km=float(match.distance_km) if match.distance_km is not None else None,
            required_by=request.required_by,
            response_deadline=batch.expires_at,
        )
        for notification, request, match, batch in rows
    ]


@router.get("/donors/reservations", response_model=list[DonorReservationResponse])
def list_my_donor_reservations(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> list[DonorReservationResponse]:
    profile = _donor_profile(db, user.id)
    rows = db.execute(
        select(BloodRequestReservation, BloodRequest)
        .join(BloodRequest, BloodRequest.id == BloodRequestReservation.request_id)
        .where(
            BloodRequestReservation.donor_id == profile.id,
            BloodRequestReservation.status.in_(("ACTIVE", "COMPLETED")),
        )
        .order_by(BloodRequestReservation.reserved_at.desc())
    ).all()
    blood_outreach._audit(db, user.id, "DONOR_RESERVATIONS_VIEWED", "blood_request", None)
    db.commit()
    return [
        DonorReservationResponse(
            reservation_id=reservation.id,
            request_id=request.id,
            public_id=request.public_id,
            facility=request.facility,
            locality=request.locality,
            blood_group=request.blood_group,
            unit_number=reservation.unit_number,
            status=reservation.status,
            reserved_at=reservation.reserved_at,
            grace_until=reservation.grace_until,
        )
        for reservation, request in rows
    ]


@router.post(
    "/notifications/{notification_id}/accept",
    response_model=AcceptNotificationResponse,
)
def accept_blood_notification(
    notification_id: UUID,
    payload: AcceptNotificationRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> AcceptNotificationResponse:
    if payload.share_contact and (
        not user.phone or user.phone_verified_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verify a phone number before choosing to share it",
        )
    notification = db.get(BloodNotification, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    reservation = blood_outreach.record_response(
        db,
        notification,
        user,
        "ACCEPTED",
        contact_shared=payload.share_contact,
    )
    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reservation could not be created",
        )
    request_obj = db.get(BloodRequest, notification.request_id)
    donor_obj = db.get(BloodDonorProfile, notification.donor_id)
    if request_obj and donor_obj:
        from app.services import blood_tracking

        blood_tracking.create_or_get_tracking_session(
            db, request_obj, reservation, donor_obj
        )
    db.commit()
    return AcceptNotificationResponse(
        message="Response recorded",
        reservation_id=reservation.id,
        grace_until=reservation.grace_until,
        contact_shared=reservation.contact_shared,
    )


@router.post("/notifications/{notification_id}/decline", response_model=MessageResponse)
def decline_blood_notification(
    notification_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> MessageResponse:
    return _respond_to_notification(notification_id, db, user, "DECLINED")


@router.post("/requests/{request_id}/reservations/{reservation_id}/cancel", response_model=MessageResponse)
def cancel_donor_reservation(
    request_id: UUID,
    reservation_id: UUID,
    payload: ReservationCancellationRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> MessageResponse:
    reservation = db.get(BloodRequestReservation, reservation_id)
    if reservation is None or reservation.request_id != request_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    blood_outreach.cancel_reservation(db, reservation_id, user, payload.reason)
    session = db.scalar(
        select(BloodDonorTrackingSession).where(
            BloodDonorTrackingSession.reservation_id == reservation_id
        )
    )
    if session is not None and session.status not in ("ARRIVED", "CANCELLED"):
        session.status = "CANCELLED"
        session.stop_reason = payload.reason or "Reservation cancelled"
        session.stopped_at = datetime.now(timezone.utc)
        session.current_latitude = None
        session.current_longitude = None
        session.current_accuracy_meters = None
    db.commit()
    return MessageResponse(message="Reservation cancelled; outreach has resumed")


@router.post(
    "/donors/reservations/{reservation_id}/revoke-contact-sharing",
    response_model=MessageResponse,
)
def revoke_donor_contact_sharing(
    reservation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> MessageResponse:
    blood_outreach.revoke_contact_sharing(db, reservation_id, user)
    db.commit()
    return MessageResponse(message="Contact-sharing permission withdrawn")


@router.get(
    "/requests/{request_id}/reservations/{reservation_id}/contact",
    response_model=ContactShareResponse,
)
def read_shared_donor_contact(
    request_id: UUID,
    reservation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[
        User,
        Depends(require_role(RoleName.GENERAL_DONOR, RoleName.BLOOD_BANK, RoleName.ADMIN)),
    ],
) -> ContactShareResponse:
    request = blood_outreach._request_or_404(db, request_id)
    if user.role.name == RoleName.GENERAL_DONOR:
        if request.requester_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    elif user.role.name == RoleName.BLOOD_BANK:
        _require_request_operations_access(db, request, user)
    reservation = db.get(BloodRequestReservation, reservation_id)
    if (
        reservation is None
        or reservation.request_id != request.id
        or reservation.status not in {"ACTIVE", "COMPLETED"}
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    if not reservation.contact_shared:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Donor has not shared contact details",
        )
    donor = db.get(BloodDonorProfile, reservation.donor_id)
    donor_user = db.get(User, donor.user_id) if donor else None
    if donor_user is None or not donor_user.phone or donor_user.phone_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verified donor contact is unavailable",
        )
    blood_outreach._audit(
        db,
        user.id,
        "DONOR_CONTACT_VIEWED",
        "blood_request_reservation",
        str(reservation.id),
    )
    db.commit()
    return ContactShareResponse(phone=donor_user.phone)


@router.post("/requests/{request_id}/expand-radius", response_model=OutreachResponse)
def expand_blood_outreach(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES))],
) -> OutreachResponse:
    request = blood_outreach._request_or_404(db, request_id)
    _require_request_operations_access(db, request, user)
    sent = blood_outreach.advance_outreach(db, request, user)
    db.commit()
    return _outreach_response(db, request, sent)


@router.post("/requests/{request_id}/stop-outreach", response_model=BloodRequestResponse)
def stop_blood_outreach(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    _require_request_operations_access(db, request, user)
    blood_outreach.stop_outreach(db, request, user, "OUTREACH_STOPPED", "Stopped by authorized staff")
    db.commit()
    return _request_response(request)


@router.post("/requests/{request_id}/fulfil", response_model=BloodRequestResponse)
def fulfil_blood_request(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    _require_request_operations_access(db, request, user)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Completion requires a donor report and receiving-institution confirmation",
    )


@router.post(
    "/requests/{request_id}/reservations/{reservation_id}/completion-report",
    response_model=DonationCompletionResponse,
    status_code=status.HTTP_201_CREATED,
)
def report_donation_completion(
    request_id: UUID,
    reservation_id: UUID,
    payload: DonationCompletionReport,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.GENERAL_DONOR))],
) -> DonationCompletionResponse:
    record = blood_outreach.report_completion(
        db,
        request_id,
        reservation_id,
        user,
        component=payload.component,
        quantity_ml=payload.quantity_ml,
    )
    db.commit()
    return DonationCompletionResponse.model_validate(record, from_attributes=True)


@router.post(
    "/requests/{request_id}/completion-reports/{record_id}/verify",
    response_model=DonationCompletionResponse,
)
def verify_donation_completion(
    request_id: UUID,
    record_id: UUID,
    payload: CompletionVerificationDecision,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES))],
) -> DonationCompletionResponse:
    request = blood_outreach._request_or_404(db, request_id)
    if user.role.name == RoleName.BLOOD_BANK:
        _require_request_operations_access(db, request, user)
    record = blood_outreach.verify_completion(
        db,
        request_id,
        record_id,
        user,
        decision=payload.decision,
        notes=payload.notes,
    )
    db.commit()
    return DonationCompletionResponse.model_validate(record, from_attributes=True)


@router.post("/requests/{request_id}/cancel", response_model=BloodRequestResponse)
def cancel_blood_request(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES, RoleName.GENERAL_DONOR))],
) -> BloodRequestResponse:
    request = blood_outreach._request_or_404(db, request_id)
    if user.role.name == RoleName.BLOOD_BANK:
        _require_request_operations_access(db, request, user)
    elif user.role.name == RoleName.GENERAL_DONOR and request.requester_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    blood_outreach.stop_outreach(db, request, user, "CANCELLED", "Cancelled by request owner or authorized staff")
    tracking_sessions = db.scalars(
        select(BloodDonorTrackingSession).where(
            BloodDonorTrackingSession.request_id == request.id
        )
    ).all()
    now = datetime.now(timezone.utc)
    for s in tracking_sessions:
        if s.status not in ("ARRIVED", "CANCELLED", "STOPPED"):
            s.status = "CANCELLED"
            s.stop_reason = "Request cancelled"
            s.stopped_at = now
            s.current_latitude = None
            s.current_longitude = None
            s.current_accuracy_meters = None
    db.commit()
    return _request_response(request)


@router.get("/dashboard/stats", response_model=DashboardStats)
def blood_dashboard_stats(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*OPERATIONS_ROLES))],
) -> DashboardStats:
    if user.role.name == RoleName.BLOOD_BANK:
        organisation = _require_verified_blood_bank(db, user)
        request_scope = BloodRequest.organisation_id == organisation.id
    else:
        request_scope = True
    now = datetime.now(timezone.utc)
    recent = now - blood_outreach.AVAILABILITY_MAX_AGE
    return DashboardStats(
        contactable_donors=db.scalar(select(func.count()).select_from(BloodDonorProfile).where(BloodDonorProfile.availability == "AVAILABLE", BloodDonorProfile.notification_consent.is_(True), BloodDonorProfile.last_confirmed_at >= recent)) or 0,
        donors_needing_confirmation=db.scalar(select(func.count()).select_from(BloodDonorProfile).where(BloodDonorProfile.availability == "NEEDS_CONFIRMATION")) or 0,
        active_requests=db.scalar(select(func.count()).select_from(BloodRequest).where(BloodRequest.status.in_(("VERIFIED", "OUTREACH_ACTIVE", "COORDINATION")), request_scope)) or 0,
        pending_verification=db.scalar(select(func.count()).select_from(BloodRequest).where(BloodRequest.status == "PENDING_VERIFICATION", request_scope)) or 0,
        fulfilled_today=db.scalar(select(func.count()).select_from(BloodRequest).where(BloodRequest.status == "FULFILLED", BloodRequest.fulfilled_at >= now.replace(hour=0, minute=0, second=0, microsecond=0), request_scope)) or 0,
        alerts_cancelled=db.scalar(select(func.count()).select_from(BloodNotification).where(BloodNotification.status == "CANCELLED")) or 0,
    )


@router.get(
    "/admin/analytics/blood-compatibility",
    response_model=BloodCompatibilityAnalytics,
)
def blood_compatibility_analytics(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(RoleName.ADMIN))],
) -> BloodCompatibilityAnalytics:
    request_counts = dict(
        db.execute(
            select(BloodRequest.blood_group, func.count(BloodRequest.id))
            .group_by(BloodRequest.blood_group)
        ).all()
    )
    notification_rows = db.execute(
        select(
            BloodNotification.donor_blood_group,
            BloodNotification.id,
            BloodNotificationResponse.response,
        )
        .outerjoin(
            BloodNotificationResponse,
            BloodNotificationResponse.notification_id == BloodNotification.id,
        )
        .where(BloodNotification.sent_at.is_not(None))
    ).all()
    notifications: dict[str, int] = {group: 0 for group in RBC_BLOOD_GROUPS}
    accepted: dict[str, int] = {group: 0 for group in RBC_BLOOD_GROUPS}
    for group, _notification_id, response in notification_rows:
        if group not in notifications:
            continue
        notifications[group] += 1
        if response == "ACCEPTED":
            accepted[group] += 1

    response_rows = db.execute(
        select(BloodNotification.sent_at, BloodNotificationResponse.responded_at)
        .join(
            BloodNotificationResponse,
            BloodNotificationResponse.notification_id == BloodNotification.id,
        )
        .where(BloodNotification.sent_at.is_not(None))
    ).all()
    response_seconds = [
        max(
            0.0,
            (
                blood_outreach._as_utc(responded_at)
                - blood_outreach._as_utc(sent_at)
            ).total_seconds(),
        )
        for sent_at, responded_at in response_rows
    ]
    analytics = BloodCompatibilityAnalytics(
        requests_by_required_group=[
            BloodGroupRequestCount(
                required_blood_group=group,
                count=request_counts.get(group, 0),
            )
            for group in RBC_BLOOD_GROUPS
        ],
        potential_donors_identified=db.scalar(
            select(func.count(BloodDonorMatch.id)).where(BloodDonorMatch.status == "MATCHED")
        )
        or 0,
        notifications_by_donor_group=[
            DonorGroupNotificationStats(
                donor_blood_group=group,
                notifications_sent=notifications[group],
                accepted=accepted[group],
                acceptance_rate=accepted[group] / notifications[group]
                if notifications[group]
                else 0.0,
            )
            for group in RBC_BLOOD_GROUPS
        ],
        institution_confirmed_fulfilments=db.scalar(
            select(func.count(BloodRequest.id)).where(BloodRequest.status == "FULFILLED")
        )
        or 0,
        unfulfilled_requests=db.scalar(
            select(func.count(BloodRequest.id)).where(BloodRequest.status != "FULFILLED")
        )
        or 0,
        average_response_seconds=sum(response_seconds) / len(response_seconds)
        if response_seconds
        else None,
    )
    blood_outreach._audit(
        db,
        user.id,
        "ADMIN_BLOOD_COMPATIBILITY_ANALYTICS_VIEWED",
        "blood_analytics",
        None,
    )
    db.commit()
    return analytics