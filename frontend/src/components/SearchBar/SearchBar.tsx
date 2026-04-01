import { useState, useRef, useCallback, useEffect } from 'react';
import './SearchBar.css';
import { useAppStore } from '../../store/useAppStore';
import { fetchRoute } from '../../services/routingService';
import type { LocationPoint } from '../../store/useAppStore';

interface NominatimResult {
  place_id: number;
  display_name: string;
  lat: string;
  lon: string;
}

async function nominatimSearch(query: string): Promise<NominatimResult[]> {
  if (!query.trim()) return [];
  const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=5`;
  const resp = await fetch(url, { headers: { 'User-Agent': 'Wheelway/1.0 (wheelchair-navigation)' } });
  return resp.json();
}

function useDebounce<T extends (...args: Parameters<T>) => void>(fn: T, delay: number): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  return useCallback(
    (...args: Parameters<T>) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => fn(...args), delay);
    },
    [fn, delay]
  ) as T;
}

export default function SearchBar() {
  const {
    origin,
    destination,
    activeField,
    setOrigin,
    setDestination,
    setRoute,
    setLoading,
    setError,
    setFlyTo,
    setActiveField,
  } = useAppStore();

  const [fromInput, setFromInput] = useState('');
  const [toInput, setToInput] = useState('');
  const [fromSuggestions, setFromSuggestions] = useState<NominatimResult[]>([]);
  const [toSuggestions, setToSuggestions] = useState<NominatimResult[]>([]);
  const [fromOpen, setFromOpen] = useState(false);
  const [toOpen, setToOpen] = useState(false);

  // Keep store actions in a ref so the auto-fetch effect always uses the latest version
  const storeRef = useRef({ setLoading, setError, setRoute });
  useEffect(() => {
    storeRef.current = { setLoading, setError, setRoute };
  });

  useEffect(() => { setFromInput(origin?.label ?? ''); }, [origin]);
  useEffect(() => { setToInput(destination?.label ?? ''); }, [destination]);

  const doFetch = useCallback(async (o: LocationPoint, d: LocationPoint) => {
    const { setLoading, setError, setRoute } = storeRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchRoute(o.lat, o.lng, d.lat, d.lng);
      setRoute(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch route.');
    } finally {
      setLoading(false);
    }
  }, []); // stable — reads store actions from ref at call time

  // Auto-fetch when both points are set
  useEffect(() => {
    if (origin && destination) {
      doFetch(origin, destination);
    }
  }, [origin, destination, doFetch]);

  const searchFrom = useCallback(async (q: string) => {
    const results = await nominatimSearch(q);
    setFromSuggestions(results);
    setFromOpen(results.length > 0);
  }, []);

  const searchTo = useCallback(async (q: string) => {
    const results = await nominatimSearch(q);
    setToSuggestions(results);
    setToOpen(results.length > 0);
  }, []);

  const debouncedSearchFrom = useDebounce(searchFrom, 300);
  const debouncedSearchTo = useDebounce(searchTo, 300);

  const handleFromChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setFromInput(val);
    setOrigin(null);
    if (val.length >= 2) debouncedSearchFrom(val);
    else { setFromSuggestions([]); setFromOpen(false); }
  };

  const handleToChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setToInput(val);
    setDestination(null);
    if (val.length >= 2) debouncedSearchTo(val);
    else { setToSuggestions([]); setToOpen(false); }
  };

  const selectFrom = (r: NominatimResult) => {
    const newOrigin: LocationPoint = { lat: parseFloat(r.lat), lng: parseFloat(r.lon), label: r.display_name };
    setOrigin(newOrigin);
    setFlyTo({ lat: newOrigin.lat, lng: newOrigin.lng });
    setFromInput(r.display_name);
    setFromOpen(false);
    setFromSuggestions([]);
  };

  const selectTo = (r: NominatimResult) => {
    const newDest: LocationPoint = { lat: parseFloat(r.lat), lng: parseFloat(r.lon), label: r.display_name };
    setDestination(newDest);
    setFlyTo({ lat: newDest.lat, lng: newDest.lng });
    setToInput(r.display_name);
    setToOpen(false);
    setToSuggestions([]);
  };

  const clearFrom = (e: React.MouseEvent) => {
    e.stopPropagation();
    setOrigin(null);
    setFromInput('');
    setFromSuggestions([]);
    setFromOpen(false);
    setRoute(null);
  };

  const clearTo = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDestination(null);
    setToInput('');
    setToSuggestions([]);
    setToOpen(false);
    setRoute(null);
  };

  return (
    <div className="search-bar-container" role="search" aria-label="Route search">
      <div className="search-bar-inner">
        <div className="search-inputs">

          {/* Origin field */}
          <div
            className={`input-group${activeField === 'origin' ? ' input-group--active input-group--origin' : ''}`}
            onClick={() => setActiveField('origin')}
          >
            <span className="input-icon origin-dot" aria-hidden="true" />
            <div className="autocomplete-wrapper">
              <input
                type="text"
                className="search-input"
                placeholder="From: click here then click map"
                value={fromInput}
                onChange={handleFromChange}
                onFocus={(e) => {
                  e.target.select();
                  setActiveField('origin');
                  if (fromSuggestions.length > 0) setFromOpen(true);
                }}
                onBlur={() => setTimeout(() => setFromOpen(false), 150)}
                aria-label="Origin location"
                aria-autocomplete="list"
                aria-expanded={fromOpen}
              />
              {fromOpen && fromSuggestions.length > 0 && (
                <ul className="suggestions-list" role="listbox" aria-label="Origin suggestions">
                  {fromSuggestions.map((r) => (
                    <li key={r.place_id} role="option" className="suggestion-item" onMouseDown={() => selectFrom(r)}>
                      {r.display_name}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {fromInput && (
              <button className="input-clear-btn" onClick={clearFrom} aria-label="Clear origin" tabIndex={-1}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
          </div>

          <div className="input-separator" aria-hidden="true" />

          {/* Destination field */}
          <div
            className={`input-group${activeField === 'destination' ? ' input-group--active input-group--destination' : ''}`}
            onClick={() => setActiveField('destination')}
          >
            <span className="input-icon dest-dot" aria-hidden="true" />
            <div className="autocomplete-wrapper">
              <input
                type="text"
                className="search-input"
                placeholder="To: click here then click map"
                value={toInput}
                onChange={handleToChange}
                onFocus={(e) => {
                  e.target.select();
                  setActiveField('destination');
                  if (toSuggestions.length > 0) setToOpen(true);
                }}
                onBlur={() => setTimeout(() => setToOpen(false), 150)}
                aria-label="Destination location"
                aria-autocomplete="list"
                aria-expanded={toOpen}
              />
              {toOpen && toSuggestions.length > 0 && (
                <ul className="suggestions-list" role="listbox" aria-label="Destination suggestions">
                  {toSuggestions.map((r) => (
                    <li key={r.place_id} role="option" className="suggestion-item" onMouseDown={() => selectTo(r)}>
                      {r.display_name}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {toInput && (
              <button className="input-clear-btn" onClick={clearTo} aria-label="Clear destination" tabIndex={-1}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
