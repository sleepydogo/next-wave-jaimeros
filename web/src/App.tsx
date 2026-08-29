import { useEffect, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";
import { ChevronRight, Phone, Play, RotateCcw } from "lucide-react";
import {
  APIProvider,
  AdvancedMarker,
  InfoWindow,
  Map,
  Pin,
  Polyline,
  useMap,
} from "@vis.gl/react-google-maps";
import { trips } from "./data/mockData";
import type { CallLog } from "./types/dashboard";
import "./App.css";
import "./route.css";
import "./fix.css";

const labels = {
  en_ruta: "En ruta",
  en_puerto: "En puerto",
  carga_habilitada: "Carga habilitada",
  emergencia: "Atención requerida",
};
function Header() {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">NW</span>NextWave Ops
      </div>
      <div className="live">
        <i />
        Monitoreo en vivo
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
      <button onClick={() => navigate("/")}>Pedidos</button>
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
  const navigate = useNavigate();
  return (
    <main className="page">
      <p className="eyebrow">Operación de hoy · 29 ago</p>
      <h1>Pedidos en movimiento</h1>
      <p className="sub">
        Seguimiento de cada entrega, su ruta y comunicaciones.
      </p>
      <section className="order-table" aria-label="Lista de pedidos">
        <div className="table-head">
          <span>Pedido / unidad</span>
          <span>Transportista</span>
          <span>Destino actual</span>
          <span>Llegada</span>
          <span />
        </div>
        {trips.map((t) => (
          <button
            className="order-row"
            key={t.id}
            onClick={() => navigate(`/pedidos/${t.id}`)}
          >
            <div>
              <div className="plate">{t.patente}</div>
              <small className="driver">{t.order}</small>
            </div>
            <div className="driver">
              {t.conductor}
              <small>{t.phone}</small>
            </div>
            <div className="destination">
              {t.ubicacion}
              <small>→ {t.destino}</small>
            </div>
            <div className="eta">{t.eta}</div>
            <span
              className={`status ${t.estado === "emergencia" ? "alert" : ""}`}
            >
              {labels[t.estado]}
            </span>
            <span className="open-link">
              Ver pedido <ChevronRight size={15} />
            </span>
          </button>
        ))}
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
    <section className="map-card border border-neutral-200 shadow-sm rounded-xl overflow-hidden bg-white">
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
              className="flex items-center gap-1.5 rounded-lg border border-neutral-300 bg-neutral-50 px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-100 transition-colors shadow-sm cursor-pointer"
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
                  ⚓ Terminal 3, Puerto La Plata
                </div>
                <Pin
                  background="#0d6b4d"
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
                  🚛 Camión AF 402 KL · En movimiento
                </div>
                <Pin
                  background="#0A5C8C"
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
                      className={`absolute -inset-3.5 rounded-full opacity-70 transition-all ${isAttention ? "bg-amber-400 animate-ping" : isCritical ? "bg-red-500 animate-ping" : "bg-teal-400 group-hover:animate-ping"}`}
                    />

                    {/* Rich Hover Tooltip */}
                    <div className="pointer-events-none absolute -top-14 z-40 opacity-0 transition-all duration-200 group-hover:opacity-100 group-hover:-translate-y-1">
                      <div className="flex flex-col gap-0.5 rounded-lg border border-neutral-800 bg-neutral-950/95 p-2.5 text-white shadow-2xl backdrop-blur-md min-w-[210px]">
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
                          📍 {c.ubicacion ?? "Ubicación en ruta"}
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
                              ? "#059669"
                              : "#0284C7"
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
                    <span className="shrink-0 text-emerald-700">📍</span>
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
                    className="mt-3 flex w-full items-center justify-between rounded-lg bg-[#0d6b4d] px-3 py-2 text-xs font-bold text-white shadow transition-all hover:bg-[#0a563e] hover:shadow-md cursor-pointer"
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
  const { tripId } = useParams();
  const trip = trips.find((t) => t.id === tripId);
  if (!trip) return <NotFound />;
  return (
    <main className="page">
      <Breadcrumb tripId={trip.id} order={trip.order} />
      <div className="detail-header">
        <p className="eyebrow">{trip.order}</p>
        <div className="order-title">
          <h1>{trip.patente}</h1>
          <span
            className={`status ${trip.estado === "emergencia" ? "alert" : ""}`}
          >
            {labels[trip.estado]}
          </span>
        </div>
        <p className="sub">
          {trip.ubicacion} · {trip.hace}
        </p>
      </div>
      <div className="detail-layout">
        <RouteMap calls={trip.calls} tripId={trip.id} />
        <aside className="side-column">
          <section className="info-card">
            <header>
              <h2>Transportista</h2>
              <Phone size={16} color="#0d6b4d" />
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
          <section className="timeline-card">
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
    <main className="page call-page">
      <Breadcrumb
        tripId={trip.id}
        order={trip.order}
        call={`Llamada ${call.time}`}
      />
      <p className="eyebrow">Registro de llamada · {call.time}</p>
      <h1>{call.title}</h1>
      <p className="sub">
        {trip.conductor} · {trip.phone} · Duración {call.duration}
      </p>
      <section className="call-log">
        <h2>Grabación y transcripción</h2>
        <div className="recording">
          <button className="play" aria-label="Reproducir llamada">
            <Play size={15} fill="currentColor" />
          </button>
          <div className="wave" />
          <span className="eta">{call.duration}</span>
        </div>
        <div className="transcript">
          {call.transcript.map((l, i) => (
            <p key={i}>
              <span className="speaker">{l.speaker}</span>
              {l.text}
            </p>
          ))}
        </div>
      </section>
      <section className="route-report">
        <header>
          <div>
            <p className="eyebrow">Contexto operativo</p>
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
    </main>
  );
}
export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Orders />} />
          <Route path="/pedidos/:tripId" element={<Detail />} />
          <Route
            path="/pedidos/:tripId/llamadas/:callId"
            element={<CallDetail />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
