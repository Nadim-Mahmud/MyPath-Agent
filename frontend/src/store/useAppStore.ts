import { create } from 'zustand';
import type { RouteResponse } from '../types/route';

export interface Preferences {
  maxIncline: number;
  avoidCobblestones: boolean;
  preferCovered: boolean;
}

export interface LocationPoint {
  lat: number;
  lng: number;
  label: string;
}

export interface FlyToTarget {
  lat: number;
  lng: number;
  zoom?: number;
}

interface AppState {
  route: RouteResponse | null;
  activeStepIndex: number;
  isLoading: boolean;
  error: string | null;
  darkMode: boolean;
  chatOpen: boolean;
  preferences: Preferences;
  origin: LocationPoint | null;
  destination: LocationPoint | null;
  flyTo: FlyToTarget | null;
  activeField: 'origin' | 'destination' | null;

  setRoute: (route: RouteResponse | null) => void;
  setActiveStep: (index: number) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  toggleDarkMode: () => void;
  toggleChat: () => void;
  setPreferences: (prefs: Partial<Preferences>) => void;
  setOrigin: (origin: LocationPoint | null) => void;
  setDestination: (destination: LocationPoint | null) => void;
  clearRoute: () => void;
  setFlyTo: (target: FlyToTarget | null) => void;
  setActiveField: (field: 'origin' | 'destination' | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  route: null,
  activeStepIndex: -1,
  isLoading: false,
  error: null,
  darkMode: false,
  chatOpen: false,
  preferences: {
    maxIncline: 8,
    avoidCobblestones: false,
    preferCovered: false,
  },
  origin: null,
  destination: null,
  flyTo: null,
  activeField: null,

  setRoute: (route) => set({ route, activeStepIndex: -1 }),
  setActiveStep: (index) => set({ activeStepIndex: index }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode })),
  toggleChat: () => set((state) => ({ chatOpen: !state.chatOpen })),
  setPreferences: (prefs) =>
    set((state) => ({ preferences: { ...state.preferences, ...prefs } })),
  setOrigin: (origin) => set({ origin }),
  setDestination: (destination) => set({ destination }),
  clearRoute: () =>
    set({
      route: null,
      activeStepIndex: -1,
      error: null,
      origin: null,
      destination: null,
      activeField: null,
    }),
  setFlyTo: (flyTo) => set({ flyTo }),
  setActiveField: (activeField) => set({ activeField }),
}));
