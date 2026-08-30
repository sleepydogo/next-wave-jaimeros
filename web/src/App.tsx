import { useEffect, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bell,
  ChevronRight,
  Clock,
  Filter,
  MapPin,
  Package,
  Phone,
  Play,
  RotateCcw,
  Search,
  Gauge,
  Truck,
  X,
} from "lucide-react";
import {
  APIProvider,
  AdvancedMarker,
  InfoWindow,
  Map,
  Pin,
  Polyline,
  useMap,
} from "@vis.gl/react-google-maps";
import { DatosProvider, useDatos } from "./useDatos";
import { LanguageProvider, LanguageSelector } from "./i18n";
import { ThemeProvider, ThemeToggle } from "./theme";
import { OperationsHome } from "./components/dashboard/OperationsHome";
import type { CallLog, TripState } from "./types/dashboard";
import "./App.css";
import "./route.css";
import "./fix.css";



export function TripStatusBadge({ state }: { state: TripState }) {
  const isAtencion = state === "atencion" || state === "emergencia";
  const isCarga = state === "carga_habilitada" || state === "en_puerto";
  const isFinalizado = state === "finalizado";

  if (isAtencion) {
    return (
      <span className="ops-status ops-status--critical">
        <span className="relative flex h-2 w-2">
          <span className="relative inline-flex rounded-full h-2 w-2 bg-red-600" />
        </span>
        <span>Atención Requerida</span>
      </span>
    );
  }

  if (isCarga) {
    return (
      <span className="ops-status ops-status--accent">
        <span className="h-2 w-2 rounded-full bg-blue-600 shrink-0" />
        <span>Carga Habilitada</span>
      </span>
    );
  }

  if (isFinalizado) {
    return (
      <span className="ops-status ops-status--muted">
        <span className="h-2 w-2 rounded-full bg-slate-400 shrink-0" />
        <span>Finalizado</span>
      </span>
    );
  }

  return (
    <span className="ops-status ops-status--success">
      <span className="relative flex h-2 w-2">
        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600" />
      </span>
      <span>En Camino</span>
    </span>
  );
}

