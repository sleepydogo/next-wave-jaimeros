import type { Alert, Call, CallLog, Trip, TripState } from "./types/dashboard";

const API_URL = (
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "")
).replace(/\/$/, "");

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
  cargando: "carga_habilitada",
  cerrado: "finalizado",
};

export async function getTrips(): Promise<Trip[]> {
  const rows = await request<Array<Record<string, unknown>>>("/ops/trips");
  return rows.map((row) => {
    const ping = row.last_ping as Record<string, number> | null;
    const portLat = Number(row.port_lat);
    const portLon = Number(row.port_lon);
    const hasPortPosition = Number.isFinite(portLat) && Number.isFinite(portLon);
    const hasTruckPosition = Boolean(
      ping && Number.isFinite(ping.lat) && Number.isFinite(ping.lon),
    );
    const truckPosition = hasTruckPosition ? { lat: ping!.lat, lng: ping!.lon } : undefined;
    const portPosition = hasPortPosition ? { lat: portLat, lng: portLon } : undefined;
    const routePositions = [truckPosition, portPosition].filter(
      (position): position is { lat: number; lng: number } => Boolean(position),
    );
    return {
      id: String(row.id),
      patente: String(row.container),
      conductor: String(row.driver_name),
      estado: stateMap[String(row.status)] ?? "en_ruta",
      ubicacion: String(row.port_name),
      order: String(row.order_id ?? row.id),
      phone: String(row.phone ?? row.driver_phone ?? "Sin teléfono"),
      destino: String(row.destination ?? row.port_name),
      eta: String(row.eta ?? "Sin ETA"),
      hace: ping ? "posición reciente" : "sin posición",
      velocidad: ping?.speed ?? 0,
      lat: ping?.lat,
      lon: ping?.lon,
      ruta: routePositions.length > 0 ? routePositions : undefined,
      eventos: [],
      calls: [],
    };
  });
}

export async function getAlerts(): Promise<Alert[]> {
  const rows = await request<Array<Record<string, unknown>>>("/ops/alerts");
  return rows.map((row) => {
    const ts = Number(row.ts);
    const time = Number.isFinite(ts) ? hora(ts) : "—";
    return {
      id: String(row.id),
      tripId: row.trip_id ? String(row.trip_id) : undefined,
      order: String(row.trip_id ?? "—"),
      patente: String(row.patente ?? row.container ?? "—"),
      conductor: String(row.driver_name ?? row.conductor ?? "—"),
      titulo: String(row.title ?? "Alerta operativa"),
      ubicacion: String(row.location ?? row.ubicacion ?? ""),
      tipo:
        row.severity === "alta"
          ? "emergencia"
          : row.severity === "baja"
            ? "resuelto"
            : "atencion",
      texto: String(row.body ?? row.text ?? ""),
      canales: String(row.channels ?? ""),
      ts,
      hora: time,
      hace: time,
    };
  });
}

/** Completa las alertas con los datos del viaje que el endpoint no repite. */
export function hydrateAlerts(alerts: Alert[], trips: Trip[]): Alert[] {
  const tripsById = new Map(trips.map((trip) => [trip.id, trip]));
  return alerts.map((alert) => {
    const trip = alert.tripId ? tripsById.get(alert.tripId) : undefined;
    if (!trip) return alert;
    return {
      ...alert,
      order: trip.order,
      patente: trip.patente,
      conductor: trip.conductor,
      ubicacion: alert.ubicacion || trip.ubicacion,
    };
  });
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


// ---- detalle de un viaje, con sus llamadas ----

const TITULOS: Record<string, string> = {
  arrival_check: "Confirmación de llegada",
  load_authorized: "Carga habilitada",
  emergency: "Atención requerida",
  prueba_local: "Prueba desde el navegador",
};

/** El backend guarda el transcript como texto plano "AGENTE: ...\nCONDUCTOR: ..." */
function parseTranscript(texto: string): { speaker: string; text: string }[] {
  if (!texto) return [];
  return texto
    .split("\n")
    .filter(Boolean)
    .map((linea) => {
      const i = linea.indexOf(":");
      if (i === -1) return { speaker: "Agente", text: linea.trim() };
      const quien = linea.slice(0, i).trim();
      return {
        speaker: quien === "AGENTE" ? "Agente" : "Conductor",
        text: linea.slice(i + 1).trim(),
      };
    });
}

function hora(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function mapCall(row: Record<string, unknown>, pos?: { lat: number; lng: number }): CallLog {
  const voice = (row.voice ?? {}) as Record<string, number>;
  const outcome = (row.outcome ?? {}) as Record<string, unknown>;
  const riesgo = Number(voice.risk ?? 0);
  const segundos = Number(row.duration_s ?? 0);
  return {
    id: String(row.id),
    time: hora(Number(row.ts)),
    duration: segundos
      ? `${String(Math.floor(segundos / 60)).padStart(2, "0")}:${String(
          Math.round(segundos % 60),
        ).padStart(2, "0")}`
      : "—",
    level: riesgo >= 0.6 ? "critical" : riesgo >= 0.3 ? "attention" : "normal",
    title: TITULOS[String(row.reason)] ?? String(row.reason),
    summary:
      (outcome.problem as string) ||
      (outcome.needs_human ? "Requiere seguimiento humano." : "Sin novedades."),
    position: pos,
    transcript: parseTranscript(String(row.transcript ?? "")),
    audioUrl: row.audio_url ? `${API_URL}${row.audio_url}` : undefined,
    costo: Number(row.cost_usd ?? 0),
    riesgoVoz: riesgo,
    // el epoch real, no la hora formateada: hace falta para cruzar la llamada
    // con la alerta que la origino
    ts: Number(row.ts),
  };
}

/** Un viaje con sus llamadas y su timeline, listo para la pantalla de detalle. */
export async function getTripDetail(tripId: string): Promise<{
  calls: CallLog[];
  eventos: { hora: string; texto: string; tipo?: "call" | "event" }[];
}> {
  const d = await request<{
    trip: Record<string, unknown>;
    pings: Array<Record<string, number>>;
    events: Array<Record<string, unknown>>;
    calls: Array<Record<string, unknown>>;
  }>(`/ops/trips/${tripId}`);

  const positionForCall = (callTs: number) => {
    const ping = (d.pings ?? []).reduce<Record<string, number> | undefined>((nearest, candidate) => {
      if (!nearest) return candidate;
      return Math.abs(candidate.ts - callTs) < Math.abs(nearest.ts - callTs) ? candidate : nearest;
    }, undefined);
    return ping ? { lat: ping.lat, lng: ping.lon } : undefined;
  };
  return {
    calls: (d.calls ?? []).map((c) => mapCall(c, positionForCall(Number(c.ts)))),
    eventos: (d.events ?? []).map((e) => ({
      hora: hora(Number(e.ts)),
      texto: String(e.type),
      tipo: String(e.type) === "call.finished" ? ("call" as const) : ("event" as const),
    })),
  };
}

/** Todos los viajes ya con sus llamadas cargadas. */
export async function getTripsConLlamadas(): Promise<Trip[]> {
  const trips = await getTrips();
  const detalles = await Promise.all(
    trips.map((t) => getTripDetail(t.id).catch(() => ({ calls: [], eventos: [] }))),
  );
  return trips.map((t, i) => ({ ...t, calls: detalles[i].calls, eventos: detalles[i].eventos }));
}
