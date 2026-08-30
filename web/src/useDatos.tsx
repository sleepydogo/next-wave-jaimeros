import { createContext, useContext, useEffect, useState } from "react";

import { getAlerts, getTripsConLlamadas } from "./api";
import { alerts as mockAlerts, trips as mockTrips } from "./data/mockData";
import type { Alert, Trip } from "./types/dashboard";

// The prototype is intentionally local-first while the visual design is in
// progress. Set VITE_DATA_SOURCE=api when it is time to reconnect the backend.
const USE_MOCK_DATA = import.meta.env.VITE_DATA_SOURCE !== "api";

/** Datos vivos del backend, refrescados solos.
 *
 * El dashboard tiene que reflejar lo que va pasando sin que nadie recargue:
 * el conductor toca un boton, el agente llama, y la llamada aparece aca con su
 * transcripcion y su audio.
 */
interface Datos {
  trips: Trip[];
  alerts: Alert[];
  cargando: boolean;
  error: string | null;
}

const Ctx = createContext<Datos>({ trips: [], alerts: [], cargando: true, error: null });

export const useDatos = () => useContext(Ctx);

export function DatosProvider({
  children,
  cada = 5000,
}: {
  children: React.ReactNode;
  cada?: number;
}) {
  const [datos, setDatos] = useState<Datos>({
    trips: USE_MOCK_DATA ? mockTrips : [],
    alerts: USE_MOCK_DATA ? mockAlerts : [],
    cargando: !USE_MOCK_DATA,
    error: null,
  });

  useEffect(() => {
    if (USE_MOCK_DATA) {
      return;
    }

    let vivo = true;
    const traer = async () => {
      try {
        const [trips, alerts] = await Promise.all([getTripsConLlamadas(), getAlerts()]);
        if (vivo) setDatos({ trips, alerts, cargando: false, error: null });
      } catch (e) {
        // no vaciamos lo que ya se estaba mostrando: si el backend parpadea,
        // el monitorista sigue viendo la ultima foto buena
        if (vivo)
          setDatos((prev) => ({ ...prev, cargando: false, error: (e as Error).message }));
      }
    };
    traer();
    const id = setInterval(traer, cada);
    return () => {
      vivo = false;
      clearInterval(id);
    };
  }, [cada]);

  return <Ctx.Provider value={datos}>{children}</Ctx.Provider>;
}
