from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pyotp
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_otp,
    generate_totp_secret,
    hash_otp,
    hash_password,
    hash_token,
    verify_otp,
    verify_password,
    verify_totp,
)
from app.models import OtpChallenge, RefreshSession, Role, RoleName, User, UserStatus
from app.schemas.auth import AuthTokens

logger = logging.getLogger(__name__)
OTP_PURPOSES = {"EMAIL_VERIFY", "LOGIN", "PASSWORD_RESET", "TOTP_LOGIN"}


def issue_challenge(db: Session, user: User, purpose: str) -> OtpChallenge:
    settings = get_settings()
    challenge = OtpChallenge(
        id=uuid4(),
        user_id=user.id,
        purpose=purpose,
        code_hash="",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expiry_minutes),
        attempts=0,
    )
    code = generate_otp()
    challenge.code_hash = hash_otp(challenge.id, code)
    db.add(challenge)
    db.flush()
    if settings.env == "development":
        logger.info("Mock OTP challenge_id=%s code=%s", challenge.id, code)
    return challenge


def verify_challenge(db: Session, challenge_id: UUID, code: str, purpose: str) -> OtpChallenge:
    settings = get_settings()
    challenge = db.get(OtpChallenge, challenge_id)
    now = datetime.now(timezone.utc)
    if (
        challenge is None
        or challenge.purpose != purpose
        or challenge.consumed_at is not None
        or _as_utc(challenge.expires_at) <= now
        or challenge.attempts >= settings.otp_max_attempts
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
        )
    if not verify_otp(challenge.id, code, challenge.code_hash):
        challenge.attempts += 1
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
        )
    challenge.attempts += 1
    challenge.consumed_at = now
    return challenge


def register_user(
    db: Session, *, email: str, password: str, role_name: RoleName, phone: str | None
) -> OtpChallenge:
    if role_name not in {RoleName.DONOR, RoleName.REQUESTER, RoleName.RECIPIENT}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-registration is not allowed for this role",
        )
    normalized_email = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == normalized_email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unable to create account")
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name, description=f"{role_name.value.title()} account")
        db.add(role)
        db.flush()
    user = User(
        role_id=role.id,
        username=f"user-{uuid4().hex}",
        email=normalized_email,
        phone=phone,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        is_active=True,
        failed_login_attempts=0,
    )
    db.add(user)
    db.flush()
    return issue_challenge(db, user, "EMAIL_VERIFY")


def authenticate_password(db: Session, *, email: str, password: str) -> tuple[User, OtpChallenge]:
    settings = get_settings()
    user = db.scalar(
        select(User).options(joinedload(User.role)).where(User.email == email.strip().lower())
    )
    if (
        user is not None
        and user.lockout_until
        and _as_utc(user.lockout_until) > datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account temporarily locked")
    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.login_max_attempts:
                user.lockout_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.login_lockout_minutes
                )
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active or user.status != UserStatus.ACTIVE or user.email_verified_at is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user.failed_login_attempts = 0
    user.lockout_until = None
    user.last_login_at = datetime.now(timezone.utc)
    if user.totp_enabled:
        challenge = _create_totp_challenge(db, user)
    else:
        challenge = issue_challenge(db, user, "LOGIN")
    db.commit()
    return user, challenge


def complete_email_verification(
    db: Session, challenge_id: UUID, code: str
) -> tuple[AuthTokens, str]:
    challenge = verify_challenge(db, challenge_id, code, "EMAIL_VERIFY")
    user = _challenge_user(db, challenge)
    user.email_verified_at = datetime.now(timezone.utc)
    tokens, refresh_token = create_token_pair(db, user)
    db.commit()
    return tokens, refresh_token


def complete_login_otp(db: Session, challenge_id: UUID, code: str) -> tuple[AuthTokens, str]:
    challenge = verify_challenge(db, challenge_id, code, "LOGIN")
    user = _challenge_user(db, challenge)
    tokens, refresh_token = create_token_pair(db, user)
    db.commit()
    return tokens, refresh_token


