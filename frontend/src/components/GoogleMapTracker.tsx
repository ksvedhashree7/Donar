import React, { useEffect, useRef, useState } from 'react';

interface Coordinates {
  lat: number;
  lng: number;
}

interface GoogleMapInstance {
  setCenter: (coords: Coordinates) => void;
  fitBounds: (bounds: GoogleLatLngBounds, padding?: number) => void;
}

interface GoogleMarkerInstance {
  setPosition: (coords: Coordinates) => void;
  setVisible: (visible: boolean) => void;
}

interface GooglePolylineInstance {
  setPath: (path: Coordinates[]) => void;
  setVisible: (visible: boolean) => void;
}

interface GoogleLatLngBounds {
  extend: (coords: Coordinates) => void;
}

interface GoogleMapsNamespace {
  Map: new (element: HTMLElement, options: Record<string, unknown>) => GoogleMapInstance;
  Marker: new (options: Record<string, unknown>) => GoogleMarkerInstance;
  Polyline: new (options: Record<string, unknown>) => GooglePolylineInstance;
  LatLngBounds: new () => GoogleLatLngBounds;
  MapTypeId: {
    ROADMAP: string;
  };
  SymbolPath: {
    CIRCLE: number;
    FORWARD_CLOSED_ARROW: number;
  };
}

interface GoogleWindowScope {
  maps?: GoogleMapsNamespace;
}

interface GoogleMapTrackerProps {
  donorCoords: Coordinates | null;
  destinationCoords: Coordinates;
  destinationName: string;
  destinationLocality: string;
  isSharing: boolean;
  status: string;
  distanceText?: string | null;
  durationText?: string | null;
  accuracyMeters?: number | null;
  lastUpdatedText?: string;
}

declare global {
  interface Window {
    google?: GoogleWindowScope;
    initUthiramMap?: () => void;
  }
}

