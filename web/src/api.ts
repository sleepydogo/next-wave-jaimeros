import type { Alert, Call, Trip, TripState } from "./types/dashboard";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface Metrics {
  costo_agente_usd: number;
  costo_humano_equivalente_usd: number;
  ahorro_usd: number;
  trips_activos: number;
  llamadas: number;
  alertas: number;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) throw new Error(`Backend error ${response.status}`);
  return response.json() as Promise<T>;
}

export const checkApiHealth = () => request<{ ok: boolean }>("/health");

const stateMap: Record<string, TripState> = {
  en_ruta: "en_ruta",
  en_puerto: "en_puerto",
  esperando_puerto: "en_puerto",
  habilitado: "carga_habilitada",
  cerrado: "carga_habilitada",
};

export async function getTrips(): Promise<Trip[]> {
  const rows = await request<Array<Record<string, unknown>>>("/ops/trips");
  return rows.map((row) => {
    const ping = row.last_ping as Record<string, number> | null;
    return {
      id: String(row.id),
      patente: String(row.container),
      conductor: String(row.driver_name),
      estado: stateMap[String(row.status)] ?? "en_ruta",
      ubicacion: String(row.port_name),
      order: String(row.order_id ?? row.id),
      phone: String(row.driver_phone ?? "Sin teléfono"),
      destino: String(row.destination ?? row.port_name),
      eta: String(row.eta ?? "Sin ETA"),
      hace: ping ? "posición reciente" : "sin posición",
      velocidad: ping?.speed ?? 0,
      lat: ping?.lat,
      lon: ping?.lon,
      eventos: [],
      calls: [],
    };
  });
}

export async function getAlerts(): Promise<Alert[]> {
  const rows = await request<Array<Record<string, unknown>>>("/ops/alerts");
  return rows.map((row) => ({
    id: String(row.id),
    tipo:
      row.severity === "alta"
        ? "emergencia"
        : row.severity === "baja"
          ? "resuelto"
          : "atencion",
    texto: String(row.text ?? row.message ?? row.event ?? "Alerta operativa"),
    hora: new Date(Number(row.ts) * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
  }));
}

export async function getCalls(): Promise<Call[]> {
  const rows = await request<Array<Record<string, unknown>>>("/ops/calls");
  return rows.map((row) => ({
    id: String(row.id),
    conductor: String(row.driver_name ?? "Conductor"),
    patente: String(row.trip_id ?? ""),
    hora: new Date(Number(row.ts) * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
    resultado: row.status === "done" ? "Contestó" : "No contestó",
    duracion: row.duration_s ? `${Math.round(Number(row.duration_s))}s` : "—",
  }));
}

export const getMetrics = () => request<Metrics>("/ops/metrics");
export const portReady = (tripId: string) =>
  request<{ ok: boolean }>(`/ops/trips/${tripId}/port-ready`, {
    method: "POST",
  });
