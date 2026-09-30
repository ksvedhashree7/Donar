from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    AccessGrant,
    Consent,
    ConsentStatus,
    Doctor,
    Donor,
    FieldVerification,
    HospitalStaff,
    RoleName,
    User,
    VerificationStatus,
)


def can_view_donor_medical(actor: User, donor: Donor, purpose: str, db: Session) -> bool:
    if purpose not in {"medical_evaluation", "matching", "coordination"}:
        return False
    if actor.role.name == RoleName.DONOR and donor.user_id == actor.id:
        return True
    if actor.role.name == RoleName.DOCTOR:
        hospital_id = db.scalar(select(Doctor.hospital_id).where(Doctor.user_id == actor.id))
    elif actor.role.name == RoleName.HOSPITAL_STAFF:
        hospital_id = db.scalar(
            select(HospitalStaff.hospital_id).where(HospitalStaff.user_id == actor.id)
        )
    else:
        return False
    if hospital_id is None or donor.hospital_id != hospital_id:
        return False

    now = datetime.now(timezone.utc)
    active_grant = db.scalar(
        select(AccessGrant.id).where(
            AccessGrant.donor_id == donor.id,
            AccessGrant.purpose == purpose,
            AccessGrant.is_active.is_(True),
            or_(
                AccessGrant.granted_to_user_id == actor.id,
                AccessGrant.granted_to_role == actor.role.name.value,
            ),
            or_(AccessGrant.valid_until.is_(None), AccessGrant.valid_until > now),
        )
    )
    active_consent = db.scalar(
        select(Consent.id).where(
            Consent.donor_id == donor.id,
            Consent.purpose == purpose,
            Consent.status == ConsentStatus.ACTIVE,
            Consent.withdrawn_at.is_(None),
        )
    )
    return active_grant is not None and active_consent is not None


def can_edit_verified_medical(actor: User, field: FieldVerification, db: Session) -> bool:
    if actor.role.name != RoleName.DOCTOR or field.status != VerificationStatus.VERIFIED:
        return False
    doctor = db.scalar(select(Doctor).where(Doctor.user_id == actor.id))
    return (
        doctor is not None
        and field.verified_by == doctor.id
        and field.hospital_id == doctor.hospital_id
    )
