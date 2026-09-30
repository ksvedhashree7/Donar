from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    BloodDonorProfile,
    BloodNotification,
    BloodRequest,
    Role,
    RoleName,
    User,
    UserStatus,
)
from app.services.blood_outreach import record_response, start_outreach


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
        password_hash="not-used-by-service-test",
        status=UserStatus.ACTIVE,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _donor(db, blood_group: str, *, consent: bool = True, available: bool = True, age_days: int = 0) -> tuple[User, BloodDonorProfile]:
    user = _user(db, RoleName.DONOR, f"donor-{uuid4().hex}")
    profile = BloodDonorProfile(
        user_id=user.id,
        blood_group=blood_group,
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
        coordinator_user_id=coordinator.id,
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


def test_stage_one_only_alerts_fresh_available_consented_exact_group_donors(db_session) -> None:
    coordinator = _user(db_session, RoleName.COORDINATOR, "coordinator")
    request = _request(db_session, coordinator)
    _, eligible = _donor(db_session, "O+")
    _donor(db_session, "A+")
    _donor(db_session, "O+", consent=False)
    _donor(db_session, "O+", available=False)
    _donor(db_session, "O+", age_days=31)

    sent = start_outreach(db_session, request, coordinator)
    notifications = db_session.scalars(select(BloodNotification)).all()

    assert sent == 1
    assert len(notifications) == 1
    assert notifications[0].donor_id == eligible.id
    assert notifications[0].status == "SENT"


def test_decline_does_not_stop_or_advance_outreach(db_session) -> None:
    coordinator = _user(db_session, RoleName.COORDINATOR, "coordinator")
    donor_user, donor_profile = _donor(db_session, "O+")
    request = _request(db_session, coordinator)
    start_outreach(db_session, request, coordinator)
    notification = db_session.scalar(select(BloodNotification))

    record_response(db_session, notification, donor_user, "DECLINED")

    assert request.outreach_active is True
    assert request.current_stage == 0
    assert request.status == "OUTREACH_ACTIVE"


def test_reaching_required_acceptances_cancels_other_alerts(db_session) -> None:
    coordinator = _user(db_session, RoleName.COORDINATOR, "coordinator")
    donor_user, _ = _donor(db_session, "O+")
    _donor(db_session, "O+")
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