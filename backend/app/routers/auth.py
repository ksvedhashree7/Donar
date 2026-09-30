from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import require_role
from app.models import OtpChallenge, RoleName, User
from app.schemas.auth import (
    AuthTokens,
    ChallengeResponse,
    ForgotPasswordRequest,
    LoginChallengeResponse,
    LoginRequest,
    OtpVerifyRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TotpSetupResponse,
    TotpVerifyRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)
ALL_ROLES = tuple(RoleName)


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/auth",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegisterResponse:
    challenge = auth_service.register_user(
        db,
        email=str(payload.email),
        password=payload.password,
        role_name=payload.role,
        phone=payload.phone,
    )
    db.commit()
    return RegisterResponse(challenge_id=challenge.id)


@router.post("/login", response_model=LoginChallengeResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> LoginChallengeResponse:
    user, challenge = auth_service.authenticate_password(
        db,
        email=str(payload.email),
        password=payload.password,
    )
    return LoginChallengeResponse(
        challenge_id=challenge.id,
        requires_otp=not user.totp_enabled,
        requires_totp=user.totp_enabled,
    )


@router.post("/otp/verify", response_model=AuthTokens)
@limiter.limit("8/minute")
def verify_otp(
    request: Request,
    payload: OtpVerifyRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthTokens:
    challenge = db.get(OtpChallenge, payload.challenge_id)
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
        )
    if challenge.purpose == "EMAIL_VERIFY":
        tokens, refresh_token = auth_service.complete_email_verification(
            db, challenge.id, payload.code
        )
    elif challenge.purpose == "LOGIN":
        tokens, refresh_token = auth_service.complete_login_otp(db, challenge.id, payload.code)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
        )
    _set_refresh_cookie(response, refresh_token)
    return tokens


@router.post("/totp/challenge/verify", response_model=AuthTokens)
@limiter.limit("8/minute")
def verify_totp_login(
    request: Request,
    payload: OtpVerifyRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthTokens:
    tokens, refresh_token = auth_service.complete_totp_login(db, payload.challenge_id, payload.code)
    _set_refresh_cookie(response, refresh_token)
    return tokens


@router.post("/refresh", response_model=AuthTokens)
@limiter.limit("10/minute")
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthTokens:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required"
        )
    tokens, replacement, _ = auth_service.rotate_refresh_token(db, refresh_token)
    _set_refresh_cookie(response, replacement)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*ALL_ROLES))],
) -> Response:
    del user
    auth_service.revoke_refresh_token(db, request.cookies.get("refresh_token"))
    response.delete_cookie("refresh_token", path="/auth", httponly=True, samesite="lax")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*ALL_ROLES))],
) -> Response:
    auth_service.revoke_all_sessions(db, user.id)
    response.delete_cookie("refresh_token", path="/auth", httponly=True, samesite="lax")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/forgot-password", response_model=ChallengeResponse)
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ChallengeResponse:
    challenge = auth_service.begin_password_reset(db, str(payload.email))
    return ChallengeResponse(challenge_id=challenge.id if challenge else uuid4())


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    auth_service.reset_password(db, payload.challenge_id, payload.code, payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/totp/setup", response_model=TotpSetupResponse)
def totp_setup(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*ALL_ROLES))],
) -> TotpSetupResponse:
    secret, uri = auth_service.setup_totp(user)
    db.commit()
    return TotpSetupResponse(secret=secret, provisioning_uri=uri)


@router.post("/totp/verify", status_code=status.HTTP_204_NO_CONTENT)
def totp_verify(
    payload: TotpVerifyRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_role(*ALL_ROLES))],
) -> Response:
    auth_service.enable_totp(user, payload.code)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
