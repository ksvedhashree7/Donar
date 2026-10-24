from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StartTrackingRequest(BaseModel):
    consent: bool = Field(..., description="Explicit donor consent for live location sharing")
    latitude: float | None = Field(None, ge=-90.0, le=90.0, description="Initial donor latitude")
    longitude: float | None = Field(None, ge=-180.0, le=180.0, description="Initial donor longitude")
    accuracy_meters: float | None = Field(None, ge=0.0, description="Initial GPS accuracy in meters")


class LocationUpdateRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Current donor latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Current donor longitude")
    accuracy_meters: float | None = Field(None, ge=0.0, description="GPS accuracy in meters")


class StopTrackingRequest(BaseModel):
    reason: str | None = Field(None, max_length=100, description="Optional cancellation or stop reason")


class TrackingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    request_id: UUID
    public_request_id: str
    status: str  # WAITING_FOR_SHARING, SHARING, PAUSED, ARRIVED, STOPPED, CANCELLED
    donor_code: str
    destination_facility: str
    destination_locality: str
    destination_latitude: float | None
    destination_longitude: float | None
    current_latitude: float | None
    current_longitude: float | None
    current_accuracy_meters: float | None
    last_location_at: datetime | None
    estimated_distance_meters: int | None
    estimated_duration_seconds: int | None
    estimated_arrival_at: datetime | None
    route_distance_text: str | None
    route_duration_text: str | None
    encoded_polyline: str | None
    is_stale: bool = False
    is_fallback_routing: bool = False
    routing_source: str = "standard_road_model"
    contact_shared: bool = False
    donor_phone: str | None = None
    arrived_at: datetime | None = None
    stopped_at: datetime | None = None


class TrackingNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tracking_session_id: UUID
    request_id: UUID
    event_type: str
    title: str
    message: str
    created_at: datetime
    is_read: bool
