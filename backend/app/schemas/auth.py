from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.phase1 import RoleName


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: RoleName
    phone: str | None = Field(default=None, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


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
