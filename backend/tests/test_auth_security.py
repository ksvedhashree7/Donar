import logging
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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
    AuditLog,
    Base,
    BloodBankStaff,
    BloodDonorProfile,
    BloodOrganisation,
    BloodRequest,
    BloodRequestReservation,
    Role,
    RoleName,
    User,
    UserStatus,
)
from app.services import auth as auth_service


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


def test_account_role_model_contains_only_the_three_supported_roles() -> None:
    assert {role.value for role in RoleName} == {"ADMIN", "BLOOD_BANK", "GENERAL_DONOR"}


def test_general_donor_cannot_enumerate_donor_profiles(client, session_factory) -> None:
    with session_factory() as db:
        role = Role(name=RoleName.GENERAL_DONOR, description="test")
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
        token = create_access_token(user.id, RoleName.GENERAL_DONOR.value)

    profile_response = client.get("/donors/profile", headers={"Authorization": f"Bearer {token}"})
    directory_response = client.get("/donors", headers={"Authorization": f"Bearer {token}"})
    assert profile_response.status_code == 404
    assert directory_response.status_code == 404


def test_registration_otp_and_refresh_rotation(client, session_factory, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.services.auth")
    registered = client.post(
        "/auth/register",
        json={
            "email": "donor@example.com",
            "password": "SamplePassword123!",
            "role": "GENERAL_DONOR",
            "phone": "+919876543210",
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


def test_admin_username_login_and_role_mismatch(client, session_factory, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.services.auth")
    assert client.get("/auth/session").status_code == 401
    with session_factory() as db:
        admin_role = Role(name=RoleName.ADMIN, description="administrator")
        donor_role = Role(name=RoleName.GENERAL_DONOR, description="donor")
        db.add_all([admin_role, donor_role])
        db.flush()
        admin = User(
            role_id=admin_role.id,
            username="admin-seed",
            email="admin-seed@example.com",
            password_hash=hash_password("SamplePassword123!"),
            status=UserStatus.ACTIVE,
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        donor = User(
            role_id=donor_role.id,
            username="donor-seed",
            email="donor-seed@example.com",
            password_hash=hash_password("SamplePassword123!"),
            status=UserStatus.ACTIVE,
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add_all([admin, donor])
        db.commit()

    login = client.post(
        "/auth/login",
        json={
            "username": "admin-seed",
            "password": "SamplePassword123!",
            "role": "ADMIN",
        },
    )
    assert login.status_code == 200
    challenge_id = login.json()["challenge_id"]
    otp_line = next(record.message for record in caplog.records if "Mock OTP" in record.message)
    otp_code = re.search(r"code=(\d{6})", otp_line).group(1)
    verified = client.post(
        "/auth/otp/verify",
        json={"challenge_id": challenge_id, "code": otp_code},
    )
    assert verified.status_code == 200
    assert verified.json()["access_token"]
    session_response = client.get(
        "/auth/session",
        headers={"Authorization": f"Bearer {verified.json()['access_token']}"},
    )
    assert session_response.status_code == 200
    assert session_response.json() == {"role": "ADMIN"}

    email_login = client.post(
        "/auth/login",
        json={
            "email": "donor-seed@example.com",
            "password": "SamplePassword123!",
            "role": "GENERAL_DONOR",
        },
    )
    assert email_login.status_code == 200

    mismatched_role = client.post(
        "/auth/login",
        json={
            "email": "donor-seed@example.com",
            "password": "SamplePassword123!",
            "role": "ADMIN",
        },
    )
    assert mismatched_role.status_code == 401


def test_blood_bank_registration_requires_details_and_admin_review(
    client, session_factory
) -> None:
    missing_details = client.post(
        "/auth/register",
        json={
            "email": "bank@example.com",
            "password": "SamplePassword123!",
            "role": "BLOOD_BANK",
        },
    )
    assert missing_details.status_code == 422
    admin_registration = client.post(
        "/auth/register",
        json={
            "email": "admin@example.com",
            "password": "SamplePassword123!",
            "role": "ADMIN",
        },
    )
    assert admin_registration.status_code == 422

    registered = client.post(
        "/auth/register",
        json={
            "email": "bank@example.com",
            "password": "SamplePassword123!",
            "role": "BLOOD_BANK",
            "blood_bank": {
                "institution_name": "Chennai Blood Centre",
                "institution_type": "Blood centre",
                "representative_name": "Authorised Representative",
                "official_phone": "+914400000000",
                "address": "1 Sample Road",
                "locality": "Adyar",
                "city": "Chennai",
                "district": "Chennai",
                "state": "Tamil Nadu",
                "pincode": "600020",
                "registration_number": "TN-BB-001",
                "issuing_authority": "State Licensing Authority",
            },
        },
    )
    assert registered.status_code == 201
    with session_factory() as db:
        organisation = db.query(BloodOrganisation).filter_by(name="Chennai Blood Centre").one()
        bank_user = db.query(User).filter_by(email="bank@example.com").one()
        association = db.query(BloodBankStaff).filter_by(user_id=bank_user.id).one()
        assert association.organisation_id == organisation.id
        assert organisation.verification_status == "PENDING"
        assert organisation.is_active is False

        admin_role = Role(name=RoleName.ADMIN, description="administrator")
        db.add(admin_role)
        db.flush()
        admin = User(
            role_id=admin_role.id,
            username="review-admin",
            email="review-admin@example.com",
            password_hash=hash_password("SamplePassword123!"),
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        admin_token = create_access_token(admin.id, RoleName.ADMIN.value)
        organisation_id = organisation.id

    reviewed = client.post(
        f"/admin/blood-banks/{organisation_id}/verification",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"decision": "VERIFY"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["verification_status"] == "VERIFIED"
    assert reviewed.json()["is_active"] is True


def test_failed_logins_lock_account(session_factory) -> None:
    with session_factory() as db:
        role = Role(name=RoleName.GENERAL_DONOR, description="donor")
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


def test_phone_verification_is_required_before_contact_sharing(client, session_factory, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.services.auth")
    with session_factory() as db:
        role = Role(name=RoleName.GENERAL_DONOR, description="donor")
        db.add(role)
        db.flush()
        user = User(
            role_id=role.id,
            username="phone-user",
            email="phone@example.com",
            phone="+919876543210",
            password_hash=hash_password("SamplePassword123!"),
            status=UserStatus.ACTIVE,
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        token = create_access_token(user.id, RoleName.GENERAL_DONOR.value)
        user_id = user.id

    headers = {"Authorization": f"Bearer {token}"}
    requested = client.post("/auth/phone/verify/request", headers=headers)
    assert requested.status_code == 200
    challenge_id = requested.json()["challenge_id"]
    otp_line = next(
        record.message
        for record in caplog.records
        if f"challenge_id={challenge_id}" in record.message
    )
    code = re.search(r"code=(\d{6})", otp_line).group(1)
    verified = client.post(
        "/auth/phone/verify",
        headers=headers,
        json={"challenge_id": challenge_id, "code": code},
    )
    assert verified.status_code == 204
    with session_factory() as db:
        assert db.get(User, user_id).phone_verified_at is not None


def test_donor_contact_is_released_only_to_request_owner_with_consent(
    client, session_factory
) -> None:
    with session_factory() as db:
        role = Role(name=RoleName.GENERAL_DONOR, description="general donor")
        db.add(role)
        db.flush()
        requester = User(
            role_id=role.id,
            username="contact-requester",
            email="contact-requester@example.com",
            phone="+919800000001",
            password_hash="not-used",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        donor_user = User(
            role_id=role.id,
            username="contact-donor",
            email="contact-donor@example.com",
            phone="+919800000002",
            password_hash="not-used",
            status=UserStatus.ACTIVE,
            is_active=True,
            phone_verified_at=datetime.now(timezone.utc),
        )
        other_requester = User(
            role_id=role.id,
            username="other-requester",
            email="other-requester@example.com",
            phone="+919800000003",
            password_hash="not-used",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        db.add_all((requester, donor_user, other_requester))
        db.flush()
        donor_profile = BloodDonorProfile(
            user_id=donor_user.id,
            blood_group="O+",
            locality="Adyar",
            notification_consent=True,
            urgent_contact_consent=False,
        )
        request = BloodRequest(
            public_id="UTH-CONTACT-1",
            requester_user_id=requester.id,
            facility="Sample Hospital",
            locality="Adyar",
            blood_group="O+",
            required_donors=1,
            required_by=datetime.now(timezone.utc) + timedelta(hours=1),
            status="COORDINATION",
        )
        db.add_all((donor_profile, request))
        db.flush()
        reservation = BloodRequestReservation(
            request_id=request.id,
            donor_id=donor_profile.id,
            unit_number=1,
            status="ACTIVE",
            contact_shared=True,
            reserved_at=datetime.now(timezone.utc),
            grace_until=datetime.now(timezone.utc) + timedelta(minutes=2),
        )
        db.add(reservation)
        db.commit()
        request_id = request.id
        reservation_id = reservation.id
        requester_token = create_access_token(requester.id, RoleName.GENERAL_DONOR.value)
        donor_token = create_access_token(donor_user.id, RoleName.GENERAL_DONOR.value)
        other_token = create_access_token(other_requester.id, RoleName.GENERAL_DONOR.value)

    endpoint = f"/requests/{request_id}/reservations/{reservation_id}/contact"
    released = client.get(
        endpoint,
        headers={"Authorization": f"Bearer {requester_token}"},
    )
    unauthorized = client.get(
        endpoint,
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert released.status_code == 200
    assert released.json() == {"phone": "+919800000002"}
    assert unauthorized.status_code == 404

    revoked = client.post(
        f"/donors/reservations/{reservation_id}/revoke-contact-sharing",
        headers={"Authorization": f"Bearer {donor_token}"},
    )
    assert revoked.status_code == 200
    assert client.get(
        endpoint,
        headers={"Authorization": f"Bearer {requester_token}"},
    ).status_code == 403


def test_totp_setup_encrypts_secret_and_verifies_code(session_factory) -> None:
    with session_factory() as db:
        role = Role(name=RoleName.GENERAL_DONOR, description="donor")
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
        role = Role(name=RoleName.GENERAL_DONOR, description="donor")
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


def test_password_hash_and_access_token_primitives() -> None:
    encoded = hash_password("SamplePassword123!")
    assert encoded.startswith("$argon2id$")
    assert verify_password("SamplePassword123!", encoded)
    assert not verify_password("wrong", encoded)
