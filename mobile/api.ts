const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export interface DriverTrip {
  id: string;
  container: string;
  port_name: string;
  status: string;
  driver_id: string;
  port_lat: number;
  port_lon: number;
}

export interface DriverTripResponse {
  trip: DriverTrip | null;
  calls: Array<{ id: string; reason: string; status: string; ts: number }>;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok)
    throw new Error(`No se pudo conectar con el backend (${response.status})`);
  return response.json() as Promise<T>;
}

export const driverApi = {
  health: () => request<{ ok: boolean }>("/health"),
  trip: (driverId: string) =>
    request<DriverTripResponse>(`/driver/${driverId}/trip`),
  ack: (tripId: string) =>
    request<{ ok: boolean }>(`/driver/${tripId}/ack`, { method: "POST" }),
  ping: (payload: {
    trip_id: string;
    lat: number;
    lon: number;
    speed: number;
  }) =>
    request<{ ok: boolean; status: string }>("/driver/ping", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
};