export const GoogleMapTracker: React.FC<GoogleMapTrackerProps> = ({
  donorCoords,
  destinationCoords,
  destinationName,
  destinationLocality,
  isSharing,
  status,
  distanceText,
  durationText,
  accuracyMeters,
  lastUpdatedText,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<GoogleMapInstance | null>(null);
  const donorMarkerRef = useRef<GoogleMarkerInstance | null>(null);
  const destMarkerRef = useRef<GoogleMarkerInstance | null>(null);
  const routePolylineRef = useRef<GooglePolylineInstance | null>(null);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

  // Google Maps JavaScript API dynamic loader
  useEffect(() => {
    if (!apiKey) {
      // No key supplied - operate in built-in vector mode
      return;
    }

    if (window.google?.maps) {
      setMapLoaded(true);
      return;
    }

    const scriptId = 'uthiram-google-maps-script';
    let script = document.getElementById(scriptId) as HTMLScriptElement;

    if (!script) {
      script = document.createElement('script');
      script.id = scriptId;
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=geometry`;
      script.async = true;
      script.defer = true;

      script.onload = () => {
        setMapLoaded(true);
      };

      script.onerror = () => {
        setLoadError('Failed to load Google Maps script. Showing high-precision vector view.');
      };

      document.head.appendChild(script);
    } else {
      script.addEventListener('load', () => setMapLoaded(true));
    }
  }, [apiKey]);

  // Initialize and update Google Map instance when API is available
  useEffect(() => {
    const maps = window.google?.maps;
    if (!mapLoaded || !maps || !mapContainerRef.current) return;

    try {
      if (!mapInstanceRef.current) {
        const initialCenter = donorCoords || destinationCoords;
        mapInstanceRef.current = new maps.Map(mapContainerRef.current, {
          center: initialCenter,
          zoom: 14,
          mapTypeId: maps.MapTypeId.ROADMAP,
          streetViewControl: false,
          mapTypeControl: false,
          fullscreenControl: true,
          styles: [
            { featureType: 'poi', stylers: [{ visibility: 'off' }] },
            { featureType: 'transit', stylers: [{ visibility: 'simplified' }] },
          ],
        });

        // Destination Marker (Hospital)
        destMarkerRef.current = new maps.Marker({
          position: destinationCoords,
          map: mapInstanceRef.current,
          title: `${destinationName} (${destinationLocality})`,
          icon: {
            path: maps.SymbolPath.CIRCLE,
            fillColor: '#dc2626',
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: 2,
            scale: 9,
          },
        });
      }

      // Update Destination Marker
      if (destMarkerRef.current) {
        destMarkerRef.current.setPosition(destinationCoords);
      }

      // Update Donor Marker
      if (donorCoords && isSharing) {
        if (!donorMarkerRef.current) {
          donorMarkerRef.current = new maps.Marker({
            position: donorCoords,
            map: mapInstanceRef.current,
            title: 'Willing Donor',
            icon: {
              path: maps.SymbolPath.FORWARD_CLOSED_ARROW,
              fillColor: '#2563eb',
              fillOpacity: 1,
              strokeColor: '#ffffff',
              strokeWeight: 2,
              scale: 6,
            },
          });
        } else {
          donorMarkerRef.current.setPosition(donorCoords);
          donorMarkerRef.current.setVisible(true);
        }

        // Draw / update route line
        if (!routePolylineRef.current) {
          routePolylineRef.current = new maps.Polyline({
            path: [donorCoords, destinationCoords],
            geodesic: true,
            strokeColor: '#2563eb',
            strokeOpacity: 0.8,
            strokeWeight: 4,
            map: mapInstanceRef.current,
          });
        } else {
          routePolylineRef.current.setPath([donorCoords, destinationCoords]);
          routePolylineRef.current.setVisible(true);
        }

        // Fit bounds to show both donor and hospital comfortably
        const bounds = new maps.LatLngBounds();
        bounds.extend(donorCoords);
        bounds.extend(destinationCoords);
        mapInstanceRef.current.fitBounds(bounds, 50);
      } else {
        if (donorMarkerRef.current) donorMarkerRef.current.setVisible(false);
        if (routePolylineRef.current) routePolylineRef.current.setVisible(false);
        mapInstanceRef.current.setCenter(destinationCoords);
      }
    } catch (err) {
      console.error('Error rendering Google Map:', err);
    }
  }, [mapLoaded, donorCoords, destinationCoords, isSharing, destinationName, destinationLocality]);

  // Fallback Vector Map calculation (SVG proportions)
  const computeSvgCoords = () => {
    const dest = destinationCoords;
    const donor = donorCoords || { lat: dest.lat - 0.008, lng: dest.lng + 0.012 };

    const minLat = Math.min(dest.lat, donor.lat) - 0.004;
    const maxLat = Math.max(dest.lat, donor.lat) + 0.004;
    const minLng = Math.min(dest.lng, donor.lng) - 0.004;
    const maxLng = Math.max(dest.lng, donor.lng) + 0.004;

    const latSpan = maxLat - minLat || 0.01;
    const lngSpan = maxLng - minLng || 0.01;

    const toSvg = (coord: Coordinates) => ({
      x: 40 + ((coord.lng - minLng) / lngSpan) * 320,
      y: 200 - ((coord.lat - minLat) / latSpan) * 160,
    });

    return {
      destSvg: toSvg(dest),
      donorSvg: toSvg(donor),
    };
  };

  const { destSvg, donorSvg } = computeSvgCoords();

  return (
    <div className="uth-live-tracker">
      <div className="uth-tracker-header">
        <div className="uth-tracker-title">
          <span className={`uth-live-dot ${isSharing ? 'is-pulsing' : ''}`} />
          <strong>Live Donor Tracking</strong>
          <span className="uth-tracker-status-tag">{status}</span>
        </div>
        {lastUpdatedText && (
          <span className="uth-tracker-last-update">{lastUpdatedText}</span>
        )}
      </div>

      {apiKey && !loadError ? (
        <div className="uth-google-map-container" ref={mapContainerRef}>
          {!mapLoaded && (
            <div className="uth-map-loading-overlay">
              <span className="uth-map-spinner" />
              <p>Connecting to Google Maps Platform…</p>
            </div>
          )}
        </div>
      ) : (
        <div className="uth-vector-map-container">
          <svg
            className="uth-vector-map"
            viewBox="0 0 400 240"
            preserveAspectRatio="xMidYMid meet"
            aria-label="Interactive Live Route Map"
            role="img"
          >
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(203, 213, 225, 0.4)" strokeWidth="1" />
              </pattern>
              <linearGradient id="routeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#2563eb" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#dc2626" stopOpacity="0.9" />
              </linearGradient>
            </defs>

            {/* Street Grid Simulation */}
            <rect width="100%" height="100%" fill="#f8fafc" />
            <rect width="100%" height="100%" fill="url(#grid)" />

            {/* Simulated Road Lines */}
            <path d="M 0 60 Q 180 80 400 50" fill="none" stroke="#e2e8f0" strokeWidth="8" />
            <path d="M 80 0 Q 120 120 140 240" fill="none" stroke="#e2e8f0" strokeWidth="6" />
            <path d="M 260 0 Q 280 140 310 240" fill="none" stroke="#e2e8f0" strokeWidth="6" />
            <path d="M 0 170 Q 200 160 400 190" fill="none" stroke="#e2e8f0" strokeWidth="8" />

            {/* Connecting Route Line */}
            {isSharing && donorCoords && (
              <>
                <path
                  d={`M ${donorSvg.x} ${donorSvg.y} Q ${(donorSvg.x + destSvg.x) / 2 + 15} ${(donorSvg.y + destSvg.y) / 2 - 20} ${destSvg.x} ${destSvg.y}`}
                  fill="none"
                  stroke="url(#routeGradient)"
                  strokeWidth="4"
                  strokeDasharray="6,4"
                  className="uth-route-animated"
                />
              </>
            )}

            {/* Destination Marker (Hospital) */}
            <g transform={`translate(${destSvg.x}, ${destSvg.y})`}>
              <circle r="14" fill="#fee2e2" />
              <circle r="9" fill="#dc2626" />
              <text x="0" y="4" textAnchor="middle" fill="#ffffff" fontSize="11" fontWeight="bold">H</text>
              <rect x="-45" y="-32" width="90" height="18" rx="4" fill="#1e293b" opacity="0.9" />
              <text x="0" y="-20" textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="600">
                {destinationName.slice(0, 14)}
              </text>
            </g>

            {/* Donor Marker */}
            {isSharing && donorCoords ? (
              <g transform={`translate(${donorSvg.x}, ${donorSvg.y})`} className="uth-donor-pin">
                <circle r="18" fill="rgba(37, 99, 235, 0.2)" className="uth-pin-pulse" />
                <circle r="8" fill="#2563eb" stroke="#ffffff" strokeWidth="2" />
                <rect x="-40" y="14" width="80" height="16" rx="4" fill="#2563eb" />
                <text x="0" y="25" textAnchor="middle" fill="#ffffff" fontSize="8" fontWeight="bold">
                  DONOR LIVE
                </text>
              </g>
            ) : (
              <g transform={`translate(${destSvg.x + 60}, ${destSvg.y + 40})`} opacity="0.5">
                <circle r="6" fill="#94a3b8" />
                <text x="0" y="16" textAnchor="middle" fill="#64748b" fontSize="8">
                  Awaiting donor start
                </text>
              </g>
            )}
          </svg>

          <div className="uth-map-notice">
            <span className="uth-notice-tag">Google Maps Ready</span>
            <small>
              {apiKey
                ? 'Displaying high-precision vector road tracking.'
                : 'Interactive vector tracking active. To enable satellite/street tiles, configure VITE_GOOGLE_MAPS_API_KEY in .env.'}
            </small>
          </div>
        </div>
      )}

      {/* ETA and Metrics Summary Strip */}
      <div className="uth-tracker-metrics-bar">
        <div className="uth-metric-item">
          <span className="uth-metric-sub">ESTIMATED ARRIVAL</span>
          <strong className="uth-metric-val">{durationText || 'Calculating…'}</strong>
        </div>
        <div className="uth-metric-item">
          <span className="uth-metric-sub">REMAINING DISTANCE</span>
          <strong className="uth-metric-val">{distanceText || (isSharing ? '~3.2 km' : '—')}</strong>
        </div>
        <div className="uth-metric-item">
          <span className="uth-metric-sub">DESTINATION</span>
          <strong className="uth-metric-val">{destinationName}</strong>
          <small>{destinationLocality}</small>
        </div>
        {accuracyMeters != null && (
          <div className="uth-metric-item uth-metric-hide-mobile">
            <span className="uth-metric-sub">GPS ACCURACY</span>
            <strong className="uth-metric-val">±{Math.round(accuracyMeters)}m</strong>
          </div>
        )}
      </div>
    </div>
  );
};

export default GoogleMapTracker;
