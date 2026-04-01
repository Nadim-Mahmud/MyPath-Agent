import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  useMapEvents,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './MapCanvas.css';
import { useAppStore } from '../../store/useAppStore';
import type { RoutePoint } from '../../types/route';

// Fix Leaflet default icon issue
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

function makeStartIcon(active: boolean) {
  return L.divIcon({
    className: '',
    html: `<div class="marker-wrap${active ? ' marker-wrap--active marker-wrap--origin' : ''}">
      <svg width="28" height="36" viewBox="0 0 28 36" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 0C6.268 0 0 6.268 0 14c0 9.333 14 22 14 22S28 23.333 28 14C28 6.268 21.732 0 14 0z" fill="#16a34a"/>
        <circle cx="14" cy="14" r="6" fill="white"/>
      </svg>
    </div>`,
    iconSize: [28, 36],
    iconAnchor: [14, 36],
  });
}

function makeEndIcon(active: boolean) {
  return L.divIcon({
    className: '',
    html: `<div class="marker-wrap${active ? ' marker-wrap--active marker-wrap--dest' : ''}">
      <svg width="28" height="36" viewBox="0 0 28 36" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 0C6.268 0 0 6.268 0 14c0 9.333 14 22 14 22S28 23.333 28 14C28 6.268 21.732 0 14 0z" fill="#dc2626"/>
        <circle cx="14" cy="14" r="6" fill="white"/>
      </svg>
    </div>`,
    iconSize: [28, 36],
    iconAnchor: [14, 36],
  });
}

function getSurfaceColor(surface: string): string {
  switch (surface?.toLowerCase()) {
    case 'asphalt':
    case 'concrete':
      return '#1A56DB';
    case 'paving_stones':
    case 'sett':
      return '#f59e0b';
    case 'unpaved':
    case 'gravel':
    case 'dirt':
      return '#ef4444';
    default:
      return '#6b7280';
  }
}

interface MapClickHandlerProps {
  onMapClick: (lat: number, lng: number) => void;
  activeField: 'origin' | 'destination' | null;
}

