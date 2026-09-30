import logging
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pyotp
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import require_role
from app.core.security import (
    create_access_token,
    decrypt_totp_secret,
    hash_password,
    verify_password,
)
from app.main import app
from app.models import (
    AccessGrant,
    AuditLog,
    Base,
    Consent,
    ConsentStatus,
    Doctor,
    Donor,
    FieldVerification,
    Hospital,
    Role,
    RoleName,
    User,
    UserStatus,
    VerificationStatus,
)
from app.services import auth as auth_service
from app.services.policies import can_edit_verified_medical, can_view_donor_medical


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    previous_factory = app.state.session_factory
    app.state.session_factory = factory
    yield factory
    app.state.session_factory = previous_factory
    engine.dispose()


@pytest.fixture
def client(session_factory):
    return TestClient(app)


@pytest.mark.parametrize(
    ("required_role", "actor_role"),
    [(required, actor) for required in RoleName for actor in RoleName],
)
def test_require_role_allows_only_matching_role(required_role, actor_role) -> None:
    dependency = require_role(required_role)
    actor = SimpleNamespace(role=SimpleNamespace(name=actor_role))
    if required_role == actor_role:
        assert dependency(actor) is actor
    else:
        with pytest.raises(HTTPException) as error:
            dependency(actor)
        assert error.value.status_code == 403


