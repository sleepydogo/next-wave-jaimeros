import { Truck, Bell, Phone, DollarSign } from "lucide-react";
import type { NavOption, NavKey } from "../types/dashboard";

export const NAV: NavOption[] = [
  { key: "viajes", label: "Viajes", icon: Truck },
  { key: "alertas", label: "Alertas", icon: Bell },
  { key: "llamadas", label: "Llamadas", icon: Phone },
  { key: "costos", label: "Costos", icon: DollarSign },
];

export const SECTION_TITLES: Record<NavKey, string> = {
  viajes: "Viajes",
  alertas: "Alertas",
  llamadas: "Llamadas",
  costos: "Costos",
};
