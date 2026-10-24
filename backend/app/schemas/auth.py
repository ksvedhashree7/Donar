from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.phase1 import RoleName


class BloodBankRegistration(BaseModel):
    institution_name: str = Field(min_length=2, max_length=200)
    institution_type: str = Field(min_length=2, max_length=80)
    representative_name: str = Field(min_length=2, max_length=160)
    official_phone: str = Field(min_length=7, max_length=50)
    address: str = Field(min_length=5, max_length=300)
    locality: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    pincode: str = Field(pattern=r"^\d{6}$")
    registration_number: str = Field(min_length=3, max_length=100)
    issuing_authority: str = Field(min_length=2, max_length=160)
    license_expires_at: datetime | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: RoleName
    phone: str | None = Field(default=None, max_length=50)
    blood_bank: BloodBankRegistration | None = None

    @model_validator(mode="after")
    def validate_registration_role(self) -> "RegisterRequest":
        if self.role == RoleName.BLOOD_BANK and self.blood_bank is None:
            raise ValueError("Blood bank registration details are required")
        if self.role == RoleName.GENERAL_DONOR and self.blood_bank is not None:
            raise ValueError("Blood bank details are only valid for Blood Bank accounts")
        if self.role == RoleName.BLOOD_BANK and self.phone is None and self.blood_bank:
            self.phone = self.blood_bank.official_phone
        if not self.phone:
            raise ValueError("A phone number is required")
        if self.role == RoleName.ADMIN:
            raise ValueError("Administrator accounts cannot self-register")
        return self


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=2, max_length=100)
    role: RoleName | None = None
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_login_identifier(self) -> "LoginRequest":
        if (self.email is None) == (self.username is None):
            raise ValueError("Provide exactly one email address or username")
        if self.username is not None and self.role != RoleName.ADMIN:
            raise ValueError("Username login is reserved for administrators")
        return self


class OtpVerifyRequest(BaseModel):
    challenge_id: UUID
    code: str = Field(pattern=r"^\d{6}$")


class ResetPasswordRequest(OtpVerifyRequest):
    new_password: str = Field(min_length=12, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class AuthTokens(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthenticatedSession(BaseModel):
    role: RoleName


class ChallengeResponse(BaseModel):
    challenge_id: UUID
    requires_otp: bool = True


class LoginChallengeResponse(ChallengeResponse):
    requires_totp: bool = False


class RegisterResponse(ChallengeResponse):
    message: str = "Verification code sent"


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TotpVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
