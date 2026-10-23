from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Cache entry: key -> (timestamp, RouteResult)
_ROUTE_CACHE: dict[str, tuple[float, RouteResult]] = {}
CACHE_TTL_SECONDS = 30.0  # Avoid repeated external calls for close coordinates


@dataclass
class RouteResult:
    distance_meters: int
    duration_seconds: int
    distance_text: str
    duration_text: str
    encoded_polyline: str | None
    is_fallback: bool
    source: str  # "google_routes_api" or "standard_road_model"


def _format_distance(meters: int) -> str:
    if meters < 1000:
        return f"{meters} m"
    km = meters / 1000.0
    return f"{km:.1f} km"


def _format_duration(seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f"{minutes} min" if minutes == 1 else f"{minutes} mins"
    hours = minutes // 60
    rem_mins = minutes % 60
    if rem_mins == 0:
        return f"{hours} hr" if hours == 1 else f"{hours} hrs"
    return f"{hours} hr {rem_mins} mins"


def _haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    earth_radius_m = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return earth_radius_m * c


def _encode_polyline_point(val: int) -> str:
    val = ~(val << 1) if val < 0 else (val << 1)
    chunks = []
    while val >= 0x20:
        chunks.append(chr((0x20 | (val & 0x1F)) + 63))
        val >>= 5
    chunks.append(chr(val + 63))
    return "".join(chunks)


def _simple_polyline(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Encode a simple 2-point polyline from origin to destination."""
    p1 = _encode_polyline_point(round(lat1 * 1e5)) + _encode_polyline_point(
        round(lon1 * 1e5)
    )
    dlat = round((lat2 - lat1) * 1e5)
    dlon = round((lon2 - lon1) * 1e5)
    p2 = _encode_polyline_point(dlat) + _encode_polyline_point(dlon)
    return p1 + p2


def fallback_road_route(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> RouteResult:
    """Calculates realistic road distance and driving duration using urban road factors."""
    straight_line_meters = _haversine_distance_meters(
        origin_lat, origin_lon, dest_lat, dest_lon
    )
    # Urban road detour factor is typically 1.30 to 1.40x straight line
    road_meters = int(straight_line_meters * 1.35)

    # Average city driving speed: 28 km/h (~7.78 m/s) with traffic
    speed_mps = 7.78
    duration_secs = int(max(60, road_meters / speed_mps))

    return RouteResult(
        distance_meters=road_meters,
        duration_seconds=duration_secs,
        distance_text=_format_distance(road_meters),
        duration_text=_format_duration(duration_secs),
        encoded_polyline=_simple_polyline(origin_lat, origin_lon, dest_lat, dest_lon),
        is_fallback=True,
        source="standard_road_model",
    )


def calculate_route(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> RouteResult:
    """Calculates road distance and ETA from donor coordinates to hospital destination.

    First attempts Google Maps Routes / Directions API if GOOGLE_MAPS_API_KEY is configured.
    Falls back gracefully to standard road model if API key is absent, rate-limited, or network fails.
    """
    # Cache key rounded to ~50m
    cache_key = f"{round(origin_lat, 3)},{round(origin_lon, 3)}->{round(dest_lat, 3)},{round(dest_lon, 3)}"
    now = time.time()
    if cache_key in _ROUTE_CACHE:
        cached_time, cached_result = _ROUTE_CACHE[cache_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_result

    settings = get_settings()
    api_key = settings.google_maps_api_key

    if not api_key:
        result = fallback_road_route(origin_lat, origin_lon, dest_lat, dest_lon)
        _ROUTE_CACHE[cache_key] = (now, result)
        return result

    # Try Google Maps Routes API
    try:
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
        }
        payload = {
            "origin": {
                "location": {
                    "latLng": {"latitude": origin_lat, "longitude": origin_lon}
                }
            },
            "destination": {
                "location": {
                    "latLng": {"latitude": dest_lat, "longitude": dest_lon}
                }
            },
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
        }

        with httpx.Client(timeout=4.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                routes = data.get("routes", [])
                if routes:
                    primary_route = routes[0]
                    distance_meters = int(primary_route.get("distanceMeters", 0))
                    # duration string format: "123s"
                    duration_str = primary_route.get("duration", "0s")
                    duration_seconds = int(duration_str.rstrip("s"))
                    polyline = primary_route.get("polyline", {}).get(
                        "encodedPolyline"
                    )

                    result = RouteResult(
                        distance_meters=distance_meters,
                        duration_seconds=duration_seconds,
                        distance_text=_format_distance(distance_meters),
                        duration_text=_format_duration(duration_seconds),
                        encoded_polyline=polyline,
                        is_fallback=False,
                        source="google_routes_api",
                    )
                    _ROUTE_CACHE[cache_key] = (now, result)
                    return result
    except Exception as exc:
        logger.warning(
            "Google Maps Routes API error: %s. Falling back to road calculation model.",
            exc,
        )

    # Fallback to standard road model if API call did not succeed
    result = fallback_road_route(origin_lat, origin_lon, dest_lat, dest_lon)
    _ROUTE_CACHE[cache_key] = (now, result)
    return result