def create_token_pair(
    db: Session, user: User, family_id: UUID | None = None
) -> tuple[AuthTokens, str]:
    settings = get_settings()
    refresh_token = create_refresh_token()
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            family_id=family_id or uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
        )
    )
    return (
        AuthTokens(
            access_token=create_access_token(user.id, user.role.name.value),
            expires_in=settings.access_token_minutes * 60,
        ),
        refresh_token,
    )


def rotate_refresh_token(db: Session, refresh_token: str) -> tuple[AuthTokens, str, User]:
    now = datetime.now(timezone.utc)
    token_hash = hash_token(refresh_token)
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash))
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    if session.revoked_at is not None:
        db.execute(
            update(RefreshSession)
            .where(RefreshSession.family_id == session.family_id)
            .values(revoked_at=now)
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    if _as_utc(session.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    user = db.scalar(select(User).options(joinedload(User.role)).where(User.id == session.user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    session.revoked_at = now
    tokens, replacement = create_token_pair(db, user, session.family_id)
    db.commit()
    return tokens, replacement, user


def revoke_refresh_token(db: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    session = db.scalar(
        select(RefreshSession).where(RefreshSession.token_hash == hash_token(refresh_token))
    )
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_sessions(db: Session, user_id: UUID) -> None:
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()


def begin_password_reset(db: Session, email: str) -> OtpChallenge | None:
    user = db.scalar(
        select(User).where(User.email == email.strip().lower(), User.is_active.is_(True))
    )
    if user is None:
        return None
    challenge = issue_challenge(db, user, "PASSWORD_RESET")
    db.commit()
    return challenge


def reset_password(db: Session, challenge_id: UUID, code: str, new_password: str) -> None:
    challenge = verify_challenge(db, challenge_id, code, "PASSWORD_RESET")
    user = _challenge_user(db, challenge)
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.lockout_until = None
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()


def setup_totp(user: User) -> tuple[str, str]:
    if user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="TOTP is already enabled")
    secret = generate_totp_secret()
    user.totp_secret = encrypt_totp_secret(secret)
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="Organ Donor Matching Platform"
    )
    return secret, uri


def enable_totp(user: User, code: str) -> None:
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="TOTP setup has not started"
        )
    secret = decrypt_totp_secret(user.totp_secret)
    if not verify_totp(secret, code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid authenticator code"
        )
    user.totp_enabled = True


def complete_totp_login(db: Session, challenge_id: UUID, code: str) -> tuple[AuthTokens, str]:
    challenge = db.get(OtpChallenge, challenge_id)
    now = datetime.now(timezone.utc)
    settings = get_settings()
    if (
        challenge is None
        or challenge.purpose != "TOTP_LOGIN"
        or challenge.consumed_at is not None
        or _as_utc(challenge.expires_at) <= now
        or challenge.attempts >= settings.otp_max_attempts
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
        )
    user = _challenge_user(db, challenge)
    if not user.totp_secret or not verify_totp(decrypt_totp_secret(user.totp_secret), code):
        challenge.attempts += 1
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
        )
    challenge.attempts += 1
    challenge.consumed_at = now
    tokens, refresh_token = create_token_pair(db, user)
    db.commit()
    return tokens, refresh_token


def _create_totp_challenge(db: Session, user: User) -> OtpChallenge:
    settings = get_settings()
    challenge = OtpChallenge(
        user_id=user.id,
        purpose="TOTP_LOGIN",
        code_hash=secrets.token_hex(32),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expiry_minutes),
        attempts=0,
    )
    db.add(challenge)
    db.flush()
    return challenge


def _challenge_user(db: Session, challenge: OtpChallenge) -> User:
    user = db.scalar(
        select(User).options(joinedload(User.role)).where(User.id == challenge.user_id)
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
        )
    return user


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
