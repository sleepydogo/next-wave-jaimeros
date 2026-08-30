import { AlertTriangle, Bell, CheckCircle2 } from "lucide-react";
import type {
  TripState,
  AlertType,
  StateMetaItem,
  AlertMetaItem,
} from "../types/dashboard";

export const COLOR = {
  accent: "#0A5C8C",
  success: "#1E8E5A",
  warning: "#B87A0A",
  critical: "#C22E2E",
} as const;

export const STATE_META: Record<TripState, StateMetaItem> = {
  en_camino: { label: "En camino", color: "#10B981" },
  en_ruta: { label: "En camino", color: "#10B981" },
  carga_habilitada: { label: "Carga habilitada", color: "#0077FC" },
  en_puerto: { label: "Carga habilitada", color: "#0077FC" },
  atencion: { label: "Atención", color: "#F59E0B" },
  emergencia: { label: "Atención", color: "#EF4444" },
  finalizado: { label: "Finalizado", color: "#64748B" },
};

export const ALERT_META: Record<AlertType, AlertMetaItem> = {
  emergencia: { color: COLOR.critical, icon: AlertTriangle },
  atencion: { color: COLOR.warning, icon: Bell },
  resuelto: { color: COLOR.success, icon: CheckCircle2 },
};
