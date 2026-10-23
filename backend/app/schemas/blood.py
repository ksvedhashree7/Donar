from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

BloodGroup = Literal["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]
BloodComponent = Literal["RED_CELLS", "PLASMA", "PLATELETS", "WHOLE_BLOOD", "OTHER"]


class DonorProfileCreate(BaseModel):
    blood_group: BloodGroup
    blood_group_verification_organisation_id: UUID | None = None
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


class DonorBloodGroupUpdate(BaseModel):
    blood_group: BloodGroup


class DonorBloodGroupVerificationBankUpdate(BaseModel):
    organisation_id: UUID


class BloodGroupVerificationQueueItem(BaseModel):
    donor_profile_id: UUID
    blood_group: str


class DonorScreeningReviewRequest(BaseModel):
    screening_completed: bool


class DonorProfileResponse(BaseModel):
    blood_group: str
    blood_group_verified: bool
    blood_group_verification_organisation_id: UUID | None
    screening_completed: bool
    potential_recipient_groups: list[str]
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
    component: BloodComponent = "RED_CELLS"
    required_donors: int = Field(ge=1, le=50)
    required_by: datetime
    urgency: Literal["URGENT", "HIGH", "ROUTINE"] = "URGENT"
    facility_reference: str | None = Field(default=None, max_length=100)
    additional_information: str | None = Field(default=None, max_length=2000)


class BloodBankResponse(BaseModel):
    id: UUID
    name: str
    institution_type: str | None
    representative_name: str | None
    official_phone: str | None
    address: str | None
    locality: str
    city: str
    district: str | None
    state: str | None
    pincode: str | None
    registration_number: str | None
    issuing_authority: str | None
    license_expires_at: datetime | None
    verification_status: str
    verification_notes: str | None
    verified_at: datetime | None
    is_active: bool


class VerifiedBloodBankOption(BaseModel):
    id: UUID
    name: str
    locality: str
    city: str


class BloodBankVerificationDecision(BaseModel):
    decision: Literal["VERIFY", "REJECT", "REQUEST_CORRECTION", "SUSPEND"]
    notes: str | None = Field(default=None, min_length=5, max_length=2000)

    @model_validator(mode="after")
    def require_explanation(self) -> "BloodBankVerificationDecision":
        if self.decision != "VERIFY" and not self.notes:
            raise ValueError("An explanation is required for this decision")
        return self


class BloodGroupVerificationRequest(BaseModel):
    confirmed_blood_group: BloodGroup


class AcceptNotificationRequest(BaseModel):
    share_contact: bool


class AcceptNotificationResponse(BaseModel):
    message: str
    reservation_id: UUID
    grace_until: datetime
    contact_shared: bool


class DonorReservationResponse(BaseModel):
    reservation_id: UUID
    request_id: UUID
    public_id: str
    facility: str
    locality: str
    blood_group: str
    unit_number: int
    status: str
    reserved_at: datetime
    grace_until: datetime


class ContactShareResponse(BaseModel):
    phone: str


class ReservationCancellationRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class DonationCompletionReport(BaseModel):
    component: Literal["WHOLE_BLOOD", "PACKED_RED_CELLS", "PLATELETS", "PLASMA", "OTHER"]
    quantity_ml: int | None = Field(default=None, ge=1, le=100000)


class CompletionVerificationDecision(BaseModel):
    decision: Literal["VERIFY", "REQUEST_CORRECTION"]
    notes: str | None = Field(default=None, min_length=5, max_length=2000)

    @model_validator(mode="after")
    def require_correction_notes(self) -> "CompletionVerificationDecision":
        if self.decision == "REQUEST_CORRECTION" and not self.notes:
            raise ValueError("An explanation is required when requesting a correction")
        return self


class DonationCompletionResponse(BaseModel):
    id: UUID
    request_id: UUID
    reservation_id: UUID
    component: str
    quantity_ml: int | None
    status: str
    reported_at: datetime
    verified_at: datetime | None
    verification_notes: str | None


class VerificationDecision(BaseModel):
    decision: Literal["VERIFY", "REJECT", "CLARIFICATION"]
    notes: str | None = Field(default=None, max_length=2000)


class BloodRequestResponse(BaseModel):
    id: UUID
    public_id: str
    facility: str
    locality: str
    blood_group: str
    component: str
    required_donors: int
    required_by: datetime
    urgency: str
    status: str
    current_stage: int
    outreach_active: bool
    assigned_staff_user_id: UUID | None
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    fulfilled_at: datetime | None


class DonorMatchResponse(BaseModel):
    donor_profile_id: UUID
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
    component: str
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


class BloodGroupCount(BaseModel):
    blood_group: str
    count: int


class BloodGroupRequestCount(BaseModel):
    required_blood_group: str
    count: int


class DonorGroupNotificationStats(BaseModel):
    donor_blood_group: str
    notifications_sent: int
    accepted: int
    acceptance_rate: float


class BloodCompatibilityAnalytics(BaseModel):
    requests_by_required_group: list[BloodGroupRequestCount]
    potential_donors_identified: int
    notifications_by_donor_group: list[DonorGroupNotificationStats]
    institution_confirmed_fulfilments: int
    unfulfilled_requests: int
    average_response_seconds: float | None


class MessageResponse(BaseModel):
    message: str