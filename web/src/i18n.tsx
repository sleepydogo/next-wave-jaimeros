import {
  createContext,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Locale = "en" | "es";

const STORAGE_KEY = "ops-locale";

// Spanish is the source language already used by the prototype. Keeping this
// dictionary separate means the visual redesign does not become coupled to the
// API or to the mock-data shape.
const english: Record<string, string> = {
  "Atención Requerida": "Action required",
  "Carga Habilitada": "Loading authorized",
  Finalizado: "Completed",
  "En Camino": "En route",
  Inicio: "Overview",
  Traslados: "Transfers",
  Pedidos: "Orders",
  Alertas: "Alerts",
  "Monitoreo en vivo": "Live monitoring",
  "Ir al inicio": "Go to overview",
  "Activar modo día": "Switch to light mode",
  "Activar modo noche": "Switch to dark mode",
  "Modo día": "Light mode",
  "Modo noche": "Dark mode",
  Noche: "Dark",
  Día: "Light",
  "Monitoreo de Voz y Flota": "Voice & fleet monitoring",
  "Gestión de Pedidos y Alertas en Ruta": "Order & route alert management",
  "Supervisión operativa centralizada: estado de viaje, ruta asignada y resolución prioritaria de incidentes.":
    "Centralized operations monitoring: trip status, assigned route, and prioritized incident response.",
  "Hay {count} viaje(s) con alerta prioritaria que requieren atención del monitorista":
    "{count} trip(s) have a priority alert requiring operator attention",
  "Ver alertas ({count})": "View alerts ({count})",
  Hay: "There are",
  "viaje(s) con alerta prioritaria que requieren atención del monitorista":
    " trip(s) with a priority alert requiring operator attention",
  "Ver alertas (": "View alerts (",
  "Total Pedidos": "Total orders",
  Atención: "Attention",
  "En camino": "En route",
  "Carga habilitada": "Loading authorized",
  Finalizados: "Completed",
  "Buscar por pedido #, patente, conductor u origen/destino...":
    "Search by order #, license plate, driver, or origin/destination...",
  Todos: "All",
  "Pedido / Unidad": "Order / vehicle",
  "Ruta Asignada (Origen ➔ Destino)": "Assigned route (origin ➔ destination)",
  "ETA Estimada": "Estimated ETA",
  "Estado / Alerta": "Status / alert",
  Acción: "Action",
  "Depósito Origen": "Origin depot",
  Detenido: "Stopped",
  Atender: "Handle",
  "Ver viaje": "View trip",
  "No se encontraron pedidos con ese criterio.": "No orders match that criteria.",
  "Limpiar filtros y buscar de nuevo": "Clear filters and search again",
  "Mostrando {visible} de {total} pedidos activos": "Showing {visible} of {total} active orders",
  Mostrando: "Showing",
  de: "of",
  "pedidos activos": "active orders",
  "Lista de pedidos": "Order list",
  "Monitoreo en vivo · Detección automática de alertas": "Live monitoring · Automatic alert detection",
  "Ruta recomendada y telemetría": "Recommended route & telemetry",
  "Haz clic en cualquier hito para enfocar la cámara y desplegar el registro exacto":
    "Click any milestone to focus the map and view the exact record",
  "Restablecer vista": "Reset view",
  "Hitos de la ruta": "Route milestones",
  "Llamada del agente": "Agent call",
  "Alerta de Atención": "Attention alert",
  "Registro Normal": "Normal record",
  Normal: "Normal",
  "Ubicación en ruta": "Location on route",
  "Ver log y transcripción completa": "View full log & transcript",
  "Camión en ruta": "Truck on route",
  "Puerto destino": "Destination port",
  "No encontramos este pedido": "We couldn't find this order",
  "El pedido que buscás no existe o ya no está disponible.":
    "The order you are looking for does not exist or is no longer available.",
  "Volver a pedidos": "Back to orders",
  Transportista: "Carrier",
  Destino: "Destination",
  "ETA estimada": "Estimated ETA",
  Velocidad: "Speed",
  "Actividad del pedido": "Order activity",
  "Registro de llamada · {time}": "Call record · {time}",
  "Grabación y transcripción": "Recording & transcript",
  "Sin grabación": "No recording",
  "No hay transcripción disponible.": "No transcript available.",
  "Contexto operativo": "Operational context",
  "Ruta y telemetría del pedido": "Order route & telemetry",
  "En ruta planificada": "On planned route",
  "Distancia planificada": "Planned distance",
  "24,1 km recorridos": "24.1 km covered",
  "Tiempo estimado": "Estimated time",
  "+ 8 min por congestión": "+ 8 min due to congestion",
  "Velocidad media": "Average speed",
  "Máxima: 78 km/h": "Maximum: 78 km/h",
  "Precisión GPS": "GPS accuracy",
  "Último ping 10:08:14": "Last ping 10:08:14",
  "Alerta · {time} hs": "Alert · {time}",
  "Qué se detectó": "What was detected",
  Severidad: "Severity",
  Alta: "High",
  Media: "Medium",
  Viaje: "Trip",
  Conductor: "Driver",
  "Notificado por": "Notified by",
  "Todavía no hay una llamada asociada a esta alerta.": "There is no call linked to this alert yet.",
  "Sin grabación disponible para esta llamada.": "No recording is available for this call.",
  "Sin transcripción.": "No transcript.",
  "Ver la llamada completa": "View full call",
  "Registro de Incidencias": "Incident log",
  "Actualizado en tiempo real": "Updated in real time",
  "Centro de Alertas Operativas": "Operations alert center",
  "Historial y estado de alertas detectadas en ruta por el agente de voz y monitoreo de telemetría.":
    "History and status of route alerts detected by the voice agent and telemetry monitoring.",
  "Total Alertas": "Total alerts",
  "Críticas / Emergencia": "Critical / emergency",
  "En Atención": "Needs attention",
  Resueltas: "Resolved",
  "Buscar alerta por título, pedido, patente o ubicación...":
    "Search alerts by title, order, license plate, or location...",
  Todas: "All",
  Críticas: "Critical",
  "Incidencia / Evento": "Incident / event",
  "Unidad / Conductor": "Vehicle / driver",
  Ubicación: "Location",
  Hora: "Time",
  Crítica: "Critical",
  Resuelta: "Resolved",
  "Ver pedido": "View order",
  "No se encontraron alertas para este filtro.": "No alerts match this filter.",
  "Mostrando {visible} de {total} alertas registradas": "Showing {visible} of {total} recorded alerts",
  "alertas registradas": "recorded alerts",
  "Lista de alertas": "Alert list",
  "Detección automática por agente de voz y GPS": "Automatic detection by voice agent and GPS",
  "· 29 ago 2026": "· Aug 29, 2026",
  "Tu navegador no puede reproducir el audio.": "Your browser cannot play this audio.",
  "Depósito Dock Sud": "Dock Sud depot",
  "Terminal 3, Puerto La Plata": "Terminal 3, La Plata Port",
  "Terminal 1, Puerto La Plata": "Terminal 1, La Plata Port",
  "Terminal 2, Puerto La Plata": "Terminal 2, La Plata Port",
  "Centro de distribución — La Plata": "Distribution center — La Plata",
  "actualizado hace 2 min": "updated 2 min ago",
  "· actualizado hace 2 min": "· updated 2 min ago",
  "Salida de depósito": "Left depot",
  "Llamada: retiro confirmado": "Call: pickup confirmed",
  "Llamada: demora por congestión": "Call: congestion delay",
  "Llamada: arribo a Terminal 3": "Call: arrival at Terminal 3",
  "Planta Zárate": "Zárate plant",
  "actualizado hace 40 s": "updated 40 sec ago",
  "· actualizado hace 40 s": "· updated 40 sec ago",
  Disponible: "Available",
  "Centro de distribución — Avellaneda": "Distribution center — Avellaneda",
  "actualizado hace 6 min": "updated 6 min ago",
  "· actualizado hace 6 min": "· updated 6 min ago",
  "Puerto habilita carga": "Port authorizes loading",
  "Parque Industrial Pilar": "Pilar industrial park",
  "En revisión": "Under review",
  "actualizado hace 1 min": "updated 1 min ago",
  "· actualizado hace 1 min": "· updated 1 min ago",
  "Parada en ruta detectada": "Stop detected on route",
  "finalizado hace 25 min": "completed 25 min ago",
  "· finalizado hace 25 min": "· completed 25 min ago",
  "Entregado (09:45)": "Delivered (09:45)",
  "Parada no programada en ruta": "Unscheduled stop on route",
  "Camión detenido en Ruta 6 km 12 por más de 8 minutos. Agente de voz inició llamada de verificación.":
    "Truck stopped on Route 6 km 12 for more than 8 minutes. Voice agent started a verification call.",
  "hace 3 min": "3 min ago",
  "Demora por congestión en acceso": "Congestion delay at access road",
  "Conductor reporta tránsito denso en Acceso Sudeste. ETA ajustada automáticamente a 10:20 hs.":
    "Driver reports heavy traffic on Acceso Sudeste. ETA automatically adjusted to 10:20.",
  "hace 45 min": "45 min ago",
  "Sin respuesta en llamada de proximidad": "No answer on proximity call",
  "Agente intentó comunicarse al ingresar a geocerca de proximidad a Puerto La Plata. Reintento en 5 min.":
    "Agent tried to contact the driver when entering the La Plata Port proximity geofence. Retry in 5 min.",
  "hace 20 min": "20 min ago",
  "Carga habilitada en puerto": "Loading authorized at port",
  "Puerto La Plata habilitó ventana de descarga en Terminal 1. Notificación enviada exitosamente.":
    "La Plata Port opened an unloading window at Terminal 1. Notification sent successfully.",
  "hace 1h 45m": "1h 45m ago",
  "Entrega completada": "Delivery completed",
  "Unidad finalizó la descarga y cerró la orden sin novedades.":
    "Vehicle completed unloading and closed the order with no incidents.",
  "hace 2h": "2h ago",
  "10:20 hs": "10:20",
  "11:05 hs": "11:05",
  "Confirmación de retiro": "Pickup confirmation",
  "Demora por congestión": "Congestion delay",
  "Arribo a Terminal 3": "Arrival at Terminal 3",
  "Marcelo confirma que retiró la unidad y sale hacia Terminal 3.":
    "Marcelo confirms he picked up the vehicle and is heading to Terminal 3.",
  "El conductor reporta tránsito intenso en el acceso. La ETA se actualiza a 10:20.":
    "The driver reports heavy traffic at the access road. ETA updates to 10:20.",
  "Se confirma llegada al punto de descarga y disponibilidad para ingresar.":
    "Arrival at the unloading point and availability to enter are confirmed.",
  "Hola Marcelo, ¿confirmás el retiro de la unidad 042?":
    "Hi Marcelo, can you confirm the pickup of unit 042?",
  "Sí, ya estoy saliendo. Estimo llegar al puerto en cuarenta minutos.":
    "Yes, I am leaving now. I estimate arriving at the port in forty minutes.",
  "Perfecto, te esperamos en Terminal 3. Buen viaje.": "Perfect, we will be waiting at Terminal 3. Safe trip.",
  "Vemos una demora sobre la ruta. ¿Todo en orden?": "We see a delay on the route. Is everything okay?",
  "Sí, hay congestión antes del acceso. Voy lento pero sigo avanzando.":
    "Yes, there is congestion before the access road. I am moving slowly but still progressing.",
  "Recibido. Actualizamos tu hora estimada de llegada.": "Received. We are updating your estimated arrival time.",
  "Marcelo, ¿ya estás en la terminal?": "Marcelo, are you already at the terminal?",
  "Sí, llegué al acceso de Terminal 3 y estoy esperando indicación.":
    "Yes, I reached Terminal 3 access and am waiting for instructions.",
  "Perfecto, registramos tu arribo.": "Perfect, we have logged your arrival.",
};

const Context = createContext<{ locale: Locale; setLocale: (locale: Locale) => void }>({
  locale: "en",
  setLocale: () => undefined,
});

function normalise(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

function sourceFor(value: string) {
  const compact = normalise(value);
  if (english[compact]) return compact;
  return Object.keys(english).find((source) => english[source] === compact) ?? compact;
}

function translated(value: string, locale: Locale) {
  const source = sourceFor(value);
  const target = locale === "en" ? english[source] ?? source : source;
  if (target === normalise(value)) return value;
  const prefix = value.match(/^\s*/)?.[0] ?? "";
  const suffix = value.match(/\s*$/)?.[0] ?? "";
  return `${prefix}${target}${suffix}`;
}

function translateElement(root: HTMLElement, locale: Locale) {
  const textWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  while (textWalker.nextNode()) nodes.push(textWalker.currentNode as Text);
  nodes.forEach((node) => {
    const parent = node.parentElement;
    if (!parent || ["SCRIPT", "STYLE"].includes(parent.tagName)) return;
    const next = translated(node.data, locale);
    if (next !== node.data) node.data = next;
  });

  root.querySelectorAll<HTMLElement>("[placeholder], [title], [aria-label]").forEach((element) => {
    (["placeholder", "title", "aria-label"] as const).forEach((attribute) => {
      const value = element.getAttribute(attribute);
      if (!value) return;
      const next = translated(value, locale);
      if (next !== value) element.setAttribute(attribute, next);
    });
  });
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved === "es" || saved === "en" ? saved : "en";
  });

  useLayoutEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, locale);
    document.documentElement.lang = locale;
    const root = document.querySelector<HTMLElement>("[data-i18n-root]");
    if (!root) return;

    const apply = () => translateElement(root, locale);
    apply();
    const observer = new MutationObserver(apply);
    observer.observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["placeholder", "title", "aria-label"],
    });
    return () => observer.disconnect();
  }, [locale]);

  const value = useMemo(() => ({ locale, setLocale }), [locale]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export const useLanguage = () => useContext(Context);

export function LanguageSelector() {
  const { locale, setLocale } = useLanguage();
  return (
    <div className="language-selector" role="group" aria-label="Language selector">
      <button type="button" aria-pressed={locale === "en"} onClick={() => setLocale("en")}>
        EN
      </button>
      <button type="button" aria-pressed={locale === "es"} onClick={() => setLocale("es")}>
        ES
      </button>
    </div>
  );
}
