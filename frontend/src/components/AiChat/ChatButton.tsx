import './AiChat.css';
import { useAppStore } from '../../store/useAppStore';

export default function ChatButton() {
  const { toggleChat, chatOpen } = useAppStore();

  return (
    <button
      className="chat-fab"
      onClick={toggleChat}
      aria-label={chatOpen ? 'Close AI chat' : 'Open AI chat'}
      aria-expanded={chatOpen}
    >
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        {/* Wheelchair icon */}
        <circle cx="12" cy="4" r="1.5" fill="currentColor" stroke="none"/>
        <path d="M12 6v5l3 3" strokeLinecap="round"/>
        <path d="M9 11H7l-2 6h10l-1-3" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="8" cy="19" r="2"/>
        <circle cx="15" cy="19" r="2"/>
        <path d="M17 14l2-1" strokeLinecap="round"/>
        {/* AI chat bubble overlay */}
        <path d="M20 2H14a1 1 0 0 0-1 1v3a1 1 0 0 0 1 1h1l1 2 1-2h3a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1z" fill="white" stroke="none" opacity="0.9"/>
        <text x="15" y="6.5" fontSize="4" fill="#1A56DB" fontWeight="bold" textAnchor="middle">AI</text>
      </svg>
    </button>
  );
}
