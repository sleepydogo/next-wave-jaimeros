import { Truck } from "lucide-react";
import type { Trip } from "../../types/dashboard";
import { STATE_META } from "../../constants/theme";
import { Card } from "../ui/Card";
import { Badge } from "../ui/Badge";
import { trips as defaultTrips } from "../../data/mockData";
import {
  InteractiveOperationsMap,
  type MapTrip,
} from "./InteractiveOperationsMap";
import { TripDetailPanel } from "./TripDetailPanel";
import { useState } from "react";

interface ViajesSectionProps {
  trips?: Trip[];
  onSelectTrip: (trip: Trip) => void;
}

export function ViajesSection({
  trips = defaultTrips,
  onSelectTrip,
}: ViajesSectionProps) {
  const [selectedMapTrip, setSelectedMapTrip] = useState<MapTrip | null>(null);
  const mapTrips: MapTrip[] = trips.map((trip, index) => ({
    id: trip.id,
    label: `${trip.patente} · ${trip.conductor}`,
    state: trip.estado,
    position: { lat: -34.5745 + index * 0.012, lng: -58.366 - index * 0.02 },
    route: [
      { lat: -34.62 + index * 0.012, lng: -58.48 - index * 0.02 },
      { lat: -34.6 + index * 0.012, lng: -58.43 - index * 0.02 },
      { lat: -34.5745 + index * 0.012, lng: -58.366 - index * 0.02 },
    ],
    alert:
      trip.estado === "emergencia"
        ? {
            title: "Parada en ruta",
            description: "No hay confirmación del conductor.",
          }
        : undefined,
    calls: trip.calls,
  }));
  return (
    <div className="flex flex-col gap-3">
      <div className="relative">
        <InteractiveOperationsMap
          trips={mapTrips}
          destination={{ lat: -34.5745, lng: -58.366 }}
          apiKey={import.meta.env.VITE_GOOGLE_MAPS_API_KEY}
          onTripSelect={setSelectedMapTrip}
          selectedTripId={selectedMapTrip?.id}
        />
        <TripDetailPanel
          trip={selectedMapTrip}
          onClose={() => setSelectedMapTrip(null)}
        />
      </div>
      {trips.map((t) => {
        const meta = STATE_META[t.estado];
        return (
          <Card key={t.id} onClick={() => onSelectTrip(t)} className="p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-neutral-100">
                  <Truck size={18} className="text-neutral-500" />
                </div>
                <div>
                  <p className="text-[15px] font-medium text-neutral-900">
                    {t.patente}
                  </p>
                  <p className="text-[13px] text-neutral-500">
                    {t.conductor} · {t.ubicacion}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-6">
                {t.estado === "en_ruta" && (
                  <p className="text-[13px] text-neutral-500 tabular-nums">
                    {t.velocidad} km/h
                  </p>
                )}
                <p className="text-[13px] text-neutral-400">{t.hace}</p>
                <Badge color={meta.color}>{meta.label}</Badge>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
