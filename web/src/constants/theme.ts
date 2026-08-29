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
  en_ruta: { label: "En ruta", color: COLOR.accent },
  en_puerto: { label: "En puerto", color: COLOR.warning },
  carga_habilitada: { label: "Carga habilitada", color: COLOR.success },
  emergencia: { label: "Emergencia", color: COLOR.critical },
};

export const ALERT_META: Record<AlertType, AlertMetaItem> = {
  emergencia: { color: COLOR.critical, icon: AlertTriangle },
  atencion: { color: COLOR.warning, icon: Bell },
  resuelto: { color: COLOR.success, icon: CheckCircle2 },
};
