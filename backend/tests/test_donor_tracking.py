from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    BloodDonorProfile,
    BloodDonorTrackingSession,
    BloodNotification,
    BloodOrganisation,
    BloodOutreachBatch,
    BloodRequest,
    BloodRequestReservation,
    BloodTrackingNotification,
    Role,
    RoleName,
    User,
    UserStatus,
)
from app.routers import blood_tracking as tracking_router
from app.schemas.blood_tracking import (
    LocationUpdateRequest,
    StartTrackingRequest,
    StopTrackingRequest,
)
from app.services import blood_outreach, blood_tracking, google_maps


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
        password_hash="not-used",
        status=UserStatus.ACTIVE,
        is_active=True,
        phone_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    return user


def _setup_workflow(db):
    requester = _user(db, RoleName.GENERAL_DONOR, f"req-{uuid4().hex[:6]}")
    donor_user = _user(db, RoleName.GENERAL_DONOR, f"dnr-{uuid4().hex[:6]}")
    other_user = _user(db, RoleName.GENERAL_DONOR, f"oth-{uuid4().hex[:6]}")

    donor_profile = BloodDonorProfile(
        user_id=donor_user.id,
        blood_group="O+",
        blood_group_verified_at=datetime.now(timezone.utc),
        screening_completed_at=datetime.now(timezone.utc),
        locality="Besant Nagar",
        approx_latitude=13.0002,
        approx_longitude=80.2668,
        availability="AVAILABLE",
        notification_consent=True,
        last_confirmed_at=datetime.now(timezone.utc),
    )
    db.add(donor_profile)
    db.flush()

    request = BloodRequest(
        public_id=f"UTH-{uuid4().hex[:6].upper()}",
        requester_user_id=requester.id,
        facility="ABC Hospital",
        locality="Adyar",
        approx_latitude=13.0067,
        approx_longitude=80.2570,
        blood_group="O+",
        component="RED_CELLS",
        required_donors=1,
        required_by=datetime.now(timezone.utc) + timedelta(hours=4),
        urgency="URGENT",
        status="OUTREACH_ACTIVE",
        outreach_active=True,
    )
    db.add(request)
    db.flush()

    batch = BloodOutreachBatch(
        request_id=request.id,
        stage=0,
        radius_min_km=0,
        radius_max_km=5,
        duration_seconds=120,
        started_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        status="ACTIVE",
    )
    db.add(batch)
    db.flush()

    notification = BloodNotification(
        request_id=request.id,
        donor_id=donor_profile.id,
        donor_blood_group="O+",
        batch_id=batch.id,
        status="SENT",
        sent_at=datetime.now(timezone.utc),
    )
    db.add(notification)
    db.flush()

    reservation = blood_outreach.record_response(
        db, notification, donor_user, "ACCEPTED", contact_shared=True
    )
    assert reservation is not None
    db.flush()

    return requester, donor_user, other_user, request, reservation, donor_profile


def test_tracking_session_created_on_reservation(db_session):
    requester, donor_user, _, request, reservation, donor_profile = _setup_workflow(db_session)

    session = blood_tracking.create_or_get_tracking_session(
        db_session, request, reservation, donor_profile
    )
    assert session is not None
    assert session.status == "WAITING_FOR_SHARING"
    assert session.destination_facility == "ABC Hospital"

    # Notification created for requester
    notif = db_session.scalar(
        select(BloodTrackingNotification).where(
            BloodTrackingNotification.tracking_session_id == session.id,
            BloodTrackingNotification.recipient_user_id == requester.id,
        )
    )
    assert notif is not None
    assert notif.event_type == "DONOR_ACCEPTED"


def test_start_tracking_requires_explicit_consent(db_session):
    _, donor_user, _, request, reservation, donor_profile = _setup_workflow(db_session)
    blood_tracking.create_or_get_tracking_session(db_session, request, reservation, donor_profile)

    with pytest.raises(HTTPException) as exc_info:
        blood_tracking.start_location_sharing(
            db_session,
            request.id,
            donor_user,
            StartTrackingRequest(consent=False),
        )
    assert exc_info.value.status_code == 400
    assert "Explicit donor consent is required" in exc_info.value.detail


