export interface Coordinate {
  latitude: number;
  longitude: number;
  elevation: number;
}

export interface Distance {
  value: number;
  type: string;
  text: string;
}

export interface Duration {
  value: number;
  type: string;
  text: string;
}

export interface RoutePoint {
  start_location: Coordinate;
  end_location: Coordinate;
  points: Coordinate[];
  surface: string;
  distance: Distance;
  duration: Duration;
  maneuver: string;
  travel_mode: string | null;
  instructions: string | null;
  incline: number;
}

export interface RouteResponse {
  routes: {
    points: RoutePoint[];
  };
}
