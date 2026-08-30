import { useEffect, useState } from "react";
import { AlertTriangle, ArrowUpRight, Clock3, PhoneCall, ShieldAlert, Truck } from "lucide-react";
import { Link } from "react-router-dom";
import { useDatos } from "../../useDatos";
import { useLanguage } from "../../i18n";
import { OperationsPulse } from "./OperationsPulse";

function MetricValue({ value, suffix = "" }: { value: number; suffix?: string }) {
  const { locale } = useLanguage();
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const frame = requestAnimationFrame(() => setDisplayed(value));
      return () => cancelAnimationFrame(frame);
    }

    let frame = 0;
    const startedAt = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - startedAt) / 400, 1);
      const eased = 1 - Math.pow(1 - progress, 4);
      setDisplayed(Math.round(value * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return (
    <span className="ops-metric__value" aria-live="polite">
      {new Intl.NumberFormat(locale).format(displayed)}{suffix}
    </span>
  );
}

export function OperationsHome() {
  const { trips, alerts } = useDatos();
  const { locale } = useLanguage();
  const isEnglish = locale === "en";
  const activeTrips = trips.filter((trip) => trip.estado !== "finalizado");
  const completedTrips = trips.filter((trip) => trip.estado === "finalizado");
  const criticalAlerts = alerts.filter((alert) => alert.tipo === "emergencia");
  const agentCalls = trips.reduce((total, trip) => total + trip.calls.length, 0);
  const activityPoints = trips
    .flatMap((trip) => trip.calls.map((call) => ({ time: call.time, level: call.level })))
    .sort((a, b) => a.time.localeCompare(b.time));
  const timeSavedMinutes = agentCalls * 12 + completedTrips.length * 18;
  const primaryAlert = criticalAlerts[0];
  const copy = isEnglish
    ? {
        context: "Operations center · mock data",
        title: "Intervene only when impact is critical.",
        intro: "The agent monitors every transfer. Your team gets a clear signal only when a human decision is required.",
        priority: `${criticalAlerts.length} critical alert requires attention`,
        alerts: "Handle critical alert",
        noAlerts: "No critical alerts pending",
        tracking: "Operational tracking",
        transfers: "View transfers",
        activeTransfers: `${activeTrips.length} active transfers · route, ETA and activity`,
        openTransfers: "Open transfers",
        metrics: "Agent metrics",
        demo: "Demo estimates",
        saved: "Time saved",
        resolved: "Orders resolved",
        calls: "Agent calls",
        escalations: "Critical escalations",
        tooltip: "Mock estimate: 12 min per call and 18 min per completed transfer",
        footer: "Continuous monitoring · intervention by exception",
      }
    : {
        context: "Centro operativo · datos mock",
        title: "Intervení solo cuando el impacto es crítico.",
        intro: "El agente monitorea cada traslado. El equipo recibe una señal clara únicamente cuando hace falta una decisión humana.",
        priority: `${criticalAlerts.length} alerta crítica requiere atención`,
        alerts: "Atender alerta crítica",
        noAlerts: "No hay alertas críticas pendientes",
        tracking: "Seguimiento operativo",
        transfers: "Ver traslados",
        activeTransfers: `${activeTrips.length} traslados activos · recorrido, ETA y actividad`,
        openTransfers: "Abrir traslados",
        metrics: "Métricas del agente",
        demo: "Estimaciones de demostración",
        saved: "Tiempo ahorrado",
        resolved: "Pedidos solucionados",
        calls: "Llamadas del agente",
        escalations: "Derivaciones críticas",
        tooltip: "Estimación mock: 12 min por llamada y 18 min por traslado finalizado",
        footer: "Monitoreo continuo · intervención por excepción",
      };

  return (
    <main className="ops-home">
      <section className="ops-command" aria-labelledby="ops-command-title">
        <div className="ops-command__copy">
          <p className="ops-home__context">{copy.context}</p>
          <h1 id="ops-command-title">{copy.title}</h1>
          <p className="ops-command__intro">{copy.intro}</p>

          <div className="ops-command__incident">
            <span className="ops-command__priority"><i aria-hidden="true" />{copy.priority}</span>
            <strong>{primaryAlert?.titulo ?? copy.noAlerts}</strong>
            {primaryAlert && <small>{primaryAlert.ubicacion} · {primaryAlert.hace}</small>}
          </div>

          <Link className="ops-primary-cta" to="/alertas?severity=critical">
            <ShieldAlert size={18} aria-hidden="true" />
            <span>{copy.alerts}</span>
            <ArrowUpRight size={18} aria-hidden="true" />
          </Link>
        </div>

        <OperationsPulse
          points={activityPoints}
          activeTrips={activeTrips.length}
          criticalAlerts={criticalAlerts.length}
          locale={locale}
        />
      </section>

      <section className="ops-transfer-entry" aria-label={copy.tracking}>
        <Link to="/pedidos">
          <span className="ops-transfer-entry__icon" aria-hidden="true"><Truck size={20} /></span>
          <span>
            <small>{copy.tracking}</small>
            <strong>{copy.transfers}</strong>
            <span>{copy.activeTransfers}</span>
          </span>
          <span className="ops-transfer-entry__cta">{copy.openTransfers} <ArrowUpRight size={17} /></span>
        </Link>
      </section>

      <section className="ops-metrics" aria-label="Métricas del agente">
        <div className="ops-metrics__heading">
          <span>{copy.metrics}</span>
          <small>{copy.demo}</small>
        </div>
        <dl>
          <div title={copy.tooltip}>
            <dt><Clock3 size={16} /> {copy.saved}</dt>
            <dd><MetricValue value={timeSavedMinutes} suffix=" min" /></dd>
          </div>
          <div>
            <dt><Truck size={16} /> {copy.resolved}</dt>
            <dd><MetricValue value={completedTrips.length} /></dd>
          </div>
          <div>
            <dt><PhoneCall size={16} /> {copy.calls}</dt>
            <dd><MetricValue value={agentCalls} /></dd>
          </div>
          <div>
            <dt><AlertTriangle size={16} /> {copy.escalations}</dt>
            <dd><MetricValue value={criticalAlerts.length} /></dd>
          </div>
        </dl>
      </section>

      <footer className="ops-home__footer">
        <span>21agents Ops</span>
        <span>{copy.footer}</span>
      </footer>
    </main>
  );
}
