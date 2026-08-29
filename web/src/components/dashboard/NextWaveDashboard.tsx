import { useCallback, useEffect, useState } from "react";
import {
  checkApiHealth,
  getTrips,
  getAlerts,
  getCalls,
  getMetrics,
} from "../../api";
import {
  trips as mockTrips,
  alerts as mockAlerts,
  calls as mockCalls,
} from "../../data/mockData";
import type { Metrics } from "../../api";
import type { Alert, Call, NavKey, Trip } from "../../types/dashboard";
import { Sidebar } from "../layout/Sidebar";
import { Header } from "../layout/Header";
import { ViajesSection } from "./ViajesSection";
import { AlertasSection } from "./AlertasSection";
import { LlamadasSection } from "./LlamadasSection";
import { CostosSection } from "./CostosSection";
import { TripPanel } from "./TripPanel";

const POLL_INTERVAL_MS = 10_000;

export default function NextWaveDashboard() {
  const [section, setSection] = useState<NavKey>("viajes");
  const [selectedTrip, setSelectedTrip] = useState<Trip | null>(null);
  const [apiConnected, setApiConnected] = useState(false);

  // datos del backend (o mock mientras no hay conexión)
  const [trips, setTrips] = useState<Trip[]>(mockTrips);
  const [alerts, setAlerts] = useState<Alert[]>(mockAlerts);
  const [callsList, setCallsList] = useState<Call[]>(mockCalls);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    // health check rápido
    const healthy = await checkApiHealth()
      .then(({ ok }) => ok)
      .catch(() => false);

    setApiConnected(healthy);

    if (!healthy) {
      // sin backend → quedarse con mock data
      setLoading(false);
      return;
    }

    // traer todo en paralelo
    const [fetchedTrips, fetchedAlerts, fetchedCalls, fetchedMetrics] =
      await Promise.allSettled([
        getTrips(),
        getAlerts(),
        getCalls(),
        getMetrics(),
      ]);

    if (fetchedTrips.status === "fulfilled") setTrips(fetchedTrips.value);
    if (fetchedAlerts.status === "fulfilled") setAlerts(fetchedAlerts.value);
    if (fetchedCalls.status === "fulfilled") setCallsList(fetchedCalls.value);
    if (fetchedMetrics.status === "fulfilled") setMetrics(fetchedMetrics.value);

    setLoading(false);
  }, []);

  // carga inicial
  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // polling cada 10 s
  useEffect(() => {
    const id = setInterval(fetchAll, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchAll]);

  return (
    <div className="flex h-full min-h-screen w-full bg-[#FAFAFA] font-sans text-neutral-900">
      <Sidebar activeSection={section} onSelectSection={setSection} />

      <div className="flex flex-1 flex-col">
        <Header section={section} apiConnected={apiConnected} />

        {loading ? (
          <main className="flex flex-1 items-center justify-center">
            <p className="text-sm text-neutral-400 animate-pulse">
              Conectando con el backend…
            </p>
          </main>
        ) : (
          <main className="flex-1 overflow-y-auto px-8 py-6">
            {section === "viajes" && (
              <ViajesSection trips={trips} onSelectTrip={setSelectedTrip} />
            )}
            {section === "alertas" && <AlertasSection alerts={alerts} />}
            {section === "llamadas" && <LlamadasSection calls={callsList} />}
            {section === "costos" && <CostosSection metrics={metrics} />}
          </main>
        )}
      </div>

      <TripPanel trip={selectedTrip} onClose={() => setSelectedTrip(null)} />
    </div>
  );
}
