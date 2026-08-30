import { useEffect, useState } from "react";
import { AlertTriangle, ArrowUpRight, Clock3, PhoneCall, ShieldAlert, Truck } from "lucide-react";
import { Link } from "react-router-dom";
import { useDatos } from "../../useDatos";
import { useLanguage } from "../../i18n";

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
  const timeSavedMinutes = agentCalls * 12 + completedTrips.length * 18;
  const primaryAlert = criticalAlerts[0];
  const copy = isEnglish
    ? {
        context: "Operations center · mock data",
        title: "Act where impact is highest.",
        intro: "The agent monitors the operation. The team steps in only when a critical alert requires a human decision.",
        navLabel: "Operational shortcuts",
        priority: `Human priority · ${criticalAlerts.length} critical`,
        alerts: "Handle alerts",
        noAlerts: "No critical alerts pending",
        review: "Review now",
        tracking: "Operational tracking",
        transfers: "View transfers",
        activeTransfers: `${activeTrips.length} active transfers · route, ETA and activity`,
        mockUpdate: "Automatic updates with mock data",
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
        title: "Actuá donde hay impacto.",
        intro: "El agente monitorea la operación. El equipo interviene únicamente cuando una alerta crítica necesita decisión humana.",
        navLabel: "Accesos operativos",
        priority: `Prioridad humana · ${criticalAlerts.length} crítica`,
        alerts: "Atender alertas",
        noAlerts: "No hay alertas críticas pendientes",
        review: "Revisar ahora",
        tracking: "Seguimiento operativo",
        transfers: "Ver traslados",
        activeTransfers: `${activeTrips.length} traslados activos · recorrido, ETA y actividad`,
        mockUpdate: "Actualización automática con datos mock",
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
      <header className="ops-home__intro">
        <div>
          <p className="ops-home__context">{copy.context}</p>
          <h1>{copy.title}</h1>
        </div>
        <p>
          {copy.intro}
        </p>
      </header>

      <section className="ops-index" aria-label={copy.navLabel}>
        <Link className="ops-action ops-action--critical" to="/alertas?severity=critical">
          <span className="ops-action__icon" aria-hidden="true"><ShieldAlert size={22} /></span>
          <span className="ops-action__body">
            <span className="ops-action__meta">{copy.priority}</span>
            <strong>{copy.alerts}</strong>
            <span>{primaryAlert?.titulo ?? copy.noAlerts}</span>
          </span>
          <span className="ops-action__aside">
            {primaryAlert && <small>{primaryAlert.ubicacion} · {primaryAlert.hace}</small>}
            <span className="ops-action__cta">{copy.review} <ArrowUpRight size={17} /></span>
          </span>
        </Link>

        <Link className="ops-action" to="/pedidos">
          <span className="ops-action__icon" aria-hidden="true"><Truck size={22} /></span>
          <span className="ops-action__body">
            <span className="ops-action__meta">{copy.tracking}</span>
            <strong>{copy.transfers}</strong>
            <span>{copy.activeTransfers}</span>
          </span>
          <span className="ops-action__aside">
            <small>{copy.mockUpdate}</small>
            <span className="ops-action__cta">{copy.openTransfers} <ArrowUpRight size={17} /></span>
          </span>
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
