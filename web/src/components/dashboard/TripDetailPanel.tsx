import type { MapTrip } from "./InteractiveOperationsMap";

interface TripDetailPanelProps {
  trip: MapTrip | null;
  onClose: () => void;
}

export function TripDetailPanel({ trip, onClose }: TripDetailPanelProps) {
  if (!trip) return null;
  return (
    <aside
      className="absolute right-6 top-6 z-10 w-80 rounded-xl border border-neutral-200 bg-white p-5 shadow-lg"
      aria-label="Detalle del viaje"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
            Viaje seleccionado
          </p>
          <h2 className="mt-2 text-xl font-semibold text-neutral-900">
            {trip.label}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-sm font-medium text-[#0A5C8C]"
        >
          Cerrar
        </button>
      </div>
      <dl className="mt-5 space-y-3 border-t border-neutral-200 pt-4 text-sm">
        <div className="flex justify-between">
          <dt className="text-neutral-500">Estado</dt>
          <dd className="font-medium text-neutral-900">
            {trip.state ?? "Sin estado"}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-neutral-500">Posición</dt>
          <dd className="font-medium text-neutral-900">
            {trip.position
              ? `${trip.position.lat.toFixed(4)}, ${trip.position.lng.toFixed(4)}`
              : "Sin posición"}
          </dd>
        </div>
      </dl>
      {trip.alert && (
        <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm">
          <p className="font-semibold text-amber-800">{trip.alert.title}</p>
          <p className="mt-1 text-amber-700">{trip.alert.description}</p>
        </div>
      )}
      <button
        type="button"
        onClick={onClose}
        className="mt-4 w-full rounded-lg bg-[#0A5C8C] px-4 py-3 text-sm font-semibold text-white"
      >
        Ver detalle
      </button>
    </aside>
  );
}
