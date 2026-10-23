from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    BloodBankStaff,
    BloodDonationRecord,
    BloodDonorProfile,
    BloodNotification,
    BloodOrganisation,
    BloodOutreachBatch,
    BloodRequest,
    BloodRequestReservation,
    BloodRequestStatusHistory,
    Role,
    RoleName,
    User,
    UserStatus,
)
from app.routers.blood import (
    blood_compatibility_analytics,
    create_blood_donor_profile,
    create_blood_request,
    read_rbc_compatibility,
    record_donor_screening_completion,
    verify_donor_blood_group,
)
from app.schemas.blood import (
    BloodGroupVerificationRequest,
    BloodRequestCreate,
    DonorProfileCreate,
    DonorScreeningReviewRequest,
)
from app.services.blood_compatibility import (
    RBC_BLOOD_GROUPS,
    compatibility_matrix,
    compatible_donor_groups,
    compatible_recipient_groups,
    is_rbc_group_compatible,
)
from app.services.blood_outreach import (
    RADIUS_STAGES,
    advance_outreach,
    cancel_reservation,
    record_response,
    report_completion,
    start_outreach,
    stop_outreach,
    verify_completion,
)
from app.worker import advance_due_outreach


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def _user(db, role_name: RoleName, suffix: str) -> User:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        role = Role(name=role_name, description=role_name.value.title())
        db.add(role)
        db.flush()
    user = User(
        role_id=role.id,
        role=role,
        username=f"{suffix}-user",
        email=f"{suffix}@example.test",
        phone="+919876543210",
        password_hash="not-used-by-service-test",
        status=UserStatus.ACTIVE,
        is_active=True,
        phone_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    return user


def _donor(
    db,
    blood_group: str,
    *,
    consent: bool = True,
    available: bool = True,
    verified: bool = True,
    age_days: int = 0,
) -> tuple[User, BloodDonorProfile]:
    user = _user(db, RoleName.GENERAL_DONOR, f"donor-{uuid4().hex}")
    profile = BloodDonorProfile(
        user_id=user.id,
        blood_group=blood_group,
        blood_group_verified_at=datetime.now(timezone.utc) if verified else None,
        screening_completed_at=datetime.now(timezone.utc) if verified else None,
        locality="Adyar",
        approx_latitude=13.0067,
        approx_longitude=80.2570,
        availability="AVAILABLE" if available else "TEMPORARILY_UNAVAILABLE",
        notification_consent=consent,
        urgent_contact_consent=True,
        last_confirmed_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )
    db.add(profile)
    db.flush()
    return user, profile


def _request(db, coordinator: User, required_donors: int = 2) -> BloodRequest:
    request = BloodRequest(
        public_id="UTH-TEST-1024",
        requester_user_id=coordinator.id,
        assigned_staff_user_id=coordinator.id,
        facility="ABC Hospital",
        locality="Adyar",
        approx_latitude=13.0067,
        approx_longitude=80.2570,
        blood_group="O+",
        required_donors=required_donors,
        required_by=datetime.now(timezone.utc) + timedelta(hours=2),
        urgency="URGENT",
        status="VERIFIED",
        verified_by_user_id=coordinator.id,
        verified_at=datetime.now(timezone.utc),
    )
    db.add(request)
    db.flush()
    return request


def test_all_64_rbc_blood_group_combinations() -> None:
    expected = {
        "O-": {"O-"},
        "O+": {"O-", "O+"},
        "A-": {"O-", "A-"},
        "A+": {"O-", "O+", "A-", "A+"},
        "B-": {"O-", "B-"},
        "B+": {"O-", "O+", "B-", "B+"},
        "AB-": {"O-", "A-", "B-", "AB-"},
        "AB+": set(RBC_BLOOD_GROUPS),
    }
    for recipient_group in RBC_BLOOD_GROUPS:
        for donor_group in RBC_BLOOD_GROUPS:
            compatible = donor_group in expected[recipient_group]
            assert is_rbc_group_compatible(donor_group, recipient_group) is compatible
            assert (donor_group in compatible_donor_groups(recipient_group)) is compatible
            assert (recipient_group in compatible_recipient_groups(donor_group)) is compatible


def test_unknown_groups_and_non_red_cell_components_match_nobody() -> None:
    assert compatible_donor_groups("UNKNOWN") == ()
    assert compatible_recipient_groups("UNKNOWN") == ()
    assert compatible_donor_groups("AB+", component="PLASMA") == ()
    assert not is_rbc_group_compatible("UNKNOWN", "AB+")
    assert set(compatibility_matrix()["AB+"]) == set(RBC_BLOOD_GROUPS)
    assert read_rbc_compatibility() == dict(compatibility_matrix())


def test_donor_profile_marks_unverified_group_as_potential_only(db_session) -> None:
    donor_user = _user(db_session, RoleName.GENERAL_DONOR, "unverified-profile")
    payload = DonorProfileCreate(
        blood_group="O+",
        locality="Adyar",
        approx_latitude=13.0067,
        approx_longitude=80.2570,
        notification_consent=True,
    )

    response = create_blood_donor_profile(payload, db_session, donor_user)

    assert response.blood_group == "O+"
    assert response.blood_group_verified is False
    assert response.potential_recipient_groups == ["O+", "A+", "B+", "AB+"]


def test_request_submission_records_initial_status_history(db_session) -> None:
    requester = _user(db_session, RoleName.GENERAL_DONOR, "requester")
    payload = BloodRequestCreate(
        facility="ABC Hospital",
        locality="Adyar",
        approx_latitude=13.0067,
        approx_longitude=80.2570,
        blood_group="O+",
        required_donors=2,
        required_by=datetime.now(timezone.utc) + timedelta(hours=2),
    )

    response = create_blood_request(payload, db_session, requester)

    history = db_session.scalar(
        select(BloodRequestStatusHistory).where(
            BloodRequestStatusHistory.request_id == response.id
        )
    )
    assert response.status == "PENDING_VERIFICATION"
    assert history is not None
    assert history.status == "PENDING_VERIFICATION"


def test_stage_one_alerts_only_verified_compatible_fresh_available_consented_donors(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "coordinator")
    request = _request(db_session, coordinator)
    _, eligible = _donor(db_session, "O+")
    _donor(db_session, "A+")
    _donor(db_session, "O+", consent=False)
    _donor(db_session, "O+", available=False)
    _donor(db_session, "O+", verified=False)
    _donor(db_session, "O+", age_days=31)

    sent = start_outreach(db_session, request, coordinator)
    notifications = db_session.scalars(select(BloodNotification)).all()

    assert sent == 1
    assert len(notifications) == 1
    assert notifications[0].donor_id == eligible.id
    assert notifications[0].status == "SENT"


def test_all_compatible_groups_are_notified_and_incompatible_groups_are_excluded(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "bank-compatible")
    request = _request(db_session, coordinator)
    request.blood_group = "A+"
    compatible_profiles = [
        _donor(db_session, group)[1] for group in ("O-", "O+", "A-", "A+")
    ]
    _donor(db_session, "B+")

    sent = start_outreach(db_session, request, coordinator)
    notified_ids = set(db_session.scalars(select(BloodNotification.donor_id)).all())

    assert sent == 4
    assert notified_ids == {profile.id for profile in compatible_profiles}


def test_donor_does_not_receive_duplicate_notification_in_later_stage(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "bank-no-duplicate")
    _, donor = _donor(db_session, "O+")
    request = _request(db_session, coordinator)
    start_outreach(db_session, request, coordinator)
    first_batch = db_session.scalar(select(BloodOutreachBatch))
    first_batch.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    donor.approx_latitude = 13.0767

    sent = advance_outreach(db_session, request, coordinator)

    assert request.current_stage == 1
    assert sent == 0
    assert db_session.scalar(
        select(func.count()).select_from(BloodNotification).where(
            BloodNotification.request_id == request.id,
            BloodNotification.donor_id == donor.id,
        )
    ) == 1


def test_request_cancellation_stops_matching_and_invalidates_pending_alerts(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "bank-request-cancel")
    donor_user, donor = _donor(db_session, "O+")
    request = _request(db_session, coordinator)
    start_outreach(db_session, request, coordinator)
    notification = db_session.scalar(
        select(BloodNotification).where(BloodNotification.donor_id == donor.id)
    )

    stop_outreach(db_session, request, coordinator, "CANCELLED", "Request withdrawn")

    assert request.outreach_active is False
    assert notification.status == "CANCELLED"
    with pytest.raises(HTTPException) as error:
        record_response(db_session, notification, donor_user, "ACCEPTED")
    assert error.value.status_code == 409


def test_non_rbc_component_cannot_start_automated_outreach(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "bank-plasma")
    request = _request(db_session, coordinator)
    request.component = "PLASMA"

    with pytest.raises(HTTPException) as error:
        start_outreach(db_session, request, coordinator)

    assert error.value.status_code == 409
    assert "component-specific" in error.value.detail.lower()


def test_verified_blood_bank_can_verify_matching_donor_group(db_session) -> None:
    bank_user = _user(db_session, RoleName.BLOOD_BANK, "verifying-bank")
    _, donor = _donor(db_session, "O+", verified=False)
    organisation = BloodOrganisation(
        name="Verified Blood Bank",
        code="TEST-BANK",
        locality="Adyar",
        city="Chennai",
        verification_status="VERIFIED",
        is_active=True,
    )
    db_session.add(organisation)
    db_session.flush()
    donor.blood_group_verification_organisation_id = organisation.id
    db_session.add(
        BloodBankStaff(
            user_id=bank_user.id,
            organisation_id=organisation.id,
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(HTTPException) as error:
        record_donor_screening_completion(
            donor.id,
            DonorScreeningReviewRequest(screening_completed=True),
            db_session,
            bank_user,
        )
    assert error.value.status_code == 409

    response = verify_donor_blood_group(
        donor.id,
        BloodGroupVerificationRequest(confirmed_blood_group="O+"),
        db_session,
        bank_user,
    )

    assert response.blood_group_verified is True
    assert donor.blood_group_verified_by_user_id == bank_user.id

    screening_response = record_donor_screening_completion(
        donor.id,
        DonorScreeningReviewRequest(screening_completed=True),
        db_session,
        bank_user,
    )
    assert screening_response.screening_completed is True


def test_bank_request_matches_only_donors_reviewed_by_that_bank(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "bank-scoped-request")
    bank = BloodOrganisation(
        name="Requesting Blood Bank",
        code="REQUEST-BANK",
        locality="Adyar",
        city="Chennai",
        verification_status="VERIFIED",
        is_active=True,
    )
    other_bank = BloodOrganisation(
        name="Other Blood Bank",
        code="OTHER-BANK",
        locality="Guindy",
        city="Chennai",
        verification_status="VERIFIED",
        is_active=True,
    )
    db_session.add_all((bank, other_bank))
    db_session.flush()
    donor_user, donor = _donor(db_session, "O+")
    _, other_donor = _donor(db_session, "O+")
    donor.blood_group_verification_organisation_id = bank.id
    other_donor.blood_group_verification_organisation_id = other_bank.id
    request = _request(db_session, coordinator)
    request.organisation_id = bank.id

    assert start_outreach(db_session, request, coordinator) == 1
    notification = db_session.scalar(select(BloodNotification))
    assert notification is not None
    assert notification.donor_id == donor.id

    donor.blood_group_verification_organisation_id = other_bank.id
    with pytest.raises(HTTPException) as error:
        record_response(db_session, notification, donor_user, "ACCEPTED")
    assert error.value.status_code == 409
    assert "no longer meets" in error.value.detail.lower()


def test_admin_compatibility_analytics_uses_persisted_matches_and_responses(db_session) -> None:
    bank_user = _user(db_session, RoleName.BLOOD_BANK, "analytics-bank")
    admin_user = _user(db_session, RoleName.ADMIN, "analytics-admin")
    donor_user, donor = _donor(db_session, "O+")
    request = _request(db_session, bank_user)
    start_outreach(db_session, request, bank_user)
    notification = db_session.scalar(
        select(BloodNotification).where(BloodNotification.donor_id == donor.id)
    )
    record_response(db_session, notification, donor_user, "ACCEPTED")

    analytics = blood_compatibility_analytics(db_session, admin_user)
    notification_group = next(
        item
        for item in analytics.notifications_by_donor_group
        if item.donor_blood_group == "O+"
    )

    assert analytics.potential_donors_identified == 1
    assert notification_group.notifications_sent == 1
    assert notification_group.accepted == 1
    assert notification_group.acceptance_rate == 1.0
    assert analytics.unfulfilled_requests == 1
    assert analytics.average_response_seconds is not None


def test_decline_does_not_stop_or_advance_outreach(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "coordinator")
    donor_user, donor_profile = _donor(db_session, "O+")
    request = _request(db_session, coordinator)
    start_outreach(db_session, request, coordinator)
    notification = db_session.scalar(select(BloodNotification))

    record_response(db_session, notification, donor_user, "DECLINED")

    assert request.outreach_active is True
    assert request.current_stage == 0
    assert request.status == "OUTREACH_ACTIVE"


def test_reaching_required_acceptances_cancels_other_alerts(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "coordinator")
    donor_user, donor_profile = _donor(db_session, "O+")
    pending_user, _ = _donor(db_session, "O+")
    request = _request(db_session, coordinator, required_donors=1)
    start_outreach(db_session, request, coordinator)
    notifications = db_session.scalars(select(BloodNotification)).all()
    accepted_notification = next(item for item in notifications if item.donor_id == donor_profile.id)
    pending_notification = next(item for item in notifications if item.donor_id != donor_profile.id)

    record_response(db_session, accepted_notification, donor_user, "ACCEPTED")

    db_session.refresh(request)
    db_session.refresh(pending_notification)
    assert request.outreach_active is False
    assert request.status == "COORDINATION"
    assert pending_notification.status == "CANCELLED"
    assert pending_notification.cancelled_at is not None
    with pytest.raises(HTTPException) as error:
        record_response(db_session, pending_notification, pending_user, "ACCEPTED")
    assert error.value.status_code == 409


def test_multiple_requested_donors_reserve_distinct_units(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "blood-bank")
    first_user, first_profile = _donor(db_session, "O+")
    second_user, second_profile = _donor(db_session, "O+")
    request = _request(db_session, coordinator, required_donors=2)
    start_outreach(db_session, request, coordinator)
    notifications = db_session.scalars(
        select(BloodNotification).where(BloodNotification.request_id == request.id)
    ).all()
    notification_by_donor = {notification.donor_id: notification for notification in notifications}

    record_response(
        db_session,
        notification_by_donor[first_profile.id],
        first_user,
        "ACCEPTED",
        contact_shared=True,
    )
    assert request.outreach_active is True
    record_response(db_session, notification_by_donor[second_profile.id], second_user, "ACCEPTED")

    reservations = db_session.scalars(
        select(BloodRequestReservation).where(
            BloodRequestReservation.request_id == request.id,
            BloodRequestReservation.status == "ACTIVE",
        )
    ).all()
    assert {reservation.unit_number for reservation in reservations} == {1, 2}
    assert next(item for item in reservations if item.donor_id == first_profile.id).contact_shared is True
    assert request.outreach_active is False
    assert request.status == "COORDINATION"


def test_cancellation_within_grace_reopens_outreach(db_session) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "blood-bank")
    donor_user, donor_profile = _donor(db_session, "O+")
    _donor(db_session, "O+")
    request = _request(db_session, coordinator, required_donors=1)
    start_outreach(db_session, request, coordinator)
    notification = db_session.scalar(
        select(BloodNotification).where(BloodNotification.donor_id == donor_profile.id)
    )
    record_response(db_session, notification, donor_user, "ACCEPTED")
    reservation = db_session.scalar(
        select(BloodRequestReservation).where(
            BloodRequestReservation.request_id == request.id,
            BloodRequestReservation.status == "ACTIVE",
        )
    )

    cancel_reservation(db_session, reservation.id, donor_user, "Unable to attend")

    db_session.refresh(request)
    db_session.refresh(reservation)
    assert reservation.status == "CANCELLED"
    assert request.status == "OUTREACH_ACTIVE"
    assert request.outreach_active is True
    assert request.current_stage == 0


def test_outreach_uses_two_minute_progressive_stages_and_broadens_after_eight_minutes(
    db_session,
) -> None:
    coordinator = _user(db_session, RoleName.BLOOD_BANK, "blood-bank")
    request = _request(db_session, coordinator)
    assert RADIUS_STAGES == (
        (0, 5, 120),
        (5, 10, 120),
        (10, 15, 120),
        (15, 20, 120),
        (20, 20016, 120),
    )

    start_outreach(db_session, request, coordinator)
    for next_stage in range(1, 5):
        current_batch = db_session.scalar(
            select(BloodOutreachBatch).where(
                BloodOutreachBatch.request_id == request.id,
                BloodOutreachBatch.stage == request.current_stage,
                BloodOutreachBatch.status == "ACTIVE",
            )
        )
        current_batch.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        advance_outreach(db_session, request, actor=None)
        assert request.current_stage == next_stage

    final_batch = db_session.scalar(
        select(BloodOutreachBatch).where(
            BloodOutreachBatch.request_id == request.id,
            BloodOutreachBatch.stage == 4,
            BloodOutreachBatch.status == "ACTIVE",
        )
    )
    final_batch.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    advance_outreach(db_session, request, actor=None)
    assert request.status == "OUTREACH_EXHAUSTED"
    assert request.outreach_active is False


def test_database_worker_advances_expired_outreach_without_browser_activity(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory.begin() as db:
        coordinator = _user(db, RoleName.BLOOD_BANK, "worker-bank")
        request = _request(db, coordinator)
        start_outreach(db, request, coordinator)
        batch = db.scalar(
            select(BloodOutreachBatch).where(
                BloodOutreachBatch.request_id == request.id,
                BloodOutreachBatch.stage == 0,
            )
        )
        batch.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        request_id = request.id

    assert advance_due_outreach(factory) == 1
    with factory() as db:
        request = db.get(BloodRequest, request_id)
        assert request.current_stage == 1
        assert request.outreach_active is True
    engine.dispose()


def test_completion_requires_institution_confirmation(db_session) -> None:
    bank_user = _user(db_session, RoleName.BLOOD_BANK, "completion-bank")
    donor_user, donor_profile = _donor(db_session, "O+")
    admin_user = _user(db_session, RoleName.ADMIN, "completion-admin")
    request = _request(db_session, bank_user, required_donors=1)
    start_outreach(db_session, request, bank_user)
    notification = db_session.scalar(
        select(BloodNotification).where(
            BloodNotification.request_id == request.id,
            BloodNotification.donor_id == donor_profile.id,
        )
    )
    record_response(db_session, notification, donor_user, "ACCEPTED")
    reservation = db_session.scalar(
        select(BloodRequestReservation).where(
            BloodRequestReservation.request_id == request.id,
            BloodRequestReservation.donor_id == donor_profile.id,
        )
    )

    record = report_completion(
        db_session,
        request.id,
        reservation.id,
        donor_user,
        component="PACKED_RED_CELLS",
        quantity_ml=350,
    )
    assert record.status == "PENDING_VERIFICATION"
    assert request.status == "COMPLETED_PENDING_VERIFICATION"
    assert request.fulfilled_at is None

    verified = verify_completion(
        db_session,
        request.id,
        record.id,
        admin_user,
        decision="VERIFY",
        notes=None,
    )
    assert verified.status == "VERIFIED"
    assert request.status == "FULFILLED"
    assert request.fulfilled_at is not None
    assert reservation.status == "COMPLETED"
    assert db_session.query(BloodDonationRecord).count() == 1