function Header() {
  const { alerts } = useDatos();
  const navigate = useNavigate();
  const location = useLocation();

  const isHome = location.pathname === "/";
  const isPedidos = location.pathname.startsWith("/pedidos");
  const isAlertas = location.pathname.startsWith("/alertas");
  const criticalCount = alerts.filter((alert) => alert.tipo === "emergencia").length;

  return (
    <header className="topbar">
      <div className="topbar__primary">
        <button
          type="button"
          onClick={() => navigate("/")}
          className="brand"
          aria-label="Ir al inicio"
        >
          <span className="brand-mark">21</span>
          <span className="brand-name">
            <span>21agents</span>
            <span className="brand-product">Ops</span>
          </span>
        </button>

        <nav className="primary-nav" aria-label="Navegación principal">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="primary-nav__item"
            aria-current={isHome ? "page" : undefined}
          >
            <Gauge size={15} />
            <span>Inicio</span>
          </button>

          <button
            type="button"
            onClick={() => navigate("/pedidos")}
            className="primary-nav__item"
            aria-current={isPedidos ? "page" : undefined}
          >
            <Package size={15} />
            <span>Traslados</span>
          </button>

          <button
            type="button"
            onClick={() => navigate("/alertas")}
            className="primary-nav__item primary-nav__item--alert"
            aria-current={isAlertas ? "page" : undefined}
          >
            <Bell size={15} />
            <span>Alertas</span>
            {criticalCount > 0 && (
              <span className="critical-count" aria-label={`${criticalCount} alertas críticas`}>
                {criticalCount}
              </span>
            )}
          </button>
        </nav>
      </div>

      <div className="topbar__utilities">
        <span className="live"><i aria-hidden="true" /><span>Monitoreo en vivo</span></span>
        <ThemeToggle />
        <LanguageSelector />
      </div>
    </header>
  );
}
function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="ops-app">
      <Header />
      {children}
    </div>
  );
}
function Breadcrumb({
  tripId,
  order,
  call,
}: {
  tripId: string;
  order: string;
  call?: string;
}) {
  const navigate = useNavigate();
  return (
    <nav className="breadcrumb" aria-label="Navegación">
      <button onClick={() => navigate("/pedidos")}>Traslados</button>
      <ChevronRight size={13} />
      {call ? (
        <>
          <button onClick={() => navigate(`/pedidos/${tripId}`)}>
            {order}
          </button>
          <ChevronRight size={13} />
          <span aria-current="page">{call}</span>
        </>
      ) : (
        <span aria-current="page">{order}</span>
      )}
    </nav>
  );
}
function Orders() {
  const { trips } = useDatos();
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("todos");

  // Priorizar viajes que requieren atención
  const sortedTrips = [...trips].sort((a, b) => {
    const aAlert = a.estado === "atencion" || a.estado === "emergencia" ? 0 : 1;
    const bAlert = b.estado === "atencion" || b.estado === "emergencia" ? 0 : 1;
    return aAlert - bAlert;
  });

  // Filtro de viajes
  const filteredTrips = sortedTrips.filter((t) => {
    if (statusFilter === "en_camino" && !(t.estado === "en_camino" || t.estado === "en_ruta")) return false;
    if (statusFilter === "carga_habilitada" && !(t.estado === "carga_habilitada" || t.estado === "en_puerto")) return false;
    if (statusFilter === "atencion" && !(t.estado === "atencion" || t.estado === "emergencia")) return false;
    if (statusFilter === "finalizado" && t.estado !== "finalizado") return false;

    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      t.order.toLowerCase().includes(term) ||
      t.patente.toLowerCase().includes(term) ||
      t.conductor.toLowerCase().includes(term) ||
      t.destino.toLowerCase().includes(term) ||
      (t.origen && t.origen.toLowerCase().includes(term))
    );
  });

  // Contadores KPI
  const totalCount = trips.length;
  const enCaminoCount = trips.filter((t) => t.estado === "en_camino" || t.estado === "en_ruta").length;
  const cargaCount = trips.filter((t) => t.estado === "carga_habilitada" || t.estado === "en_puerto").length;
  const atencionCount = trips.filter((t) => t.estado === "atencion" || t.estado === "emergencia").length;
  const finalizadoCount = trips.filter((t) => t.estado === "finalizado").length;

  return (
    <main className="page ops-workspace">
      <header className="ops-page-header">
        <div>
          <h1>
            Gestión de Pedidos y Alertas en Ruta
          </h1>
          <p>
            Supervisión operativa centralizada: estado de viaje, ruta asignada y resolución prioritaria de incidentes.
          </p>
        </div>
        <span className="ops-page-meta">5 unidades · actualización en vivo</span>
      </header>

      {/* Banner de alerta prioritaria si hay casos que requieren atención */}
      {atencionCount > 0 && (
        <div className="ops-priority-strip">
          <div>
            <AlertTriangle size={18} aria-hidden="true" />
            <span>Hay {atencionCount} viaje(s) con alerta prioritaria que requieren atención del monitorista</span>
          </div>
          <button
            onClick={() => setStatusFilter("atencion")}
            className="ops-button ops-button--primary ops-button--small"
          >
            <span>Ver alertas ({atencionCount})</span>
            <ChevronRight size={15} />
          </button>
        </div>
      )}

      {/* Tarjetas KPI Resumen */}
      <div className="ops-stat-rail" aria-label="Filtrar pedidos por estado">
        <button
          onClick={() => setStatusFilter("todos")}
          className={`ops-stat-filter ${statusFilter === "todos" ? "is-active" : ""}`}
        >
          <span>Total pedidos</span>
          <strong>{totalCount}</strong>
        </button>

        <button
          onClick={() => setStatusFilter("atencion")}
          className={`ops-stat-filter ops-stat-filter--critical ${statusFilter === "atencion" ? "is-active" : ""}`}
        >
          <span>Atención</span>
          <strong>{atencionCount}</strong>
        </button>

        <button
          onClick={() => setStatusFilter("en_camino")}
          className={`ops-stat-filter ${statusFilter === "en_camino" ? "is-active" : ""}`}
        >
          <span>En camino</span>
          <strong>{enCaminoCount}</strong>
        </button>

        <button
          onClick={() => setStatusFilter("carga_habilitada")}
          className={`ops-stat-filter ${statusFilter === "carga_habilitada" ? "is-active" : ""}`}
        >
          <span>Carga habilitada</span>
          <strong>{cargaCount}</strong>
        </button>

        <button
          onClick={() => setStatusFilter("finalizado")}
          className={`ops-stat-filter ${statusFilter === "finalizado" ? "is-active" : ""}`}
        >
          <span>Finalizados</span>
          <strong>{finalizadoCount}</strong>
        </button>
      </div>

      {/* Toolbar: Búsqueda y Filtros */}
      <div className="ops-toolbar">
        {/* Campo de búsqueda */}
        <div className="ops-search">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            type="text"
            placeholder="Buscar por pedido #, patente, conductor u origen/destino..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="ops-search__input"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="ops-search__clear"
              aria-label="Limpiar búsqueda"
            >
              <X size={15} />
            </button>
          )}
        </div>

        {/* Tabs de estado */}
        <div className="ops-tabs">
          {[
            { id: "todos", label: "Todos" },
            { id: "atencion", label: "Atención" },
            { id: "en_camino", label: "En camino" },
            { id: "carga_habilitada", label: "Carga habilitada" },
            { id: "finalizado", label: "Finalizado" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`ops-tab ${statusFilter === tab.id ? "is-active" : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tabla de Pedidos Refactorizada */}
      <section className="ops-table-surface" aria-label="Lista de pedidos">
        <div className="overflow-x-auto">
          <table className="ops-table min-w-[900px]">
            {/* Encabezados de Columna */}
            <thead>
              <tr className="ops-table-head">
                <th className="py-3.5 px-5 w-[220px]">
                  <div className="flex items-center gap-1.5">
                    <Package size={14} className="text-[var(--color-accent)]" />
                    <span>Pedido / Unidad</span>
                  </div>
                </th>
                <th className="py-3.5 px-5">
                  <div className="flex items-center gap-1.5">
                    <MapPin size={14} className="text-[var(--color-accent)]" />
                    <span>Ruta Asignada (Origen ➔ Destino)</span>
                  </div>
                </th>
                <th className="py-3.5 px-5 w-[140px]">
                  <div className="flex items-center gap-1.5">
                    <Clock size={14} className="text-[var(--color-accent)]" />
                    <span>ETA Estimada</span>
                  </div>
                </th>
                <th className="py-3.5 px-5 w-[220px]">
                  <div className="flex items-center gap-1.5">
                    <Activity size={14} className="text-[var(--color-accent)]" />
                    <span>Estado / Alerta</span>
                  </div>
                </th>
                <th className="py-3.5 px-5 w-[130px] text-right">
                  <span>Acción</span>
                </th>
              </tr>
            </thead>

            {/* Cuerpo de Tabla */}
            <tbody className="divide-y divide-neutral-200/70">
              {filteredTrips.length > 0 ? (
                filteredTrips.map((t) => {
                  const isAttention = t.estado === "atencion" || t.estado === "emergencia";
                  return (
                    <tr
                      key={t.id}
                      onClick={() => navigate(`/pedidos/${t.id}`)}
                      className={`ops-table-row group ${isAttention ? "is-critical" : ""}`}
                    >
                      {/* Col 1: Pedido / Unidad */}
                      <td className="py-4 px-5 align-middle">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200/80 tracking-wide">
                              {t.order}
                            </span>
                            <span className="text-sm font-extrabold text-neutral-900 group-hover:text-[var(--color-accent)] transition-colors">
                              {t.patente}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5 text-xs text-neutral-500 font-medium">
                            <Truck size={13} className="text-neutral-400 shrink-0" />
                            <span className="truncate">{t.conductor}</span>
                          </div>
                        </div>
                      </td>

                      {/* Col 2: Ruta Asignada (Origen -> Destino) */}
                      <td className="py-4 px-5 align-middle">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-bold text-neutral-700 bg-neutral-100 px-2 py-0.5 rounded border border-neutral-200/80">
                              {t.origen ?? "Depósito Origen"}
                            </span>
                            <ArrowRight size={14} className="text-[var(--color-accent)] shrink-0" />
                            <span className="text-xs font-extrabold bg-blue-50 px-2 py-0.5 rounded border border-blue-200/80 text-blue-950">
                              {t.destino}
                            </span>
                          </div>
                          <div className="text-[11px] text-neutral-500 font-medium flex items-center gap-1">
                            <MapPin size={12} className={isAttention ? "text-red-600 shrink-0" : "text-neutral-400 shrink-0"} />
                            <span className={isAttention ? "font-bold text-red-900 truncate" : "truncate"}>
                              {t.ubicacion}
                            </span>
                            <span className="text-neutral-400">· {t.hace}</span>
                          </div>
                        </div>
                      </td>

                      {/* Col 3: ETA Estimada */}
                      <td className="py-4 px-5 align-middle">
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-1.5 text-sm font-extrabold text-neutral-900 font-mono">
                            <Clock size={14} className="text-neutral-400" />
                            <span>{t.eta}</span>
                          </div>
                          <span className="text-[11px] font-medium text-neutral-500">
                            {t.velocidad > 0 ? `${t.velocidad} km/h` : "Detenido"}
                          </span>
                        </div>
                      </td>

                      {/* Col 4: Estado / Alerta de Viaje */}
                      <td className="py-4 px-5 align-middle">
                        <TripStatusBadge state={t.estado} />
                      </td>

                      {/* Col 5: CTA Para Ir */}
                      <td className="py-4 px-5 align-middle text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/pedidos/${t.id}`);
                          }}
                          className="ops-button ops-button--primary ops-button--small"
                        >
                          <span>{isAttention ? "Atender" : "Ver viaje"}</span>
                          <ChevronRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-neutral-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Filter size={28} className="text-neutral-300" />
                      <p className="text-sm font-semibold">No se encontraron pedidos con ese criterio.</p>
                      <button
                        onClick={() => {
                          setSearchTerm("");
                          setStatusFilter("todos");
                        }}
                        className="mt-2 text-xs font-bold text-[var(--color-accent)] hover:underline cursor-pointer"
                      >
                        Limpiar filtros y buscar de nuevo
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Footer de la tabla */}
        <div className="ops-table-footer">
          <span>Mostrando <strong>{filteredTrips.length}</strong> de <strong>{trips.length}</strong> pedidos activos</span>
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Monitoreo en vivo · Detección automática de alertas
          </span>
        </div>
      </section>
    </main>
  );
}

