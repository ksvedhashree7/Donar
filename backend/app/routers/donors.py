from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models import (
    AccessGrant,
    Consent,
    ConsentStatus,
    Doctor,
    Donor,
    HospitalStaff,
    RoleName,
    User,
)
from app.schemas.donor import DonorMedicalResponse, DonorSummary
from app.services.policies import can_view_donor_medical

router = APIRouter(prefix="/donors", tags=["donors"])
HOSPITAL_ROLES = (RoleName.DOCTOR, RoleName.HOSPITAL_STAFF)
MEDICAL_ROLES = (RoleName.DONOR, *HOSPITAL_ROLES)


@router.get("", response_model=list[DonorSummary])
def list_donors_with_active_grants(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*HOSPITAL_ROLES))],
) -> list[DonorSummary]:
    if user.role.name == RoleName.DOCTOR:
        hospital_id = db.scalar(select(Doctor.hospital_id).where(Doctor.user_id == user.id))
    else:
        hospital_id = db.scalar(
            select(HospitalStaff.hospital_id).where(HospitalStaff.user_id == user.id)
        )
    if hospital_id is None:
        return []
    now = datetime.now(timezone.utc)
    donors = db.scalars(
        select(Donor)
        .join(AccessGrant, AccessGrant.donor_id == Donor.id)
        .join(Consent, Consent.donor_id == Donor.id)
        .where(
            Donor.hospital_id == hospital_id,
            AccessGrant.is_active.is_(True),
            AccessGrant.purpose == "medical_evaluation",
            or_(
                AccessGrant.granted_to_user_id == user.id,
                AccessGrant.granted_to_role == user.role.name.value,
            ),
            or_(AccessGrant.valid_until.is_(None), AccessGrant.valid_until > now),
            Consent.purpose == "medical_evaluation",
            Consent.status == ConsentStatus.ACTIVE,
            Consent.withdrawn_at.is_(None),
        )
        .distinct()
    ).all()
    return [
        DonorSummary(id=donor.id, donor_code=donor.donor_code, status=donor.status.value)
        for donor in donors
    ]


@router.get("/{donor_id}/medical", response_model=DonorMedicalResponse)
def read_donor_medical(
    donor_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*MEDICAL_ROLES))],
    purpose: Annotated[Literal["medical_evaluation", "matching", "coordination"], Query()],
) -> DonorMedicalResponse:
    donor = db.get(Donor, donor_id)
    if donor is None or not can_view_donor_medical(user, donor, purpose, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Donor record not found")
    profile = donor.medical_profile
    safe_profile = None
    if profile:
        safe_profile = {
            "blood_group": profile.blood_group,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "allergies": profile.allergies,
            "conditions": profile.conditions,
        }
    return DonorMedicalResponse(
        donor_code=donor.donor_code,
        blood_group=donor.blood_group,
        organ=donor.organ,
        medical_profile=safe_profile,
    )
