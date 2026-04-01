import './RoutePanel.css';
import { useAppStore } from '../../store/useAppStore';
import type { RoutePoint } from '../../types/route';

function ManeuverIcon({ maneuver }: { maneuver: string }) {
  const m = maneuver?.toLowerCase() ?? '';

  if (m.includes('left')) {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
        <polyline points="15 18 9 12 15 6" />
      </svg>
    );
  }
  if (m.includes('right')) {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
        <polyline points="9 18 15 12 9 6" />
      </svg>
    );
  }
  if (m.includes('u-turn') || m.includes('uturn')) {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
        <polyline points="4 9 4 4 9 4" />
        <path d="M20 20v-7a4 4 0 0 0-4-4H4" />
      </svg>
    );
  }
  if (m.includes('arrive') || m.includes('destination')) {
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
        <circle cx="12" cy="10" r="3" />
      </svg>
    );
  }
  // Default: straight ahead
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
      <line x1="12" y1="19" x2="12" y2="5" />
      <polyline points="5 12 12 5 19 12" />
    </svg>
  );
}

function SurfaceBadge({ surface }: { surface: string }) {
  const labelMap: Record<string, string> = {
    asphalt: 'Asphalt',
    concrete: 'Concrete',
    paving_stones: 'Paving Stones',
    sett: 'Sett',
    unpaved: 'Unpaved',
    gravel: 'Gravel',
    dirt: 'Dirt',
  };
  const colorMap: Record<string, string> = {
    asphalt: 'badge-blue',
    concrete: 'badge-blue',
    paving_stones: 'badge-amber',
    sett: 'badge-amber',
    unpaved: 'badge-red',
    gravel: 'badge-red',
    dirt: 'badge-red',
  };
  const label = labelMap[surface?.toLowerCase()] ?? surface ?? 'Unknown';
  const color = colorMap[surface?.toLowerCase()] ?? 'badge-gray';
  return <span className={`surface-badge ${color}`}>{label}</span>;
}

function formatDistance(points: RoutePoint[]): string {
  const totalFeet = points.reduce((sum, p) => sum + (p.distance?.value ?? 0), 0);
  const miles = totalFeet / 5280;
  if (miles < 0.1) return `${Math.round(totalFeet)} ft`;
  return `${miles.toFixed(2)} mi`;
}

function formatDuration(points: RoutePoint[]): string {
  const totalSeconds = points.reduce((sum, p) => sum + (p.duration?.value ?? 0), 0);
  const minutes = Math.round(totalSeconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
}

interface RoutePanelProps {
  onClose: () => void;
}

export default function RoutePanel({ onClose }: RoutePanelProps) {
  const { route, activeStepIndex, setActiveStep } = useAppStore();

  if (!route) return null;

  const points = (route.routes?.points ?? []).filter((step): step is RoutePoint => !!step && typeof step === 'object');

  return (
    <div className="route-panel" role="complementary" aria-label="Turn-by-turn directions">
      <div className="route-panel-header">
        <div className="route-summary">
          <div className="route-stat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm-8 2a2 2 0 1 1-4 0 2 2 0 0 1 4 0z"/>
            </svg>
            <span>{formatDistance(points)}</span>
          </div>
          <div className="route-stat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>{formatDuration(points)}</span>
          </div>
        </div>
        <button className="close-btn" onClick={onClose} aria-label="Close route panel">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="route-steps-list" role="list">
        {points.map((step, idx) => {
          const isActive = idx === activeStepIndex;
          const isHighIncline = step.incline > 5;
          return (
            <button
              key={idx}
              role="listitem"
              className={`route-step${isActive ? ' active' : ''}`}
              onClick={() => setActiveStep(isActive ? -1 : idx)}
              aria-pressed={isActive}
              aria-label={`Step ${idx + 1}: ${step.maneuver ?? 'Continue'}, ${step.distance?.text ?? ''}`}
            >
              <div className="step-icon" aria-hidden="true">
                <ManeuverIcon maneuver={step.maneuver ?? ''} />
              </div>
              <div className="step-content">
                <div className="step-top">
                  <span className="step-maneuver">
                    {step.maneuver
                      ? step.maneuver
                          .split('-')
                          .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                          .join(' ')
                      : 'Continue'}
                  </span>
                  <SurfaceBadge surface={step.surface} />
                </div>
                {step.instructions && (
                  <p className="step-instructions">{step.instructions}</p>
                )}
                <div className="step-meta">
                  <span className="step-distance">{step.distance?.text ?? '—'}</span>
                  <span className="step-duration">{step.duration?.text ?? '—'}</span>
                  <span className={`step-incline${isHighIncline ? ' incline-high' : ''}`}>
                    {step.incline != null ? `${step.incline.toFixed(1)}% grade` : '—'}
                    {isHighIncline && (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-label="Steep incline warning">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                        <line x1="12" y1="9" x2="12" y2="13"/>
                        <line x1="12" y1="17" x2="12.01" y2="17"/>
                      </svg>
                    )}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