function MapCameraController({
  selectedPos,
  defaultCenter,
}: {
  selectedPos: { lat: number; lng: number } | null;
  defaultCenter: { lat: number; lng: number };
}) {
  const map = useMap();
  useEffect(() => {
    if (!map) return;
    if (selectedPos) {
      map.panTo(selectedPos);
      map.setZoom(14);
    } else {
      map.panTo(defaultCenter);
      map.setZoom(11);
    }
  }, [map, selectedPos, defaultCenter]);
  return null;
}

function RouteMap({ calls, tripId }: { calls: CallLog[]; tripId: string }) {
  const [selected, setSelected] = useState<number | null>(null);
  const navigate = useNavigate();
  const defaultCenter = { lat: -34.595, lng: -58.42 };
  const spots = [
    { lat: -34.61, lng: -58.43 },
    { lat: -34.59, lng: -58.4 },
    { lat: -34.575, lng: -58.366 },
  ];
  const destination = { lat: -34.5745, lng: -58.366 };
  const truckSpot = { lat: -34.62, lng: -58.48 };

  const selectedCall = selected !== null ? calls[selected] : null;
  const selectedPos =
    selectedCall?.position ??
    (selected !== null ? (spots[selected] ?? null) : null);

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
  const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || "DEMO_MAP_ID";

  return (
    <section className="map-card ops-panel">
      <header className="map-header flex items-center justify-between px-5 py-4 border-b border-neutral-200 bg-white">
        <div>
          <h2 className="text-base font-bold text-neutral-900">
            Ruta recomendada y telemetría
          </h2>
          <p className="text-xs text-neutral-500">
            Haz clic en cualquier hito para enfocar la cámara y desplegar el
            registro exacto
          </p>
        </div>
        <div className="flex items-center gap-3">
          {selected !== null ? (
            <button
              onClick={() => setSelected(null)}
              className="ops-button ops-button--secondary ops-button--small"
            >
              <RotateCcw size={13} />
              <span>Ver toda la ruta</span>
            </button>
          ) : (
            <span className="text-xs font-medium text-neutral-500 tabular-nums">
              24,8 km · 42 min
            </span>
          )}
        </div>
      </header>
      <div className="route-map relative h-[480px] w-full">
        <APIProvider apiKey={apiKey}>
          <Map
            mapId={mapId}
            defaultCenter={defaultCenter}
            defaultZoom={11}
            gestureHandling="greedy"
            disableDefaultUI
            style={{ height: "100%", width: "100%" }}
          >
            <MapCameraController
              selectedPos={selectedPos}
              defaultCenter={defaultCenter}
            />

            {/* Destination Marker */}
            <AdvancedMarker
              position={destination}
              title="Puerto destino (Terminal 3)"
            >
              <div className="group relative cursor-pointer flex flex-col items-center">
                <div className="pointer-events-none absolute -top-10 z-30 opacity-0 transition-opacity group-hover:opacity-100 whitespace-nowrap rounded-lg bg-neutral-900 px-2.5 py-1 text-xs font-medium text-white shadow-xl">
                  <MapPin size={12} /> Terminal 3, Puerto La Plata
                </div>
                <Pin
                  background="#0A5C8C"
                  borderColor="#fff"
                  glyphColor="#fff"
                />
              </div>
            </AdvancedMarker>

            {/* Truck Marker */}
            <AdvancedMarker
              position={truckSpot}
              title="Ubicación del camión (AF 402 KL)"
            >
              <div className="group relative cursor-pointer flex flex-col items-center">
                <div className="pointer-events-none absolute -top-10 z-30 opacity-0 transition-opacity group-hover:opacity-100 whitespace-nowrap rounded-lg bg-neutral-900 px-2.5 py-1 text-xs font-medium text-white shadow-xl">
                  <Truck size={12} /> Camión AF 402 KL · En movimiento
                </div>
                <Pin
                  background="#231F20"
                  borderColor="#fff"
                  glyphColor="#fff"
                />
              </div>
            </AdvancedMarker>

            {/* Call Markers with Pulse Aura & Hover Tooltips */}
            {calls.map((c, i) => {
              const pos = c.position ?? spots[i] ?? spots[spots.length - 1];
              const isSelected = selected === i;
              const isAttention = c.level === "attention";
              const isCritical = c.level === "critical";

              return (
                <AdvancedMarker
                  key={c.id}
                  position={pos}
                  title={`${c.time} - ${c.title}`}
                  onClick={() => setSelected(i)}
                >
                  <div className="group relative flex cursor-pointer flex-col items-center">
                    {/* Animated Pulse Ring */}
                    <div
                      className={`absolute -inset-2 rounded-full opacity-35 transition-opacity group-hover:opacity-70 ${isAttention ? "bg-amber-400" : isCritical ? "bg-red-500" : "bg-blue-400"}`}
                    />

                    {/* Rich Hover Tooltip */}
                    <div className="pointer-events-none absolute -top-14 z-40 opacity-0 transition-[opacity,transform] duration-200 group-hover:opacity-100 group-hover:-translate-y-1">
                      <div className="flex flex-col gap-0.5 rounded-lg border border-neutral-800 bg-neutral-950/95 p-2.5 text-white shadow-2xl min-w-[210px]">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                            {c.time} hs · {isAttention ? "Atención" : "Normal"}
                          </span>
                          <span className="text-[10px] font-medium text-neutral-400">
                            Clic para hacer zoom
                          </span>
                        </div>
                        <p className="text-xs font-bold text-neutral-100">
                          {c.title}
                        </p>
                        <p className="text-[11px] text-neutral-400 truncate">
                          <MapPin size={11} /> {c.ubicacion ?? "Ubicación en ruta"}
                        </p>
                      </div>
                    </div>

                    <Pin
                      background={
                        isCritical
                          ? "#C22E2E"
                          : isAttention
                            ? "#D97706"
                            : isSelected
                              ? "#0A5C8C"
                              : "#67ACFC"
                      }
                      borderColor="#fff"
                      glyphColor="#fff"
                    />
                  </div>
                </AdvancedMarker>
              );
            })}

            <Polyline
              path={[
                truckSpot,
                ...calls.map((c, i) => c.position ?? spots[i]),
                destination,
              ]}
              strokeColor="#0A5C8C"
              strokeOpacity={0.95}
              strokeWeight={5}
            />

            {/* InfoWindow anchored directly AT the exact pin location */}
            {selectedCall && selectedPos && (
              <InfoWindow
                position={selectedPos}
                pixelOffset={[0, -38]}
                onCloseClick={() => setSelected(null)}
              >
                <div className="p-2 min-w-[250px] max-w-[290px]">
                  <div className="flex items-center justify-between gap-2 pb-1 border-b border-neutral-100">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider ${selectedCall.level === "attention" ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900"}`}
                    >
                      {selectedCall.level === "attention"
                        ? "Alerta de Atención"
                        : "Registro Normal"}
                    </span>
                    <span className="text-xs font-mono font-bold text-neutral-600">
                      {selectedCall.time} hs
                    </span>
                  </div>

                  <h3 className="mt-2 text-sm font-bold text-neutral-900 leading-snug">
                    {selectedCall.title}
                  </h3>

                  <div className="mt-1 flex items-start gap-1 text-[11px] font-medium text-neutral-600">
                    <MapPin size={13} className="shrink-0 text-emerald-700" />
                    <span className="leading-tight">
                      {selectedCall.ubicacion ?? "Ubicación en ruta"}
                    </span>
                  </div>

                  <p className="mt-2 rounded-lg bg-neutral-50 p-2.5 text-xs text-neutral-700 leading-relaxed border border-neutral-100">
                    "{selectedCall.summary}"
                  </p>

                  <button
                    onClick={() =>
                      navigate(`/pedidos/${tripId}/llamadas/${selectedCall.id}`)
                    }
                    className="ops-button ops-button--primary ops-button--small mt-3 w-full justify-between"
                  >
                    <span>Ver log y transcripción completa</span>
                    <ChevronRight size={14} />
                  </button>
                </div>
              </InfoWindow>
            )}
          </Map>
        </APIProvider>
      </div>
      <footer className="legend flex items-center justify-between border-t border-neutral-200 bg-neutral-50 px-5 py-3 text-xs text-neutral-600">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <i className="line" />
            Ruta planificada
          </span>
          <span className="flex items-center gap-1.5">
            <i />
            Pines de llamadas e hitos
          </span>
        </div>
        <span className="text-[11px] font-medium text-neutral-500">
          Pines interactivos con zoom automático y detalle exacto
        </span>
      </footer>
    </section>
  );
}

function NotFound() {
  return (
    <main className="page">
      <h1>No encontramos este pedido</h1>
      <p className="sub">
        Es posible que haya sido eliminado o que el enlace sea incorrecto.
      </p>
    </main>
  );
}
function Detail() {
  const { trips } = useDatos();
  const { tripId } = useParams();
  const trip = trips.find((t) => t.id === tripId);
  if (!trip) return <NotFound />;
  return (
    <main className="page ops-workspace ops-workspace--detail">
      <Breadcrumb tripId={trip.id} order={trip.order} />
      <div className="detail-header">
        <div className="ops-record-heading">
          <div>
            <h1>{trip.patente}</h1>
            <p className="sub">
              {trip.order} · {trip.ubicacion} · {trip.hace}
            </p>
          </div>
          <TripStatusBadge state={trip.estado} />
        </div>
      </div>
      <div className="detail-layout">
        <RouteMap calls={trip.calls} tripId={trip.id} />
        <aside className="side-column">
          <section className="info-card ops-panel">
            <header>
              <h2>Transportista</h2>
              <Phone size={16} color="var(--color-accent)" />
            </header>
            <div className="contact">
              <div className="avatar">
                {trip.conductor
                  .split(" ")
                  .map((x) => x[0])
                  .join("")}
              </div>
              <div>
                <strong>{trip.conductor}</strong>
                <span>{trip.phone}</span>
              </div>
            </div>
            <div className="details">
              <div className="detail-item">
                <label>Destino</label>
                <p>{trip.destino}</p>
              </div>
              <div className="detail-item">
                <label>ETA estimada</label>
                <p>{trip.eta}</p>
              </div>
              <div className="detail-item">
                <label>Velocidad</label>
                <p>{trip.velocidad ? `${trip.velocidad} km/h` : "Detenido"}</p>
              </div>
            </div>
          </section>
          <section className="timeline-card ops-panel">
            <header>
              <h2>Actividad del pedido</h2>
            </header>
            <div className="timeline">
              {trip.eventos.map((e, i) => (
                <div className={`event ${e.tipo ?? ""}`} key={i}>
                  <time>{e.hora}</time>
                  <p>{e.texto}</p>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </main>
  );
}
function CallDetail() {
  const { trips } = useDatos();
  const { tripId, callId } = useParams();
  const trip = trips.find((t) => t.id === tripId);
  const call = trip?.calls.find((c) => c.id === callId);
  if (!trip || !call) return <NotFound />;
  const route = [
    ["08:12", "Depósito Dock Sud", "Salida confirmada · odómetro 18.442 km"],
    ["08:42", "Av. 9 de Julio", "Llamada 1 · retiro confirmado"],
    ["09:28", "Acceso Sudeste", "Llamada 2 · congestión detectada"],
    ["10:06", "Terminal 3", "Llamada 3 · arribo y espera de acceso"],
  ];
  return (
    <main className="page call-page ops-workspace ops-record-page">
      <Breadcrumb
        tripId={trip.id}
        order={trip.order}
        call={`Llamada ${call.time}`}
      />
      <header className="ops-record-header">
        <span className="ops-page-meta">Registro de llamada · {call.time}</span>
        <h1>{call.title}</h1>
        <p>{trip.conductor} · {trip.phone} · Duración {call.duration}</p>
      </header>
      <div className="ops-record-layout">
      <section className="call-log ops-panel">
        <h2>Grabación y transcripción</h2>
        {call.audioUrl ? (
          <div className="recording">
            {/* el wav lo graba el propio agente durante la llamada */}
            <audio controls preload="metadata" src={call.audioUrl} style={{ width: "100%" }}>
              Tu navegador no puede reproducir el audio.
            </audio>
          </div>
        ) : (
          <div className="recording">
            <button className="play" aria-label="Reproducir llamada" disabled>
              <Play size={15} fill="currentColor" />
            </button>
            <div className="wave" />
            <span className="eta">Sin grabación</span>
          </div>
        )}
        {call.riesgoVoz !== undefined && (
          <p className="sub" style={{ marginTop: 8 }}>
            Riesgo de voz {call.riesgoVoz}
            {call.costo ? ` · costo USD ${call.costo.toFixed(4)}` : ""}
          </p>
        )}
        <div className="transcript">
          {call.transcript.map((l, i) => (
            <p key={i}>
              <span className="speaker">{l.speaker}</span>
              {l.text}
            </p>
          ))}
        </div>
      </section>
      <section className="route-report ops-panel">
        <header>
          <div>
            <h2>Ruta y telemetría del pedido</h2>
          </div>
          <span className="status">En ruta planificada</span>
        </header>
        <div className="route-metrics">
          <div>
            <small>Distancia planificada</small>
            <strong>24,8 km</strong>
            <span>24,1 km recorridos</span>
          </div>
          <div>
            <small>Tiempo estimado</small>
            <strong>42 min</strong>
            <span>+ 8 min por congestión</span>
          </div>
          <div>
            <small>Velocidad media</small>
            <strong>54 km/h</strong>
            <span>Máxima: 78 km/h</span>
          </div>
          <div>
            <small>Precisión GPS</small>
            <strong>± 6 m</strong>
            <span>Último ping 10:08:14</span>
          </div>
        </div>
        <div className="route-log">
          <h3>Hitos de la ruta</h3>
          {route.map(([time, place, detail]) => (
            <div className="route-event" key={time}>
              <time>{time}</time>
              <div>
                <strong>{place}</strong>
                <span>{detail}</span>
              </div>
            </div>
          ))}
        </div>
        <footer>
          Ruta sugerida: Autopista Buenos Aires–La Plata · Fuente: GPS de
          unidad, geocercas y registro de llamadas.
        </footer>
      </section>
      </div>
    </main>
  );
}
/** Detalle de una alerta: que paso, y la llamada que el agente hizo por eso.
 *
 * La alerta y la llamada no estan unidas por una FK: se vinculan por viaje y
 * cercania en el tiempo, que es como ocurren (el agente llama al detectar el
 * evento). Tomamos la llamada mas cercana dentro de una ventana de 2 minutos.
 */
function AlertDetail() {
  const { trips, alerts } = useDatos();
  const { alertId } = useParams();
  const navigate = useNavigate();

  const alerta = alerts.find((a) => a.id === alertId);
  if (!alerta) return <NotFound />;

  const trip = trips.find((t) => t.id === alerta.tripId);
  // La llamada arranca justo despues de la alerta (el agente reacciona al
  // evento), asi que buscamos la mas cercana en el tiempo dentro de 5 minutos.
  const cerca = (c: CallLog) => Math.abs((c.ts ?? 0) - (alerta.ts ?? 0));
  const llamada = trip?.calls
    .filter((c) => c.ts && alerta.ts && cerca(c) < 300)
    .sort((a, b) => cerca(a) - cerca(b))[0];

  const critica = alerta.tipo === "emergencia";

  return (
    <main className="page call-page ops-workspace ops-record-page">
      {trip && <Breadcrumb tripId={trip.id} order={trip.order} call={`Alerta ${alerta.hora}`} />}
      <header className="ops-record-header">
        <span className="ops-page-meta">Alerta · {alerta.hora} hs</span>
        <h1>{alerta.titulo}</h1>
        <p>{alerta.texto}</p>
      </header>

      <div className="ops-record-layout ops-record-layout--alerts">
      <section className="call-log ops-panel">
        <h2>Qué se detectó</h2>
        <div className="transcript">
          <p><span className="speaker">Severidad</span>{critica ? "Alta" : "Media"}</p>
          <p><span className="speaker">Viaje</span>{alerta.tripId ?? "—"}</p>
          <p><span className="speaker">Conductor</span>{trip?.conductor ?? alerta.conductor}</p>
          {alerta.canales && (
            <p><span className="speaker">Notificado por</span>{alerta.canales}</p>
          )}
        </div>
      </section>

      <section className="call-log ops-panel">
        <h2>Llamada del agente</h2>
        {!llamada ? (
          <p className="sub">
            Todavía no hay una llamada asociada a esta alerta.
          </p>
        ) : (
          <>
            {llamada.audioUrl ? (
              <div className="recording">
                <audio controls preload="metadata" src={llamada.audioUrl} style={{ width: "100%" }}>
                  Tu navegador no puede reproducir el audio.
                </audio>
              </div>
            ) : (
              <p className="sub">Sin grabación disponible para esta llamada.</p>
            )}
            <p className="sub" style={{ marginTop: 8 }}>
              {llamada.title} · duración {llamada.duration}
              {llamada.riesgoVoz !== undefined ? ` · riesgo de voz ${llamada.riesgoVoz}` : ""}
              {llamada.costo ? ` · USD ${llamada.costo.toFixed(4)}` : ""}
            </p>
            <div className="transcript">
              {llamada.transcript.length === 0 ? (
                <p>Sin transcripción.</p>
              ) : (
                llamada.transcript.map((l, i) => (
                  <p key={i}>
                    <span className="speaker">{l.speaker}</span>
                    {l.text}
                  </p>
                ))
              )}
            </div>
            {trip && (
              <button
                className="ops-button ops-button--primary ops-button--small"
                onClick={() => navigate(`/pedidos/${trip.id}/llamadas/${llamada.id}`)}
              >
                <span>Ver la llamada completa</span>
                <ChevronRight size={15} />
              </button>
            )}
          </>
        )}
      </section>
      </div>
    </main>
  );
}

function AlertsScreen() {
  const { alerts } = useDatos();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [searchTerm, setSearchTerm] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>(() =>
    searchParams.get("severity") === "critical" ? "criticas" : "todas",
  );

  // Ordenar: Alertas de emergencia/atención primero
  const sortedAlerts = [...alerts].sort((a, b) => {
    const aOrder = a.tipo === "emergencia" ? 0 : a.tipo === "atencion" ? 1 : 2;
    const bOrder = b.tipo === "emergencia" ? 0 : b.tipo === "atencion" ? 1 : 2;
    return aOrder - bOrder;
  });

  const filteredAlerts = sortedAlerts.filter((a) => {
    if (severityFilter === "criticas" && a.tipo !== "emergencia") return false;
    if (severityFilter === "atencion" && a.tipo !== "atencion") return false;
    if (severityFilter === "resueltas" && a.tipo !== "resuelto") return false;

    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      a.titulo.toLowerCase().includes(term) ||
      a.texto.toLowerCase().includes(term) ||
      a.order.toLowerCase().includes(term) ||
      a.patente.toLowerCase().includes(term) ||
      a.conductor.toLowerCase().includes(term) ||
      a.ubicacion.toLowerCase().includes(term)
    );
  });

  const totalCount = alerts.length;
  const criticalCount = alerts.filter((a) => a.tipo === "emergencia").length;
  const atencionCount = alerts.filter((a) => a.tipo === "atencion").length;
  const resueltasCount = alerts.filter((a) => a.tipo === "resuelto").length;

  return (
    <main className="page ops-workspace">
      <header className="ops-page-header">
        <div>
          <h1>
            Centro de Alertas Operativas
          </h1>
          <p>
            Historial y estado de alertas detectadas en ruta por el agente de voz y monitoreo de telemetría.
          </p>
        </div>
        <span className="ops-page-meta">Prioridad por impacto · actualización en vivo</span>
      </header>

      {/* Tarjetas KPI Resumen */}
      <div className="ops-stat-rail ops-stat-rail--four" aria-label="Filtrar alertas por severidad">
        <button
          onClick={() => setSeverityFilter("todas")}
          className={`ops-stat-filter ${severityFilter === "todas" ? "is-active" : ""}`}
        >
          <span>Total alertas</span>
          <strong>{totalCount}</strong>
        </button>

        <button
          onClick={() => setSeverityFilter("criticas")}
          className={`ops-stat-filter ops-stat-filter--critical ${severityFilter === "criticas" ? "is-active" : ""}`}
        >
          <span>Críticas / emergencia</span>
          <strong>{criticalCount}</strong>
        </button>

        <button
          onClick={() => setSeverityFilter("atencion")}
          className={`ops-stat-filter ops-stat-filter--warning ${severityFilter === "atencion" ? "is-active" : ""}`}
        >
          <span>En atención</span>
          <strong>{atencionCount}</strong>
        </button>

        <button
          onClick={() => setSeverityFilter("resueltas")}
          className={`ops-stat-filter ${severityFilter === "resueltas" ? "is-active" : ""}`}
        >
          <span>Resueltas</span>
          <strong>{resueltasCount}</strong>
        </button>
      </div>

      {/* Toolbar: Búsqueda y Filtros */}
      <div className="ops-toolbar">
        <div className="ops-search">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            type="text"
            placeholder="Buscar alerta por título, pedido, patente o ubicación..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="ops-search__input"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="ops-search__clear"
              aria-label="Limpiar búsqueda"
            >
              <X size={15} />
            </button>
          )}
        </div>

        <div className="ops-tabs">
          {[
            { id: "todas", label: "Todas" },
            { id: "criticas", label: "Críticas" },
            { id: "atencion", label: "Atención" },
            { id: "resueltas", label: "Resueltas" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSeverityFilter(tab.id)}
              className={`ops-tab ${severityFilter === tab.id ? "is-active" : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tabla de Alertas */}
      <section className="ops-table-surface" aria-label="Lista de alertas">
        <div className="overflow-x-auto">
          <table className="ops-table min-w-[900px]">
            <thead>
              <tr className="ops-table-head">
                <th className="py-3.5 px-5">
                  <div className="flex items-center gap-1.5">
                    <AlertTriangle size={14} className="text-[var(--color-accent)]" />
                    <span>Incidencia / Evento</span>
                  </div>
                </th>
                <th className="py-3.5 px-5 w-[200px]">
                  <div className="flex items-center gap-1.5">
                    <Truck size={14} className="text-[var(--color-accent)]" />
                    <span>Unidad / Conductor</span>
                  </div>
                </th>
                <th className="py-3.5 px-5 w-[220px]">
                  <div className="flex items-center gap-1.5">
                    <MapPin size={14} className="text-[var(--color-accent)]" />
                    <span>Ubicación</span>
                  </div>
                </th>
                <th className="py-3.5 px-5 w-[160px]">
                  <div className="flex items-center gap-1.5">
                    <Activity size={14} className="text-[var(--color-accent)]" />
                    <span>Severidad</span>
                  </div>
                </th>
                <th className="py-3.5 px-5 w-[100px]">
                  <div className="flex items-center gap-1.5">
                    <Clock size={14} className="text-[var(--color-accent)]" />
                    <span>Hora</span>
                  </div>
                </th>
                <th className="py-3.5 px-5 w-[130px] text-right">
                  <span>Acción</span>
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-neutral-200/70">
              {filteredAlerts.length > 0 ? (
                filteredAlerts.map((a) => {
                  const isCritical = a.tipo === "emergencia";
                  const isAtencion = a.tipo === "atencion";
                  return (
                    <tr
                      key={a.id}
                      onClick={() => a.tripId && navigate(`/pedidos/${a.tripId}`)}
                      className={`ops-table-row group ${isCritical ? "is-critical" : isAtencion ? "is-warning" : ""}`}
                    >
                      {/* Incidencia / Detalle */}
                      <td className="py-4 px-5 align-middle">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2">
                            <span className="font-extrabold text-sm text-neutral-900 group-hover:text-[var(--color-accent)] transition-colors">
                              {a.titulo}
                            </span>
                            <span className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200/80">
                              {a.order}
                            </span>
                          </div>
                          <p className="text-xs text-neutral-600 line-clamp-2">{a.texto}</p>
                        </div>
                      </td>

                      {/* Conductor / Unidad */}
                      <td className="py-4 px-5 align-middle">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-sm font-extrabold text-neutral-900">{a.patente}</span>
                          <span className="text-xs text-neutral-500 font-medium">{a.conductor}</span>
                        </div>
                      </td>

                      {/* Ubicación */}
                      <td className="py-4 px-5 align-middle">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-xs font-semibold text-neutral-800 flex items-center gap-1">
                            <MapPin size={12} className="shrink-0 text-neutral-400" /> {a.ubicacion}
                          </span>
                          {a.hace && <span className="text-[11px] text-neutral-500">{a.hace}</span>}
                        </div>
                      </td>

                      {/* Severidad */}
                      <td className="py-4 px-5 align-middle">
                        {isCritical ? (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-full bg-red-50 text-red-700 border border-red-200 shadow-2xs">
                            <span className="relative flex h-2 w-2">
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-600" />
                            </span>
                            <span>Crítica</span>
                          </span>
                        ) : isAtencion ? (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-full bg-amber-50 text-amber-800 border border-amber-200 shadow-2xs">
                            <span className="h-2 w-2 rounded-full bg-amber-500 shrink-0" />
                            <span>Atención</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs">
                            <span className="h-2 w-2 rounded-full bg-emerald-600 shrink-0" />
                            <span>Resuelta</span>
                          </span>
                        )}
                      </td>

                      {/* Hora */}
                      <td className="py-4 px-5 align-middle">
                        <span className="font-mono text-xs font-bold text-neutral-800">{a.hora} hs</span>
                      </td>

                      {/* CTA */}
                      <td className="py-4 px-5 align-middle text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/alertas/${a.id}`);
                          }}
                          className="ops-button ops-button--primary ops-button--small"
                        >
                          <span>{isCritical ? "Atender" : "Ver pedido"}</span>
                          <ChevronRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-neutral-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Filter size={28} className="text-neutral-300" />
                      <p className="text-sm font-semibold">No se encontraron alertas para este filtro.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="ops-table-footer">
          <span>Mostrando <strong>{filteredAlerts.length}</strong> de <strong>{alerts.length}</strong> alertas registradas</span>
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Detección automática por agente de voz y GPS
          </span>
        </div>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <BrowserRouter>
          <DatosProvider>
            <div data-i18n-root>
              <Layout>
                <Routes>
                  <Route path="/" element={<OperationsHome />} />
                  <Route path="/pedidos" element={<Orders />} />
                  <Route path="/alertas" element={<AlertsScreen />} />
                  <Route path="/alertas/:alertId" element={<AlertDetail />} />
                  <Route path="/pedidos/:tripId" element={<Detail />} />
                  <Route path="/pedidos/:tripId/llamadas/:callId" element={<CallDetail />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            </div>
          </DatosProvider>
        </BrowserRouter>
      </LanguageProvider>
    </ThemeProvider>
  );
}
