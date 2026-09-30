from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

BloodGroup = Literal["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]


class DonorProfileCreate(BaseModel):
    blood_group: BloodGroup
    locality: str = Field(min_length=2, max_length=120)
    approx_latitude: float = Field(ge=-90, le=90)
    approx_longitude: float = Field(ge=-180, le=180)
    availability: Literal["AVAILABLE", "TEMPORARILY_UNAVAILABLE", "NEEDS_CONFIRMATION"] = "NEEDS_CONFIRMATION"
    notification_consent: bool
    urgent_contact_consent: bool = False


class DonorAvailabilityUpdate(BaseModel):
    availability: Literal["AVAILABLE", "TEMPORARILY_UNAVAILABLE", "NEEDS_CONFIRMATION"]
    notification_consent: bool | None = None
    urgent_contact_consent: bool | None = None


class DonorProfileResponse(BaseModel):
    blood_group: str
    locality: str
    availability: str
    notification_consent: bool
    urgent_contact_consent: bool
    last_confirmed_at: datetime | None


class BloodRequestCreate(BaseModel):
    facility: str = Field(min_length=2, max_length=200)
    locality: str = Field(min_length=2, max_length=120)
    approx_latitude: float = Field(ge=-90, le=90)
    approx_longitude: float = Field(ge=-180, le=180)
    blood_group: BloodGroup
    required_donors: int = Field(ge=1, le=50)
    required_by: datetime
    urgency: Literal["URGENT", "HIGH", "ROUTINE"] = "URGENT"
    facility_reference: str | None = Field(default=None, max_length=100)
    additional_information: str | None = Field(default=None, max_length=2000)


class VerificationDecision(BaseModel):
    decision: Literal["VERIFY", "REJECT", "CLARIFICATION"]
    notes: str | None = Field(default=None, max_length=2000)


class BloodRequestResponse(BaseModel):
    id: UUID
    public_id: str
    facility: str
    locality: str
    blood_group: str
    required_donors: int
    required_by: datetime
    urgency: str
    status: str
    current_stage: int
    outreach_active: bool
    coordinator_user_id: UUID | None
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    fulfilled_at: datetime | None


class DonorMatchResponse(BaseModel):
    donor_code: str
    blood_group: str
    locality: str
    distance_km: float | None
    availability_confirmed_at: datetime | None
    notification_consent: bool
    response: str


class DonorEmergencyAlertResponse(BaseModel):
    notification_id: UUID
    request_id: UUID
    public_id: str
    facility: str
    locality: str
    blood_group: str
    distance_km: float | None
    required_by: datetime
    response_deadline: datetime


class OutreachResponse(BaseModel):
    request_id: UUID
    stage: int
    radius_min_km: int
    radius_max_km: int
    duration_seconds: int
    notifications_sent: int
    accepted: int
    declined: int
    no_response: int
    remaining: int
    outreach_active: bool
    status: str


class DashboardStats(BaseModel):
    contactable_donors: int
    donors_needing_confirmation: int
    active_requests: int
    pending_verification: int
    fulfilled_today: int
    alerts_cancelled: int


class MessageResponse(BaseModel):
    message: str