def test_start_tracking_and_location_updates(db_session):
    requester, donor_user, _, request, reservation, donor_profile = _setup_workflow(db_session)
    blood_tracking.create_or_get_tracking_session(db_session, request, reservation, donor_profile)

    # Donor starts sharing with initial coordinates (Besant Nagar)
    session = blood_tracking.start_location_sharing(
        db_session,
        request.id,
        donor_user,
        StartTrackingRequest(
            consent=True,
            latitude=13.0002,
            longitude=80.2668,
            accuracy_meters=12.5,
        ),
    )
    assert session.status == "SHARING"
    assert session.consent_granted_at is not None
    assert session.current_latitude is not None
    assert session.estimated_distance_meters is not None
    assert session.estimated_duration_seconds is not None
    assert session.route_distance_text is not None

    # Requester receives notification that sharing started
    started_notif = db_session.scalar(
        select(BloodTrackingNotification).where(
            BloodTrackingNotification.tracking_session_id == session.id,
            BloodTrackingNotification.event_type == "LOCATION_SHARING_STARTED",
        )
    )
    assert started_notif is not None

    # Donor updates position closer to hospital
    session = blood_tracking.update_donor_location(
        db_session,
        request.id,
        donor_user,
        LocationUpdateRequest(
            latitude=13.0040,
            longitude=80.2590,
            accuracy_meters=8.0,
        ),
    )
    assert session.current_latitude == 13.0040
    assert session.last_location_at is not None


def test_coordinate_validation():
    # Valid coordinates
    req = LocationUpdateRequest(latitude=13.0067, longitude=80.2570)
    assert req.latitude == 13.0067

    # Latitude out of bounds (> 90)
    with pytest.raises(ValidationError):
        LocationUpdateRequest(latitude=95.0, longitude=80.0)

    # Latitude out of bounds (< -90)
    with pytest.raises(ValidationError):
        LocationUpdateRequest(latitude=-91.0, longitude=80.0)

    # Longitude out of bounds (> 180)
    with pytest.raises(ValidationError):
        LocationUpdateRequest(latitude=13.0, longitude=185.0)


def test_authorized_vs_unauthorized_tracking_access(db_session):
    requester, donor_user, other_user, request, reservation, donor_profile = _setup_workflow(db_session)
    blood_tracking.create_or_get_tracking_session(db_session, request, reservation, donor_profile)

    # Authorized requester access
    req_view = blood_tracking.get_tracking_session_for_user(db_session, request.id, requester)
    assert req_view.public_request_id == request.public_id
    assert req_view.destination_facility == "ABC Hospital"
    # Contact was shared
    assert req_view.contact_shared is True
    assert req_view.donor_phone == "+919876543210"

    # Authorized donor access
    donor_view = blood_tracking.get_tracking_session_for_user(db_session, request.id, donor_user)
    assert donor_view.status == "WAITING_FOR_SHARING"

    # Unauthorized third party rejected
    with pytest.raises(HTTPException) as exc_info:
        blood_tracking.get_tracking_session_for_user(db_session, request.id, other_user)
    assert exc_info.value.status_code == 404


def test_mark_donor_arrived(db_session):
    requester, donor_user, _, request, reservation, donor_profile = _setup_workflow(db_session)
    blood_tracking.create_or_get_tracking_session(db_session, request, reservation, donor_profile)
    blood_tracking.start_location_sharing(
        db_session, request.id, donor_user, StartTrackingRequest(consent=True)
    )

    session = blood_tracking.mark_donor_arrived(db_session, request.id, donor_user)
    assert session.status == "ARRIVED"
    assert session.arrived_at is not None
    assert session.estimated_duration_seconds == 0

    # Notification generated for requester
    arrived_notif = db_session.scalar(
        select(BloodTrackingNotification).where(
            BloodTrackingNotification.tracking_session_id == session.id,
            BloodTrackingNotification.event_type == "DONOR_ARRIVED",
        )
    )
    assert arrived_notif is not None


def test_stop_tracking_clears_live_coordinates_for_privacy(db_session):
    requester, donor_user, _, request, reservation, donor_profile = _setup_workflow(db_session)
    blood_tracking.create_or_get_tracking_session(db_session, request, reservation, donor_profile)
    blood_tracking.start_location_sharing(
        db_session,
        request.id,
        donor_user,
        StartTrackingRequest(consent=True, latitude=13.002, longitude=80.260),
    )

    session = blood_tracking.stop_location_sharing(
        db_session, request.id, donor_user, "Donor paused journey"
    )
    assert session.status == "STOPPED"
    assert session.stopped_at is not None
    assert session.current_latitude is None
    assert session.current_longitude is None


def test_google_maps_fallback_routing():
    # Tests standard road model calculation
    origin_lat, origin_lon = 13.0002, 80.2668
    dest_lat, dest_lon = 13.0067, 80.2570

    route = google_maps.fallback_road_route(origin_lat, origin_lon, dest_lat, dest_lon)
    assert route.distance_meters > 0
    assert route.duration_seconds > 0
    assert route.is_fallback is True
    assert route.encoded_polyline is not None
    assert "km" in route.distance_text or "m" in route.distance_text
    assert "min" in route.duration_text
