import './AiChat.css';
import { useAppStore } from '../../store/useAppStore';

export default function ChatPanel() {
  const { chatOpen, toggleChat } = useAppStore();

  return (
    <div
      className={`chat-panel${chatOpen ? ' chat-panel--open' : ''}`}
      role="dialog"
      aria-label="AI Chat"
      aria-hidden={!chatOpen}
    >
      <div className="chat-panel-header">
        <div className="chat-panel-title">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <span>Wheelway AI Assistant</span>
        </div>
        <button className="chat-close-btn" onClick={toggleChat} aria-label="Close chat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div className="chat-panel-body">
        <div className="chat-coming-soon">
          <div className="chat-coming-soon-icon" aria-hidden="true">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
              <path d="M12 6v6l4 2"/>
            </svg>
          </div>
          <h3 className="chat-coming-soon-title">AI Chat — Coming Soon</h3>
          <p className="chat-coming-soon-desc">
            Our AI-powered accessibility assistant is currently in development. Soon you'll be able to:
          </p>
          <ul className="chat-feature-list">
            <li>Ask about wheelchair-accessible routes and paths</li>
            <li>Get real-time surface condition updates</li>
            <li>Find accessible points of interest nearby</li>
            <li>Report barriers and hazards on your route</li>
          </ul>
          <p className="chat-coming-soon-note">
            The AI is powered by our Spring Boot backend and will be available in a future update.
          </p>
        </div>
      </div>

      <div className="chat-panel-footer">
        <input
          type="text"
          className="chat-input"
          placeholder="AI chat coming soon…"
          disabled
          aria-disabled="true"
          aria-label="Chat input (not yet available)"
        />
        <button className="chat-send-btn" disabled aria-label="Send message (not available)" aria-disabled="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  );
}
