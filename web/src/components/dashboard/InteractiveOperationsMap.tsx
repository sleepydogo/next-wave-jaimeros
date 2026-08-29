import { useEffect, useState } from "react";
import {
  APIProvider,
  AdvancedMarker,
  InfoWindow,
  Map,
  Pin,
  Polyline,
  useMap,
} from "@vis.gl/react-google-maps";
import { ChevronRight, RotateCcw } from "lucide-react";
import { useNavigate } from "react-router-dom";

export interface RoutePoint {
  lat: number;
  lng: number;
}

export interface MapCall {
  id: string;
  time: string;
  duration: string;
  level: string;
  title: string;
  summary: string;
  ubicacion?: string;
  position?: RoutePoint;
}

export interface MapTrip {
  id: string;
  label: string;
  position?: RoutePoint;
  route?: RoutePoint[];
  state?: string;
  alert?: { title: string; description: string };
  calls?: MapCall[];
}

interface InteractiveOperationsMapProps {
  trips: MapTrip[];
  destination: RoutePoint;
  apiKey?: string;
  onTripSelect?: (trip: MapTrip) => void;
  selectedTripId?: string;
}

function MapCameraController({
  targetPos,
  defaultCenter,
}: {
  targetPos: RoutePoint | null;
  defaultCenter: RoutePoint;
}) {
  const map = useMap();
  useEffect(() => {
    if (!map) return;
    if (targetPos) {
      map.panTo(targetPos);
      map.setZoom(14);
    } else {
      map.panTo(defaultCenter);
      map.setZoom(11);
    }
  }, [map, targetPos, defaultCenter]);
  return null;
}

