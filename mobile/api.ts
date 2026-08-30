// El default apunta al tunel de ngrok, no a localhost: desde el telefono
// "localhost" es el propio telefono. Se puede pisar con EXPO_PUBLIC_API_URL,
// pero ojo que esa variable se inlinea al compilar y Metro la cachea, asi que
// hay que arrancar con `npx expo start --clear` para que tome un valor nuevo.
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ??
  "https://parchment-grafted-delouse.ngrok-free.dev";

export interface DriverTrip {
  id: string;
  driver_name?: string;
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
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      // sin esto, ngrok free devuelve su pagina de advertencia en HTML
      // en vez de la respuesta de la API
      "ngrok-skip-browser-warning": "true",
      ...(options?.headers ?? {}),
    },
  });
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
  // Los cuatro hitos que disparan una llamada del agente. Cada boton dispara
  // UNO solo: el backend publica el evento y el agente llama.
  triggers: () => request<Array<{ id: string; titulo: string }>>("/driver/triggers"),
  trigger: (tripId: string, hito: string) =>
    request<{ ok: boolean; hito: string; titulo: string; evento: string; event_id: string }>(
      `/driver/${tripId}/trigger/${hito}`,
      { method: "POST" },
    ),
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
