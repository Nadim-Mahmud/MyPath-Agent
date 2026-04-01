import { useRef, useEffect, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './AiChat.css';
import { useAppStore } from '../../store/useAppStore';
import { sendChat } from '../../services/chatService';

const MAX_CHARS = 500;
const CURRENT_LOCATION_ROUTE_INTENT = /(?:my|current)\s+location|from\s+here|route\s+me\s+to|directions\s+to|navigate\s+to/i;

async function reverseGeocodeLabel(lat: number, lng: number): Promise<string> {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`,
      { headers: { 'User-Agent': 'Wheelway/1.0 (wheelchair-navigation)' } },
    );
    const data = await response.json();
    if (typeof data?.display_name === 'string' && data.display_name.trim()) {
      return data.display_name.trim();
    }
  } catch {
    // Fallback handled below
  }
  return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
}

async function resolveRouteLabel(
  point: { lat: number; lng: number; label?: string | null },
  fallbackText: string,
): Promise<string> {
  const provided = point.label?.trim();
  if (provided) return provided;
  const resolved = await reverseGeocodeLabel(point.lat, point.lng);
  return resolved || fallbackText;
}

export default function ChatPanel() {
  const {
    chatOpen,
    toggleChat,
    chatMessages,
    chatSessionId,
    isChatLoading,
    addChatMessage,
    setChatLoading,
    clearChatMessages,
    route,
    origin,
    destination,
    userPosition,
    setOrigin,
    setDestination,
    setFlyTo,
    setError,
  } = useAppStore();

  const [input, setInput] = useState('');
  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [chatMessages]);

  useEffect(() => {
    if (chatOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [chatOpen]);

  const resolveUserLocation = useCallback(async (): Promise<{ lat: number; lng: number } | null> => {
    if (userPosition) {
      return { lat: userPosition[0], lng: userPosition[1] };
    }
    if (!navigator.geolocation) {
      return null;
    }

    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        },
        () => resolve(null),
        { enableHighAccuracy: true, timeout: 3000, maximumAge: 30000 },
      );
    });
  }, [userPosition]);

  const buildContext = useCallback(async () => {
    const userLocation = await resolveUserLocation();
    return {
      user_location: userLocation,
      active_route: route ?? null,
      map_center: origin
        ? { lat: origin.lat, lng: origin.lng }
        : destination
        ? { lat: destination.lat, lng: destination.lng }
        : null,
    };
  }, [resolveUserLocation, route, origin, destination]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isChatLoading) return;

    setInput('');
    addChatMessage({ role: 'user', content: text });
    setChatLoading(true);

    try {
      const context = await buildContext();
      const wantsCurrentLocationRoute = CURRENT_LOCATION_ROUTE_INTENT.test(text);
      if (wantsCurrentLocationRoute && !context.user_location) {
        setError('Location is required for current-location routing. Enable GPS permission and try again.');
        addChatMessage({
          role: 'assistant',
          content: 'Please enable location access so I can route from your current location.',
        });
        return;
      }

      const response = await sendChat(chatSessionId, text, context);
      addChatMessage({ role: 'assistant', content: response.message });

      if (response.route_action) {
        const nextOrigin = response.route_action.origin;
        const nextDestination = response.route_action.destination;
        const [originLabel, destinationLabel] = await Promise.all([
          resolveRouteLabel(nextOrigin, 'AI selected origin'),
          resolveRouteLabel(nextDestination, 'AI selected destination'),
        ]);

        setOrigin({
          lat: nextOrigin.lat,
          lng: nextOrigin.lng,
          label: originLabel,
        });
        setDestination({
          lat: nextDestination.lat,
          lng: nextDestination.lng,
          label: destinationLabel,
        });
        setFlyTo({ lat: nextOrigin.lat, lng: nextOrigin.lng, zoom: 14 });
      }
    } catch (err) {
      addChatMessage({
        role: 'assistant',
        content: (err as Error).message ?? 'Something went wrong. Please try again.',
      });
    } finally {
      setChatLoading(false);
    }
  }, [
    input,
    isChatLoading,
    chatSessionId,
    buildContext,
    addChatMessage,
    setChatLoading,
    setOrigin,
    setDestination,
    setFlyTo,
    setError,
  ]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className={`chat-panel${chatOpen ? ' chat-panel--open' : ''}`}
      role="dialog"
      aria-label="AI Chat"
      aria-hidden={!chatOpen}
    >
      {/* Header */}
      <div className="chat-panel-header">
        <div className="chat-panel-title">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <span>Wheelway AI</span>
        </div>
        <div className="chat-header-actions">
          {chatMessages.length > 0 && (
            <button
              className="chat-clear-btn"
              onClick={clearChatMessages}
              aria-label="Clear conversation"
              title="Clear conversation"
              disabled={isChatLoading}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                <path d="M10 11v6M14 11v6"/>
              </svg>
            </button>
          )}
          <button className="chat-close-btn" onClick={toggleChat} aria-label="Close chat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Message thread */}
      <div className="chat-panel-body" ref={bodyRef} role="log" aria-live="polite" aria-label="Chat messages">
        {chatMessages.length === 0 ? (
          <div className="chat-empty-state">
            <div className="chat-empty-icon" aria-hidden="true">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4">
                <circle cx="12" cy="4" r="1.5" fill="currentColor" stroke="none"/>
                <path d="M12 6v5l3 3" strokeLinecap="round"/>
                <path d="M9 11H7l-2 6h10l-1-3" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="8" cy="19" r="2"/>
                <circle cx="15" cy="19" r="2"/>
              </svg>
            </div>
            <p className="chat-empty-title">Ask Wheelway AI</p>
            <p className="chat-empty-hint">
              Try: <em>"Find me an accessible route to Central Park"</em> or{' '}
              <em>"Are there ramps near my location?"</em>
            </p>
          </div>
        ) : (
          <div className="chat-messages">
            {chatMessages.map((msg, i) => (
              <div
                key={i}
                className={`chat-message chat-message--${msg.role}`}
                aria-label={`${msg.role === 'user' ? 'You' : 'Wheelway AI'}: ${msg.content}`}
              >
                <div className="chat-bubble">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              </div>
            ))}
            {isChatLoading && (
              <div className="chat-message chat-message--assistant" aria-label="Wheelway AI is typing">
                <div className="chat-bubble chat-bubble--typing" aria-hidden="true">
                  <span /><span /><span />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input footer */}
      <div className="chat-panel-footer">
        <div className="chat-input-wrapper">
          <input
            ref={inputRef}
            type="text"
            className="chat-input"
            placeholder="Ask about accessible routes, ramps, elevators…"
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, MAX_CHARS))}
            onKeyDown={handleKeyDown}
            disabled={isChatLoading}
            aria-label="Chat input"
            aria-disabled={isChatLoading}
            maxLength={MAX_CHARS}
          />
          {input.length > MAX_CHARS - 60 && (
            <span className="chat-char-count" aria-live="polite">
              {input.length}/{MAX_CHARS}
            </span>
          )}
        </div>
        <button
          className={`chat-send-btn${!isChatLoading && input.trim() ? ' chat-send-btn--active' : ''}`}
          onClick={handleSend}
          disabled={isChatLoading || !input.trim()}
          aria-label="Send message"
        >
          {isChatLoading ? (
            <svg className="chat-spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
