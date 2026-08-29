import { X, PhoneCall } from "lucide-react";
import type { Trip } from "../../types/dashboard";
import { STATE_META, COLOR } from "../../constants/theme";
import { Badge } from "../ui/Badge";

interface TripPanelProps {
  trip: Trip | null;
  onClose: () => void;
}

export function TripPanel({ trip, onClose }: TripPanelProps) {
  if (!trip) return null;

  const meta = STATE_META[trip.estado];

  return (
    <div className="fixed inset-0 z-20 flex justify-end">
      <div
        className="flex-1 bg-black/10 transition-opacity"
        onClick={onClose}
      />

      <div className="flex h-full w-[380px] flex-col bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[20px] font-semibold text-neutral-900">
              {trip.patente}
            </p>
            <p className="text-[13px] text-neutral-500">{trip.conductor}</p>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600 transition-colors"
            aria-label="Cerrar panel"
          >
            <X size={20} />
          </button>
        </div>

        <div className="mt-4">
          <Badge color={meta.color}>{meta.label}</Badge>
        </div>

        <div className="mt-6">
          <p className="text-[13px] font-medium text-neutral-600">
            Ubicación actual
          </p>
          <p className="mt-1 text-[14px] text-neutral-800">{trip.ubicacion}</p>
        </div>

        <div className="mt-6 flex-1 overflow-y-auto">
          <p className="mb-3 text-[13px] font-medium text-neutral-600">
            Línea de tiempo
          </p>
          <div className="flex flex-col gap-4">
            {trip.eventos.map((e, i) => (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="h-2 w-2 rounded-full bg-neutral-300" />
                  {i !== trip.eventos.length - 1 && (
                    <span className="mt-1 w-px flex-1 bg-neutral-200" />
                  )}
                </div>
                <div className="pb-1">
                  <p className="text-[13px] text-neutral-400">{e.hora}</p>
                  <p className="text-[14px] text-neutral-800">{e.texto}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <button
          className="mt-4 flex items-center justify-center gap-2 rounded-lg py-2.5 text-[14px] font-medium text-white transition-opacity hover:opacity-90"
          style={{ backgroundColor: COLOR.accent }}
        >
          <PhoneCall size={15} /> Llamar al conductor
        </button>
      </div>
    </div>
  );
}