export function InteractiveOperationsMap({
  trips,
  destination,
  apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY,
  onTripSelect,
  selectedTripId,
}: InteractiveOperationsMapProps) {
  const [selectedCallData, setSelectedCallData] = useState<{
    call: MapCall;
    tripId: string;
    pos: RoutePoint;
  } | null>(null);
  const navigate = useNavigate();

  const activeTargetPos = selectedCallData?.pos ?? null;

  return (
    <div className="relative h-[440px] overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm flex flex-col">
      {/* Top Map Action Bar */}
      <div className="z-10 flex items-center justify-between border-b border-neutral-200 bg-white px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-bold text-neutral-800">
            Mapa Operativo en Vivo
          </span>
        </div>
        {selectedCallData ? (
          <button
            type="button"
            onClick={() => setSelectedCallData(null)}
            className="flex items-center gap-1.5 rounded-lg border border-neutral-300 bg-neutral-50 px-2.5 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100 transition-colors shadow-sm cursor-pointer"
          >
            <RotateCcw size={12} />
            <span>Restablecer zoom</span>
          </button>
        ) : (
          <span className="text-[11px] font-medium text-neutral-500">
            Pines interactivos con zoom a dirección
          </span>
        )}
      </div>

      <div className="relative flex-1 w-full h-full">
        <APIProvider apiKey={apiKey}>
          <Map
            defaultCenter={destination}
            defaultZoom={11}
            gestureHandling="greedy"
            disableDefaultUI
            style={{ width: "100%", height: "100%" }}
          >
            <MapCameraController
              targetPos={activeTargetPos}
              defaultCenter={destination}
            />

            {/* Puerto destino marker */}
            <AdvancedMarker
              position={destination}
              title="Puerto destino (Terminal 3)"
            >
              <div className="group relative cursor-pointer flex flex-col items-center">
                <div className="pointer-events-none absolute -top-9 z-30 opacity-0 transition-opacity group-hover:opacity-100 whitespace-nowrap rounded-md bg-neutral-900 px-2.5 py-1 text-[11px] font-medium text-white shadow-xl">
                  ⚓ Terminal 3, Puerto La Plata
                </div>
                <Pin
                  background="#0d6b4d"
                  borderColor="#FFFFFF"
                  glyphColor="#FFFFFF"
                />
              </div>
            </AdvancedMarker>

            {/* Trips & Call markers */}
            {trips.map((trip) => (
              <span key={trip.id}>
                {trip.position && (
                  <AdvancedMarker
                    position={trip.position}
                    title={trip.label}
                    onClick={() => onTripSelect?.(trip)}
                  >
                    <div className="group relative cursor-pointer flex flex-col items-center">
                      <div className="pointer-events-none absolute -top-10 z-30 opacity-0 transition-opacity group-hover:opacity-100 whitespace-nowrap rounded-md bg-neutral-900 px-2.5 py-1 text-[11px] font-medium text-white shadow-xl">
                        🚛 {trip.label}{" "}
                        <span className="text-emerald-300">(Ver viaje)</span>
                      </div>
                      <Pin
                        background={
                          selectedTripId === trip.id ? "#1E8E5A" : "#B87A0A"
                        }
                        borderColor="#FFFFFF"
                        glyphColor="#FFFFFF"
                      />
                    </div>
                  </AdvancedMarker>
                )}

                {/* Render call markers along trip route */}
                {trip.calls?.map((call, idx) => {
                  const callSpot =
                    call.position ?? trip.route?.[idx + 1] ?? trip.position;
                  if (!callSpot) return null;
                  const isAttention = call.level === "attention";
                  const isCritical = call.level === "critical";

                  return (
                    <AdvancedMarker
                      key={call.id}
                      position={callSpot}
                      title={`${call.time} - ${call.title}`}
                      onClick={() =>
                        setSelectedCallData({
                          call,
                          tripId: trip.id,
                          pos: callSpot,
                        })
                      }
                    >
                      <div className="group relative flex cursor-pointer flex-col items-center">
                        {/* Animated Pulse Ring */}
                        <div
                          className={`absolute -inset-3 rounded-full opacity-70 transition-all ${isAttention ? "bg-amber-400 animate-ping" : isCritical ? "bg-red-500 animate-ping" : "bg-teal-400 group-hover:animate-ping"}`}
                        />

                        {/* Rich Hover Tooltip */}
                        <div className="pointer-events-none absolute -top-14 z-40 opacity-0 transition-all duration-200 group-hover:opacity-100 group-hover:-translate-y-1">
                          <div className="flex flex-col gap-0.5 rounded-lg border border-neutral-800 bg-neutral-950/95 p-2.5 text-white shadow-2xl backdrop-blur-md min-w-[200px]">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                                {call.time} hs ·{" "}
                                {isAttention ? "Atención" : "Normal"}
                              </span>
                              <span className="text-[10px] font-medium text-neutral-400">
                                Clic para zoom
                              </span>
                            </div>
                            <p className="text-xs font-bold text-neutral-100">
                              {call.title}
                            </p>
                            <p className="text-[11px] text-neutral-400 truncate">
                              📍 {call.ubicacion ?? "Ubicación en ruta"}
                            </p>
                          </div>
                        </div>

                        <Pin
                          background={
                            isCritical
                              ? "#C22E2E"
                              : isAttention
                                ? "#D97706"
                                : "#0284C7"
                          }
                          borderColor="#FFFFFF"
                          glyphColor="#FFFFFF"
                        />
                      </div>
                    </AdvancedMarker>
                  );
                })}

                {trip.route && trip.route.length > 1 && (
                  <Polyline
                    path={trip.route}
                    strokeColor="#0A5C8C"
                    strokeOpacity={0.8}
                    strokeWeight={4}
                  />
                )}
              </span>
            ))}

            {/* InfoWindow anchored directly AT the exact pin location */}
            {selectedCallData && (
              <InfoWindow
                position={selectedCallData.pos}
                pixelOffset={[0, -38]}
                onCloseClick={() => setSelectedCallData(null)}
              >
                <div className="p-2 min-w-[240px] max-w-[280px]">
                  <div className="flex items-center justify-between gap-2 pb-1 border-b border-neutral-100">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider ${selectedCallData.call.level === "attention" ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900"}`}
                    >
                      {selectedCallData.call.level === "attention"
                        ? "Atención"
                        : "Normal"}
                    </span>
                    <span className="text-xs font-mono font-bold text-neutral-600">
                      {selectedCallData.call.time} hs
                    </span>
                  </div>

                  <h3 className="mt-2 text-sm font-bold text-neutral-900 leading-snug">
                    {selectedCallData.call.title}
                  </h3>

                  <div className="mt-1 flex items-start gap-1 text-[11px] font-medium text-neutral-600">
                    <span className="shrink-0 text-emerald-700">📍</span>
                    <span className="leading-tight">
                      {selectedCallData.call.ubicacion ?? "Ubicación en ruta"}
                    </span>
                  </div>

                  <p className="mt-2 rounded-lg bg-neutral-50 p-2.5 text-xs text-neutral-700 leading-relaxed border border-neutral-100">
                    "{selectedCallData.call.summary}"
                  </p>

                  <button
                    type="button"
                    onClick={() =>
                      navigate(
                        `/pedidos/${selectedCallData.tripId}/llamadas/${selectedCallData.call.id}`,
                      )
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
    </div>
  );
}
