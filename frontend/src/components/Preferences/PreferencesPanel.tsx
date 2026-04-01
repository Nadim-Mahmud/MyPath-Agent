import { useState } from 'react';
import './Preferences.css';
import { useAppStore } from '../../store/useAppStore';

export default function PreferencesPanel() {
  const [open, setOpen] = useState(false);
  const { preferences, setPreferences } = useAppStore();

  return (
    <>
      <button
        className="prefs-toggle-btn"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close preferences' : 'Open route preferences'}
        aria-expanded={open}
        title="Route Preferences"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.07 4.93A10 10 0 0 0 6.93 4.93"/>
          <path d="M4.93 6.93A10 10 0 0 0 4.93 17.07"/>
          <path d="M6.93 19.07A10 10 0 0 0 19.07 19.07"/>
          <path d="M19.07 17.07A10 10 0 0 0 19.07 6.93"/>
        </svg>
      </button>

      {open && (
        <div
          className="prefs-panel"
          role="dialog"
          aria-label="Route preferences"
          aria-modal="false"
        >
          <div className="prefs-header">
            <h2 className="prefs-title">Route Preferences</h2>
            <button
              className="prefs-close-btn"
              onClick={() => setOpen(false)}
              aria-label="Close preferences"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <div className="prefs-body">
            {/* Max Incline Slider */}
            <div className="pref-item">
              <label className="pref-label" htmlFor="max-incline">
                <div className="pref-label-text">
                  <span>Maximum Incline</span>
                  <span className="pref-value-badge">{preferences.maxIncline}%</span>
                </div>
                <p className="pref-description">
                  Avoid routes with grades steeper than this threshold.
                </p>
              </label>
              <div className="slider-wrapper">
                <span className="slider-min">0%</span>
                <input
                  id="max-incline"
                  type="range"
                  min={0}
                  max={15}
                  step={1}
                  value={preferences.maxIncline}
                  onChange={(e) => setPreferences({ maxIncline: Number(e.target.value) })}
                  className="pref-slider"
                  aria-valuemin={0}
                  aria-valuemax={15}
                  aria-valuenow={preferences.maxIncline}
                  aria-valuetext={`${preferences.maxIncline}% maximum grade`}
                />
                <span className="slider-max">15%</span>
              </div>
            </div>

            <div className="pref-divider" aria-hidden="true" />

            {/* Avoid Cobblestones Toggle */}
            <div className="pref-item">
              <div className="pref-toggle-row">
                <div>
                  <span className="pref-toggle-label">Avoid Cobblestones</span>
                  <p className="pref-description">
                    Prefer routes with smooth, paved surfaces over cobblestone or sett surfaces.
                  </p>
                </div>
                <label className="toggle-switch" aria-label="Avoid cobblestones toggle">
                  <input
                    type="checkbox"
                    checked={preferences.avoidCobblestones}
                    onChange={(e) => setPreferences({ avoidCobblestones: e.target.checked })}
                    aria-checked={preferences.avoidCobblestones}
                  />
                  <span className="toggle-track">
                    <span className="toggle-thumb" />
                  </span>
                </label>
              </div>
            </div>

            <div className="pref-divider" aria-hidden="true" />

            {/* Prefer Covered Routes Toggle */}
            <div className="pref-item">
              <div className="pref-toggle-row">
                <div>
                  <span className="pref-toggle-label">Prefer Covered Routes</span>
                  <p className="pref-description">
                    Favor routes with overhead cover, such as arcades or covered walkways.
                  </p>
                </div>
                <label className="toggle-switch" aria-label="Prefer covered routes toggle">
                  <input
                    type="checkbox"
                    checked={preferences.preferCovered}
                    onChange={(e) => setPreferences({ preferCovered: e.target.checked })}
                    aria-checked={preferences.preferCovered}
                  />
                  <span className="toggle-track">
                    <span className="toggle-thumb" />
                  </span>
                </label>
              </div>
            </div>
          </div>

          <div className="prefs-footer">
            <p className="prefs-note">
              Preferences are applied to future route searches.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
