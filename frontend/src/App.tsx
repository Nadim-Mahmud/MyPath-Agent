import { useState, useEffect, Component } from 'react';
import type { ReactNode } from 'react';
import './App.css';
import { useAppStore } from './store/useAppStore';
import MapCanvas from './components/Map/MapCanvas';
import SearchBar from './components/SearchBar/SearchBar';
import RoutePanel from './components/RoutePanel/RoutePanel';
import ChatButton from './components/AiChat/ChatButton';
import ChatPanel from './components/AiChat/ChatPanel';
import PreferencesPanel from './components/Preferences/PreferencesPanel';

class MapErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; mountKey: number }
> {
  state = { hasError: false, mountKey: 0 };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch() {
    // Remount children cleanly after the current render cycle
    setTimeout(() => {
      this.setState(s => ({ hasError: false, mountKey: s.mountKey + 1 }));
    }, 0);
  }

  render() {
    if (this.state.hasError) return null;
    return (
      <div key={this.state.mountKey} style={{ position: 'absolute', inset: 0 }}>
        {this.props.children}
      </div>
    );
  }
}

function ErrorToast() {
  const { error, setError } = useAppStore();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (error) {
      setVisible(true);
      const timer = setTimeout(() => {
        setVisible(false);
        setTimeout(() => setError(null), 300);
      }, 6000);
      return () => clearTimeout(timer);
    }
  }, [error, setError]);

  if (!error) return null;

  return (
    <div className={`error-toast${visible ? ' error-toast--visible' : ''}`} role="alert">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ flexShrink: 0 }}>
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <span>{error}</span>
      <button
        className="error-toast-close"
        onClick={() => { setVisible(false); setTimeout(() => setError(null), 300); }}
        aria-label="Dismiss error"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}

function DarkModeToggle() {
  const { darkMode, toggleDarkMode } = useAppStore();
  return (
    <button
      className="dark-mode-btn"
      onClick={toggleDarkMode}
      aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
      title={darkMode ? 'Light Mode' : 'Dark Mode'}
    >
      {darkMode ? (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      ) : (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      )}
    </button>
  );
}

export default function App() {
  const { darkMode, route } = useAppStore();
  const [routePanelOpen, setRoutePanelOpen] = useState(false);

  // Open panel whenever a route is fetched
  useEffect(() => {
    if (route) setRoutePanelOpen(true);
  }, [route]);

  const showRoutePanel = !!route && routePanelOpen;

  return (
    <div
      className="app-root"
      data-theme={darkMode ? 'dark' : 'light'}
    >
      {/* Full-screen map */}
      <MapErrorBoundary>
        <MapCanvas />
      </MapErrorBoundary>

      {/* Search bar pinned top-center */}
      <SearchBar />

      {/* Route panel slides in from the left */}
      <div
        className={`route-panel-wrapper${showRoutePanel ? ' route-panel-wrapper--open' : ''}`}
        aria-hidden={!showRoutePanel}
      >
        {showRoutePanel && (
          <RoutePanel onClose={() => setRoutePanelOpen(false)} />
        )}
      </div>

      {/* Top-right controls */}
      <div className="top-right-controls">
        <DarkModeToggle />
        <div className="prefs-wrapper">
          <PreferencesPanel />
        </div>
      </div>

      {/* Error toast */}
      <ErrorToast />

      {/* AI Chat floating button + panel */}
      <ChatButton />
      <ChatPanel />

      {/* Re-open route panel button (when route exists but panel is closed) */}
      {route && !routePanelOpen && (
        <button
          className="reopen-panel-btn"
          onClick={() => setRoutePanelOpen(true)}
          aria-label="Show route directions"
          title="Show Directions"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          Directions
        </button>
      )}
    </div>
  );
}
