import { createContext, useContext, useEffect, useState } from "react";

import { getAlerts, getMetrics, getTripsConLlamadas, hydrateAlerts } from "./api";
import type { Metrics } from "./api";
import type { Alert, Trip } from "./types/dashboard";

/** Datos vivos del backend, refrescados solos.
 *
 * El dashboard tiene que reflejar lo que va pasando sin que nadie recargue:
 * el conductor toca un boton, el agente llama, y la llamada aparece aca con su
 * transcripcion y su audio.
 */
interface Datos {
  trips: Trip[];
  alerts: Alert[];
  metrics: Metrics | null;
  cargando: boolean;
  error: string | null;
}

const Ctx = createContext<Datos>({
  trips: [],
  alerts: [],
  metrics: null,
  cargando: true,
  error: null,
});

export const useDatos = () => useContext(Ctx);

export function DatosProvider({
  children,
  cada = 5000,
}: {
  children: React.ReactNode;
  cada?: number;
}) {
  const [datos, setDatos] = useState<Datos>({
    trips: [],
    alerts: [],
    metrics: null,
    cargando: true,
    error: null,
  });

  useEffect(() => {
    let vivo = true;
    const traer = async () => {
      try {
        const [trips, rawAlerts, metrics] = await Promise.all([
          getTripsConLlamadas(),
          getAlerts(),
          getMetrics(),
        ]);
        const alerts = hydrateAlerts(rawAlerts, trips);
        if (vivo) setDatos({ trips, alerts, metrics, cargando: false, error: null });
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
