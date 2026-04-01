import axios from 'axios';
import type { RouteResponse } from '../types/route';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080',
  headers: {
    Authorization: `Bearer ${import.meta.env.VITE_API_KEY}`,
  },
});

export async function fetchRoute(
  srcLat: number,
  srcLon: number,
  destLat: number,
  destLon: number
): Promise<RouteResponse> {
  try {
    const response = await apiClient.get<RouteResponse>('/route/getSingleRoute', {
      params: { srcLat, srcLon, destLat, destLon },
    });
    return response.data;
  } catch (err) {
    if (axios.isAxiosError(err)) {
      if (!err.response) {
        throw new Error(
          'Cannot reach the routing server. Please check your connection or try again later.'
        );
      }
      if (err.response.status === 401) {
        throw new Error('Authentication failed. Invalid API key.');
      }
      if (err.response.status === 404) {
        throw new Error(
          'No accessible route found between these two locations. Try different start or end points.'
        );
      }
      throw new Error(`Routing server error (${err.response.status}). Please try again.`);
    }
    throw new Error('An unexpected error occurred. Please try again.');
  }
}