def test_recipient_cannot_list_donors(client, session_factory) -> None:
    with session_factory() as db:
        role = Role(name=RoleName.RECIPIENT, description="test")
        db.add(role)
        db.flush()
        user = User(
            role_id=role.id,
            username="recipient-test",
            email="recipient@example.com",
            password_hash=hash_password("SamplePassword123!"),
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add(user)
        db.commit()
        token = create_access_token(user.id, RoleName.RECIPIENT.value)

    response = client.get("/donors", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_registration_otp_and_refresh_rotation(client, session_factory, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.services.auth")
    registered = client.post(
        "/auth/register",
        json={
            "email": "donor@example.com",
            "password": "SamplePassword123!",
            "role": "DONOR",
        },
    )
    assert registered.status_code == 201
    challenge_id = registered.json()["challenge_id"]
    otp_line = next(record.message for record in caplog.records if "Mock OTP" in record.message)
    otp_code = re.search(r"code=(\d{6})", otp_line).group(1)

    verified = client.post(
        "/auth/otp/verify", json={"challenge_id": challenge_id, "code": otp_code}
    )
    assert verified.status_code == 200
    assert verified.json()["token_type"] == "bearer"
    old_refresh = client.cookies.get("refresh_token")
    assert old_refresh

    rotated = client.post("/auth/refresh")
    assert rotated.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh

    client.cookies.set("refresh_token", old_refresh, path="/auth")
    replayed = client.post("/auth/refresh")
    assert replayed.status_code == 401

    with session_factory() as db:
        assert (
            db.query(User).filter_by(email="donor@example.com").one().email_verified_at is not None
        )
        audit_rows = db.query(AuditLog).order_by(AuditLog.created_at, AuditLog.id).all()
        assert len(audit_rows) >= 4
        assert all(row.row_hash for row in audit_rows)
        assert all(
            row.prev_hash == audit_rows[index - 1].row_hash
            for index, row in enumerate(audit_rows)
            if index
        )


def test_failed_logins_lock_account(session_factory) -> None:
    with session_factory() as db:
        role = Role(name=RoleName.DONOR, description="donor")
        db.add(role)
        db.flush()
        user = User(
            role_id=role.id,
            username="locked-user",
            email="locked@example.com",
            password_hash=hash_password("SamplePassword123!"),
            status=UserStatus.ACTIVE,
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()

        for _ in range(5):
            with pytest.raises(HTTPException) as error:
                auth_service.authenticate_password(
                    db,
                    email="locked@example.com",
                    password="WrongPassword123!",
                )
            assert error.value.status_code == 401

        with pytest.raises(HTTPException) as error:
            auth_service.authenticate_password(
                db,
                email="locked@example.com",
                password="SamplePassword123!",
            )
        assert error.value.status_code == 423
        assert db.query(User).filter_by(email="locked@example.com").one().failed_login_attempts == 5


def test_totp_setup_encrypts_secret_and_verifies_code(session_factory) -> None:
    with session_factory() as db:
        role = Role(name=RoleName.DONOR, description="donor")
        db.add(role)
        db.flush()
        user = User(
            role_id=role.id,
            username="totp-user",
            email="totp@example.com",
            password_hash="not-used",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add(user)
        db.flush()

        secret, provisioning_uri = auth_service.setup_totp(user)
        assert "otpauth://totp/" in provisioning_uri
        assert user.totp_secret != secret
        assert decrypt_totp_secret(user.totp_secret) == secret
        auth_service.enable_totp(user, pyotp.TOTP(secret).now())
        assert user.totp_enabled


def test_forgot_password_response_does_not_disclose_account(
    client, session_factory, caplog
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.auth")
    with session_factory() as db:
        role = Role(name=RoleName.DONOR, description="donor")
        db.add(role)
        db.flush()
        db.add(
            User(
                role_id=role.id,
                username="reset-user",
                email="reset@example.com",
                password_hash=hash_password("OldPassword123!"),
                status=UserStatus.ACTIVE,
                is_active=True,
                email_verified_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    known = client.post("/auth/forgot-password", json={"email": "reset@example.com"})
    unknown = client.post("/auth/forgot-password", json={"email": "missing@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert set(known.json()) == set(unknown.json())
    reset_otp_line = next(
        record.message for record in caplog.records if "Mock OTP" in record.message
    )
    reset_code = re.search(r"code=(\d{6})", reset_otp_line).group(1)
    reset = client.post(
        "/auth/reset-password",
        json={
            "challenge_id": known.json()["challenge_id"],
            "code": reset_code,
            "new_password": "NewSamplePassword123!",
        },
    )
    assert reset.status_code == 204

    old_password = client.post(
        "/auth/login",
        json={"email": "reset@example.com", "password": "OldPassword123!"},
    )
    new_password = client.post(
        "/auth/login",
        json={"email": "reset@example.com", "password": "NewSamplePassword123!"},
    )
    assert old_password.status_code == 401
    assert new_password.status_code == 200


def test_donor_medical_access_requires_hospital_grant_and_consent(session_factory) -> None:
    with session_factory() as db:
        hospital = Hospital(name="Test Hospital", code="TEST", city="Chennai")
        db.add(hospital)
        db.flush()
        doctor_role = Role(name=RoleName.DOCTOR, description="doctor")
        donor_role = Role(name=RoleName.DONOR, description="donor")
        db.add_all([doctor_role, donor_role])
        db.flush()
        doctor_user = User(
            role_id=doctor_role.id,
            username="doctor-user",
            email="doctor@example.com",
            password_hash="not-used",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        donor_user = User(
            role_id=donor_role.id,
            username="donor-user",
            email="donor2@example.com",
            password_hash="not-used",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add_all([doctor_user, donor_user])
        db.flush()
        doctor = Doctor(
            user_id=doctor_user.id, hospital_id=hospital.id, first_name="Test", last_name="Doctor"
        )
        donor = Donor(
            user_id=donor_user.id,
            hospital_id=hospital.id,
            donor_code="DNR-TEST",
            first_name="Test",
            last_name="Donor",
        )
        db.add_all([doctor, donor])
        db.flush()
        db.refresh(doctor_user)
        db.refresh(donor_user)

        assert not can_view_donor_medical(doctor_user, donor, "medical_evaluation", db)
        db.add_all(
            [
                AccessGrant(
                    donor_id=donor.id,
                    granted_to_user_id=doctor_user.id,
                    purpose="medical_evaluation",
                    is_active=True,
                    valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
                ),
                Consent(
                    donor_id=donor.id,
                    purpose="medical_evaluation",
                    version=1,
                    status=ConsentStatus.ACTIVE,
                    is_withdrawable=True,
                ),
            ]
        )
        db.flush()
        assert can_view_donor_medical(doctor_user, donor, "medical_evaluation", db)
        assert can_view_donor_medical(donor_user, donor, "medical_evaluation", db)
        assert not can_view_donor_medical(doctor_user, donor, "unknown-purpose", db)


def test_admin_cannot_edit_verified_medical_field(session_factory) -> None:
    with session_factory() as db:
        admin_role = Role(name=RoleName.ADMIN, description="admin")
        db.add(admin_role)
        db.flush()
        admin = User(
            role_id=admin_role.id,
            username="admin-user",
            email="admin@example.com",
            password_hash="not-used",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        field = FieldVerification(
            donor_id=uuid4(),
            field_name="blood_group",
            value="O+",
            status=VerificationStatus.VERIFIED,
        )
        db.add_all([admin, field])
        db.flush()
        db.refresh(admin)
        assert not can_edit_verified_medical(admin, field, db)


def test_password_hash_and_access_token_primitives() -> None:
    encoded = hash_password("SamplePassword123!")
    assert encoded.startswith("$argon2id$")
    assert verify_password("SamplePassword123!", encoded)
    assert not verify_password("wrong", encoded)
