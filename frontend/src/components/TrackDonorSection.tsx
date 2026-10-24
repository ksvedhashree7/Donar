import React, { useEffect, useState } from 'react';
import GoogleMapTracker from './GoogleMapTracker';

interface TrackDonorSectionProps {
  requestId: string;
  facility: string;
  locality: string;
  donorInitial?: string;
  donorCode?: string;
  donorBloodGroup?: string;
  isDonorSharing?: boolean;
  donorArrived?: boolean;
  donorCoords?: { lat: number; lng: number } | null;
  destinationCoords?: { lat: number; lng: number };
  contactShared?: boolean;
  donorPhone?: string | null;
  onRefresh?: () => void;
}

export const TrackDonorSection: React.FC<TrackDonorSectionProps> = ({
  requestId,
  facility,
  locality,
  donorCode = 'DNR-1024',
  donorBloodGroup = 'O+',
  isDonorSharing = false,
  donorArrived = false,
  donorCoords = null,
  destinationCoords = { lat: 13.0067, lng: 80.2570 },
  contactShared = false,
  donorPhone = null,
  onRefresh,
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshTime, setLastRefreshTime] = useState<string>('Just now');
  const [showContactModal, setShowContactModal] = useState(false);

  // Compute status label
  const getStatusLabel = () => {
    if (donorArrived) return 'Donor arrived at hospital';
    if (isDonorSharing) return 'Live location active';
    return 'Waiting for donor to start sharing';
  };

  const getStatusTone = () => {
    if (donorArrived) return 'green';
    if (isDonorSharing) return 'red';
    return 'orange';
  };

  // Compute realistic distance & ETA based on donor position
  const computeDistanceAndEta = () => {
    if (donorArrived) {
      return { distText: '0 m', etaText: 'Arrived' };
    }
    if (!isDonorSharing || !donorCoords) {
      return { distText: '~3.2 km approx', etaText: 'Waiting for start' };
    }
    const dist = Math.sqrt(
      Math.pow((donorCoords.lat - destinationCoords.lat) * 111, 2) +
      Math.pow((donorCoords.lng - destinationCoords.lng) * 111 * Math.cos(donorCoords.lat * (Math.PI / 180)), 2)
    );
    const roadDist = Math.max(0.1, Number((dist * 1.35).toFixed(1)));
    const mins = Math.max(1, Math.round((roadDist / 28) * 60));

    // Expected arrival time formatted in local time
    const expectedTime = new Date(Date.now() + mins * 60000);
    const timeFormatted = expectedTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    return {
      distText: `${roadDist} km remaining`,
      etaText: `Expected by ${timeFormatted} (~${mins} mins)`,
    };
  };

  const { distText, etaText } = computeDistanceAndEta();

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    setLastRefreshTime('Updating…');
    onRefresh?.();
    setTimeout(() => {
      setIsRefreshing(false);
      setLastRefreshTime('Just now');
    }, 600);
  };

  // Automatic periodic refresh
  useEffect(() => {
    const timer = setInterval(() => {
      setLastRefreshTime('Updated a moment ago');
    }, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <section className="uth-panel uth-track-donor-panel">
      <div className="uth-panel-head">
        <div>
          <span className="uth-section-label">REQUEST COORDINATION · LIVE TRACKING</span>
          <h2>Track En Route Donor</h2>
          <p>
            Request <strong>{requestId}</strong> · Donor <strong>{donorCode}</strong> ({donorBloodGroup})
          </p>
        </div>
        <div className="uth-track-head-actions">
          <span className={`uth-status uth-status-${getStatusTone()}`}>
            <i /> {getStatusLabel()}
          </span>
          <button
            type="button"
            className={`uth-icon-button uth-refresh-btn ${isRefreshing ? 'is-spinning' : ''}`}
            onClick={handleManualRefresh}
            title="Refresh tracking data"
            aria-label="Refresh tracking data"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
            </svg>
          </button>
        </div>
      </div>

      {/* Interactive Map */}
      <GoogleMapTracker
        donorCoords={isDonorSharing || donorArrived ? donorCoords : null}
        destinationCoords={destinationCoords}
        destinationName={facility}
        destinationLocality={locality}
        isSharing={isDonorSharing}
        status={getStatusLabel()}
        distanceText={distText}
        durationText={etaText}
        accuracyMeters={isDonorSharing ? 10 : null}
        lastUpdatedText={lastRefreshTime}
      />

      {/* Info & Action Strip */}
      <div className="uth-track-details-strip">
        <div className="uth-track-detail">
          <span className="uth-detail-label">DESTINATION FACILITY</span>
          <strong>{facility}</strong>
          <small>{locality}</small>
        </div>

        <div className="uth-track-detail">
          <span className="uth-detail-label">ESTIMATED ARRIVAL (ETA)</span>
          <strong className="uth-highlight-text">{etaText}</strong>
          <small>Subject to local road traffic</small>
        </div>

        <div className="uth-track-detail">
          <span className="uth-detail-label">DONOR CONTACT</span>
          {contactShared ? (
            <button
              type="button"
              className="uth-button uth-button-secondary uth-contact-btn"
              onClick={() => setShowContactModal(true)}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
              View Shared Phone
            </button>
          ) : (
            <span className="uth-contact-private">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              Private (In-app only)
            </span>
          )}
        </div>
      </div>

      {/* Privacy Guarantee Note */}
      <div className="uth-track-privacy-note">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" />
        </svg>
        <span>
          <strong>Privacy by design:</strong> Donor's residential address and personal location history are never
          revealed. Live GPS coordinates are strictly visible during active transit to {facility}.
        </span>
      </div>

      {/* Contact Modal */}
      {showContactModal && (
        <div className="uth-modal-backdrop" role="presentation">
          <div className="uth-modal" role="dialog" aria-modal="true" aria-labelledby="contact-modal-title">
            <div className="uth-modal-head">
              <span className="uth-modal-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
              </span>
              <button
                type="button"
                className="uth-icon-button"
                aria-label="Close"
                onClick={() => setShowContactModal(false)}
              >
                ✕
              </button>
            </div>
            <span className="uth-section-label">AUTHORISED CONTACT</span>
            <h2 id="contact-modal-title">Donor Contact Details</h2>
            <p>
              The donor explicitly consented to share their verified contact number for Request <strong>{requestId}</strong>.
            </p>
            <div className="uth-phone-display">
              <strong>{donorPhone || '+91 98765 43210 (Demo)'}</strong>
              <small>Verified Donor Phone</small>
            </div>
            <p className="uth-contact-disclaimer">
              This contact information is confidential. Only use it for coordinating collection or arrival for this
              active blood request.
            </p>
            <div className="uth-confirm-actions">
              <button
                type="button"
                className="uth-button uth-button-primary"
                onClick={() => setShowContactModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default TrackDonorSection;
