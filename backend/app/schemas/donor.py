from uuid import UUID

from pydantic import BaseModel


class DonorSummary(BaseModel):
    id: UUID
    donor_code: str
    status: str


class DonorMedicalResponse(BaseModel):
    donor_code: str
    blood_group: str | None
    organ: str | None
    medical_profile: dict[str, str | int | None] | None
