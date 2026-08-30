export type TripState =
  | "en_camino"
  | "carga_habilitada"
  | "atencion"
  | "finalizado"
  | "en_ruta"
  | "en_puerto"
  | "emergencia";
export interface CallLog {
  id: string;
  time: string;
  duration: string;
  level: "normal" | "attention" | "critical";
  title: string;
  summary: string;
  ubicacion?: string;
  position?: { lat: number; lng: number };
  transcript: { speaker: string; text: string }[];
}
export interface TripEvent {
  hora: string;
  texto: string;
  tipo?: "call" | "event";
}
export interface Trip {
  id: string;
  order: string;
  patente: string;
  conductor: string;
  phone: string;
  estado: TripState;
  origen?: string;
  ubicacion: string;
  destino: string;
  hace: string;
  velocidad: number;
  eta: string;
  eventos: TripEvent[];
  calls: CallLog[];
  lat?: number;
  lon?: number;
  ruta?: { lat: number; lng: number }[];
}
export type AlertType = "emergencia" | "resuelto" | "atencion";
export type AlertSeverity = "critica" | "atencion" | "info" | "resuelta";

export interface Alert {
  id: string;
  tripId?: string;
  order: string;
  patente: string;
  conductor: string;
  tipo: AlertType;
  severidad?: AlertSeverity;
  titulo: string;
  texto: string;
  ubicacion: string;
  hora: string;
  hace?: string;
  estado?: "pendiente" | "en_gestion" | "resuelta";
}
export interface Call {
  id: string;
  conductor: string;
  patente: string;
  hora: string;
  resultado: string;
  duracion: string;
}
export interface CostData {
  hora: string;
  agente: number;
  humano: number;
}
export type NavKey = "viajes" | "alertas" | "llamadas" | "costos";
export interface NavOption {
  key: NavKey;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}
export interface StateMetaItem {
  label: string;
  color: string;
}
export interface AlertMetaItem {
  color: string;
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
}
