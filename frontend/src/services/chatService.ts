const AI_CORE_URL = import.meta.env.VITE_AI_CORE_URL || 'http://localhost:8000';

export interface ChatContext {
  user_location?: { lat: number; lng: number } | null;
  active_route?: unknown | null;
  map_center?: { lat: number; lng: number } | null;
}

export interface MapPin {
  lat: number;
  lng: number;
  label: string;
  pin_type: 'accessible' | 'ramp';
}

export interface ChatResponse {
  session_id: string;
  message: string;
  response_intent?: 'route' | 'accessibility' | 'general' | null;
  route_action?: {
    origin: { lat: number; lng: number; label?: string | null };
    destination: { lat: number; lng: number; label?: string | null };
  } | null;
  map_pins?: MapPin[] | null;
}

export async function sendChat(
  sessionId: string,
  message: string,
  context?: ChatContext,
): Promise<ChatResponse> {
  const response = await fetch(`${AI_CORE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message, context: context ?? null }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error ?? 'Something went wrong. Please try again.');
  }

  return data as ChatResponse;
}

export async function clearChatSession(sessionId: string): Promise<void> {
  await fetch(`${AI_CORE_URL}/session/${sessionId}`, { method: 'DELETE' }).catch(() => {});
}
