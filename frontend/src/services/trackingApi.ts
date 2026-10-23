export interface TrackingSession {
  session_id: string;
  request_id: string;
  public_request_id: string;
  status: 'WAITING_FOR_SHARING' | 'SHARING' | 'PAUSED' | 'ARRIVED' | 'STOPPED' | 'CANCELLED';
  donor_code: string;
  destination_facility: string;
  destination_locality: string;
  destination_latitude: number | null;
  destination_longitude: number | null;
  current_latitude: number | null;
  current_longitude: number | null;
  current_accuracy_meters: number | null;
  last_location_at: string | null;
  estimated_distance_meters: number | null;
  estimated_duration_seconds: number | null;
  estimated_arrival_at: string | null;
  route_distance_text: string | null;
  route_duration_text: string | null;
  encoded_polyline: string | null;
  is_stale: boolean;
  is_fallback_routing: boolean;
  routing_source: string;
  contact_shared: boolean;
  donor_phone: string | null;
  arrived_at: string | null;
  stopped_at: string | null;
}

export interface TrackingNotification {
  id: string;
  tracking_session_id: string;
  request_id: string;
  event_type: string;
  title: string;
  message: string;
  created_at: string;
  is_read: boolean;
}

const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl.replace(/\/$/, '');
  return `http://${window.location.hostname}:8000`;
};

export async function fetchTrackingSession(requestId: string): Promise<TrackingSession | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/requests/${requestId}/tracking`, {
      headers: {
        'Accept': 'application/json',
      },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

export async function startTracking(
  requestId: string,
  payload: { consent: boolean; latitude?: number; longitude?: number; accuracy_meters?: number }
): Promise<TrackingSession | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/requests/${requestId}/tracking/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

export async function sendLocationUpdate(
  requestId: string,
  payload: { latitude: number; longitude: number; accuracy_meters?: number }
): Promise<TrackingSession | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/requests/${requestId}/tracking/location`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

export async function stopTracking(requestId: string, reason?: string): Promise<TrackingSession | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/requests/${requestId}/tracking/stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ reason }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

export async function markArrived(requestId: string): Promise<TrackingSession | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/requests/${requestId}/tracking/arrive`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}
