import React, { useCallback, useEffect, useRef, useState } from 'react';
import GoogleMapTracker from './GoogleMapTracker';

interface DonationJourneyPanelProps {
  requestId: string;
  bloodGroup: string;
  facility: string;
  locality: string;
  destinationCoords?: { lat: number; lng: number };
  onStatusChange?: (status: string, toastMsg: string) => void;
  onArrived?: () => void;
}

export const DonationJourneyPanel: React.FC<DonationJourneyPanelProps> = ({
  requestId,
  bloodGroup,
  facility,
  locality,
  destinationCoords = { lat: 13.0067, lng: 80.2570 },
  onStatusChange,
  onArrived,
}) => {
  // Journey state
  const [isSharing, setIsSharing] = useState(false);
  const [isArrived, setIsArrived] = useState(false);
  const [isStopped, setIsStopped] = useState(false);
  const [consentGranted, setConsentGranted] = useState(false);
  const [showConsentModal, setShowConsentModal] = useState(false);

  // Permission state: 'prompt' | 'granted' | 'denied' | 'unsupported'
  const [permissionState, setPermissionState] = useState<string>('prompt');
  const [permissionError, setPermissionError] = useState<string | null>(null);

  // Live coordinates (Initial near Besant Nagar / Adyar)
  const [donorCoords, setDonorCoords] = useState<{ lat: number; lng: number }>({
    lat: 13.0002,
    lng: 80.2668,
  });
  const [accuracy, setAccuracy] = useState<number | null>(12);
  const [distanceKm, setDistanceKm] = useState<number>(3.2);
  const [etaMinutes, setEtaMinutes] = useState<number>(11);
  const [simulateMovement, setSimulateMovement] = useState<boolean>(false);
  const [lastUpdateText, setLastUpdateText] = useState<string>('Just now');

  const watchIdRef = useRef<number | null>(null);
  const simIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Check initial browser permission status if supported
  useEffect(() => {
    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions
        .query({ name: 'geolocation' as PermissionName })
        .then((result) => {
          setPermissionState(result.state);
          result.onchange = () => setPermissionState(result.state);
        })
        .catch(() => setPermissionState('prompt'));
    }
  }, []);

  // Real browser geolocation watcher when live sharing is active
  useEffect(() => {
    if (!isSharing || simulateMovement || isArrived || isStopped) {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      return;
    }

    if (!('geolocation' in navigator)) {
      setPermissionState('unsupported');
      setPermissionError('Geolocation is not supported by this browser.');
      return;
    }

    watchIdRef.current = navigator.geolocation.watchPosition(
      (position) => {
        const { latitude, longitude, accuracy: acc } = position.coords;
        setDonorCoords({ lat: latitude, lng: longitude });
        setAccuracy(acc);
        setPermissionState('granted');
        setPermissionError(null);
        setLastUpdateText('Live (GPS)');

        // Recalculate distance and ETA
        const dist = Math.sqrt(
          Math.pow((latitude - destinationCoords.lat) * 111, 2) +
          Math.pow((longitude - destinationCoords.lng) * 111 * Math.cos(latitude * (Math.PI / 180)), 2)
        );
        const roadDist = Math.max(0.1, Number((dist * 1.35).toFixed(1)));
        setDistanceKm(roadDist);
        setEtaMinutes(Math.max(1, Math.round((roadDist / 28) * 60)));
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setPermissionState('denied');
          setPermissionError('Location permission was denied. You can re-enable location in your browser settings.');
          setIsSharing(false);
        } else {
          setPermissionError('Unable to retrieve location. Retrying…');
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 10000,
      }
    );

    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [isSharing, simulateMovement, isArrived, isStopped, destinationCoords]);

  const handleMarkArrived = useCallback(() => {
    setIsSharing(false);
    setIsArrived(true);
    setDistanceKm(0);
    setEtaMinutes(0);
    onArrived?.();
    onStatusChange?.('Donor arrived', 'You have marked your arrival at the hospital. Coordination staff alerted.');
  }, [onArrived, onStatusChange]);

  // Movement simulator (for interactive testing without physical travel)
  useEffect(() => {
    if (!isSharing || !simulateMovement || isArrived || isStopped) {
      if (simIntervalRef.current) clearInterval(simIntervalRef.current);
      return;
    }

    simIntervalRef.current = setInterval(() => {
      setDonorCoords((prev) => {
        const deltaLat = (destinationCoords.lat - prev.lat) * 0.12;
        const deltaLng = (destinationCoords.lng - prev.lng) * 0.12;

        const nextLat = prev.lat + deltaLat;
        const nextLng = prev.lng + deltaLng;

        const distLeft = Math.sqrt(
          Math.pow((destinationCoords.lat - nextLat) * 111, 2) +
          Math.pow((destinationCoords.lng - nextLng) * 111 * Math.cos(nextLat * (Math.PI / 180)), 2)
        );
        const roadDist = Math.max(0.1, Number((distLeft * 1.35).toFixed(1)));
        setDistanceKm(roadDist);
        setEtaMinutes(Math.max(1, Math.round((roadDist / 28) * 60)));
        setLastUpdateText('Live · Simulated update');

        if (roadDist < 0.2) {
          handleMarkArrived();
        }

        return { lat: nextLat, lng: nextLng };
      });
    }, 3000);

    return () => {
      if (simIntervalRef.current) clearInterval(simIntervalRef.current);
    };
  }, [isSharing, simulateMovement, isArrived, isStopped, destinationCoords, handleMarkArrived]);

  const handleStartSharing = () => {
    setShowConsentModal(true);
  };

  const confirmConsentAndStart = () => {
    setConsentGranted(true);
    setShowConsentModal(false);
    setIsSharing(true);
    setIsStopped(false);
    setIsArrived(false);
    setPermissionError(null);
    onStatusChange?.('Live location sharing active', 'Live location sharing started. ABC Hospital can view your journey.');
  };

  const handleStopSharing = () => {
    setIsSharing(false);
    setIsStopped(true);
    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    onStatusChange?.('Live tracking paused', 'Location sharing paused. Your coordinates are no longer visible.');
  };

  const openGoogleMapsNavigation = () => {
    const query = encodeURIComponent(`${facility}, ${locality}`);
    window.open(`https://www.google.com/maps/dir/?api=1&destination=${query}`, '_blank', 'noopener,noreferrer');
  };

  return (
    <section className="uth-panel uth-journey-panel">
      <div className="uth-panel-head">
        <div>
          <span className="uth-section-label">ACTIVE DONATION JOURNEY</span>
          <h2>Blood Request {requestId} · {bloodGroup}</h2>
          <p>Destination: <strong>{facility}</strong> ({locality})</p>
        </div>
        <div className="uth-journey-badge-group">
          {consentGranted && (
            <span className="uth-badge uth-badge-outline" title="Explicit user privacy consent granted for this journey">
              ✓ Consent Verified
            </span>
          )}
          <span className={`uth-status ${isArrived ? 'uth-status-green' : isSharing ? 'uth-status-red' : 'uth-status-neutral'}`}>
            <i /> {isArrived ? 'Arrived at Hospital' : isSharing ? 'Sharing Live Location' : isStopped ? 'Sharing Stopped' : 'Ready to Share'}
          </span>
        </div>
      </div>

      {permissionState === 'denied' && (
        <div className="uth-permission-banner uth-permission-warning">
          <strong>Location Blocked:</strong> Geolocation permission is blocked in your browser settings. Please allow location permissions to share your journey.
        </div>
      )}

      {permissionError && permissionState !== 'denied' && (
        <div className="uth-permission-banner uth-permission-warning">
          <strong>Location Notice:</strong> {permissionError}
        </div>
      )}

      {/* Map View */}
      <GoogleMapTracker
        donorCoords={isSharing || isArrived ? donorCoords : null}
        destinationCoords={destinationCoords}
        destinationName={facility}
        destinationLocality={locality}
        isSharing={isSharing}
        status={isArrived ? 'Arrived' : isSharing ? 'Live on Route' : 'Ready'}
        distanceText={isArrived ? '0 m' : `${distanceKm} km`}
        durationText={isArrived ? 'Arrived' : `~${etaMinutes} mins`}
        accuracyMeters={isSharing ? accuracy : null}
        lastUpdatedText={lastUpdateText}
      />

      {/* Action Bar */}
      <div className="uth-journey-actions">
        <button
          type="button"
          className="uth-button uth-button-secondary uth-nav-btn"
          onClick={openGoogleMapsNavigation}
          title="Open directions in official Google Maps app"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="3 11 22 2 13 21 11 13 3 11" />
          </svg>
          Open Navigation in Google Maps
        </button>

        {!isSharing && !isArrived && (
          <button
            type="button"
            className="uth-button uth-button-primary uth-live-btn"
            onClick={handleStartSharing}
          >
            <span className="uth-live-dot is-pulsing" />
            Start Live Location Sharing
          </button>
        )}

        {isSharing && (
          <button
            type="button"
            className="uth-button uth-button-danger-quiet"
            onClick={handleStopSharing}
          >
            Stop Sharing Location
          </button>
        )}

        {!isArrived && (
          <button
            type="button"
            className="uth-button uth-button-green"
            onClick={handleMarkArrived}
          >
            Mark as Arrived
          </button>
        )}
      </div>

      {/* Simulation and Privacy Footnote */}
      <div className="uth-journey-footer">
        <label className="uth-sim-toggle">
          <input
            type="checkbox"
            checked={simulateMovement}
            onChange={(e) => setSimulateMovement(e.target.checked)}
          />
          <span>Simulate journey movement (Demo testing)</span>
        </label>
        <span className="uth-privacy-footnote">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" />
          </svg>
          Location is shared strictly for this active journey. Your exact home address is never collected or stored.
        </span>
      </div>

      {/* Consent Dialog Modal */}
      {showConsentModal && (
        <div className="uth-modal-backdrop" role="presentation">
          <div className="uth-modal" role="dialog" aria-modal="true" aria-labelledby="consent-title">
            <div className="uth-modal-head">
              <span className="uth-modal-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" />
                </svg>
              </span>
              <button
                type="button"
                className="uth-icon-button"
                aria-label="Close"
                onClick={() => setShowConsentModal(false)}
              >
                ✕
              </button>
            </div>
            <span className="uth-section-label">EXPLICIT PRIVACY CONSENT</span>
            <h2 id="consent-title">Share Live Location with {facility}?</h2>
            <p>
              By starting live tracking, your approximate route and estimated arrival time will be shown to authorised
              hospital coordinators for <strong>Request {requestId}</strong> so they can prepare for your arrival.
            </p>
            <ul className="uth-consent-bullet-list">
              <li>Tracking stops immediately when you click "Stop Sharing" or "Mark as Arrived".</li>
              <li>Your phone number and personal home address remain completely confidential.</li>
              <li>No background tracking is performed once your session concludes.</li>
            </ul>
            <div className="uth-confirm-actions">
              <button
                type="button"
                className="uth-button uth-button-secondary"
                onClick={() => setShowConsentModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="uth-button uth-button-primary"
                onClick={confirmConsentAndStart}
              >
                I Consent & Start Sharing
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default DonationJourneyPanel;