function MapClickHandler({ onMapClick, activeField }: MapClickHandlerProps) {
  useMapEvents({
    click(e) {
      if (activeField) {
        onMapClick(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

interface ActiveStepPannerProps {
  activeStepIndex: number;
  routePoints: RoutePoint[];
}

function ActiveStepPanner({ activeStepIndex, routePoints }: ActiveStepPannerProps) {
  const map = useMap();

  useEffect(() => {
    if (activeStepIndex >= 0 && routePoints[activeStepIndex]) {
      const step = routePoints[activeStepIndex];
      const lat = step.start_location.latitude;
      const lng = step.start_location.longitude;
      if (lat !== 0 || lng !== 0) {
        map.panTo([lat, lng]);
      }
    }
  }, [activeStepIndex, routePoints, map]);

  return null;
}

function MapRefCapture({ mapRef }: { mapRef: { current: L.Map | null } }) {
  const map = useMap();
  mapRef.current = map;
  return null;
}

async function reverseGeocode(lat: number, lng: number): Promise<string> {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`,
      { headers: { 'User-Agent': 'Wheelway/1.0 (wheelchair-navigation)' } }
    );
    const data = await response.json();
    return data.display_name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  } catch {
    return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  }
}

export default function MapCanvas() {
  const {
    route, activeStepIndex, origin, destination,
    setOrigin, setDestination,
    flyTo, setFlyTo,
    activeField,
  } = useAppStore();

  const mapRef = useRef<L.Map | null>(null);
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState<string | null>(null);

  // Pan map when flyTo is triggered from search bar
  useEffect(() => {
    if (flyTo && mapRef.current) {
      mapRef.current.setView([flyTo.lat, flyTo.lng], flyTo.zoom ?? 15, { animate: true });
      setFlyTo(null);
    }
  }, [flyTo, setFlyTo]);

  // Auto-focus on user's location on first load
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        mapRef.current?.setView([pos.coords.latitude, pos.coords.longitude], 14, { animate: false });
      },
      () => {},
      { enableHighAccuracy: false, timeout: 8000 }
    );
  }, []);

  const handleMapClick = useCallback(
    async (lat: number, lng: number) => {
      const label = await reverseGeocode(lat, lng);
      if (activeField === 'origin') {
        setOrigin({ lat, lng, label });
      } else if (activeField === 'destination') {
        setDestination({ lat, lng, label });
      }
    },
    [activeField, setOrigin, setDestination]
  );

  const handleLocateMe = useCallback(() => {
    if (!navigator.geolocation) {
      setLocateError('Geolocation is not supported by your browser');
      return;
    }
    setLocating(true);
    setLocateError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        mapRef.current?.setView([pos.coords.latitude, pos.coords.longitude], 16, { animate: true });
        setLocating(false);
      },
      () => {
        setLocateError('Unable to retrieve your location');
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }, []);

  const routePoints = route?.routes?.points ?? [];

  const allPolylinePoints = routePoints.flatMap((seg) =>
    seg.points.map((p) => [p.latitude, p.longitude] as [number, number])
  );

  const startIcon = useMemo(() => makeStartIcon(activeField === 'origin'), [activeField]);
  const endIcon = useMemo(() => makeEndIcon(activeField === 'destination'), [activeField]);

  const originCoord = origin ? ([origin.lat, origin.lng] as [number, number]) : null;
  const destCoord = destination ? ([destination.lat, destination.lng] as [number, number]) : null;

  const startCoord = originCoord ?? (routePoints.length > 0
    ? ([routePoints[0].start_location.latitude, routePoints[0].start_location.longitude] as [number, number])
    : null);

  const endCoord = destCoord ?? (routePoints.length > 0
    ? ([routePoints[routePoints.length - 1].end_location.latitude, routePoints[routePoints.length - 1].end_location.longitude] as [number, number])
    : null);

  const showCrosshair = !!activeField;

  return (
    <div className={`map-canvas-wrapper${showCrosshair ? ' crosshair-cursor' : ''}`}>
      <MapContainer
        center={[40.7128, -74.006]}
        zoom={13}
        style={{ height: '100%', width: '100%' }}
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapRefCapture mapRef={mapRef} />
        <MapClickHandler onMapClick={handleMapClick} activeField={activeField} />

        {routePoints.length > 0 && activeStepIndex >= 0 && (
          <ActiveStepPanner activeStepIndex={activeStepIndex} routePoints={routePoints} />
        )}

        {/* Full route polyline */}
        {allPolylinePoints.length > 0 && (
          <Polyline
            positions={allPolylinePoints}
            pathOptions={{ color: '#1A56DB', weight: 4, opacity: 0.8 }}
          />
        )}

        {/* Colored segments by surface */}
        {routePoints.map((seg, idx) => {
          const segPoints = seg.points.map((p) => [p.latitude, p.longitude] as [number, number]);
          const isActive = idx === activeStepIndex;
          return (
            <Polyline
              key={idx}
              positions={segPoints}
              pathOptions={{
                color: getSurfaceColor(seg.surface),
                weight: isActive ? 7 : 4,
                opacity: isActive ? 1 : 0.75,
              }}
            />
          );
        })}

        {/* Origin marker */}
        {startCoord && startCoord[0] !== 0 && (
          <Marker position={startCoord} icon={startIcon} />
        )}

        {/* Destination marker */}
        {endCoord && endCoord[0] !== 0 && (
          <Marker position={endCoord} icon={endIcon} />
        )}
      </MapContainer>

      {/* Locate me button */}
      <button
        className={`locate-me-btn${locating ? ' locating' : ''}`}
        onClick={handleLocateMe}
        aria-label="Focus on my current location"
        title="Focus on my current location"
        disabled={locating}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
          <circle cx="12" cy="12" r="8" />
        </svg>
      </button>

      {locateError && (
        <div className="locate-error" role="alert">{locateError}</div>
      )}
    </div>
  );
}
