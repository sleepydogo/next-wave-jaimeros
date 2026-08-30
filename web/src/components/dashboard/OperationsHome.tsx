import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useDatos } from "../../useDatos";
import { useLanguage } from "../../i18n";
import { OperationsPulse } from "./OperationsPulse";

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
  const formatMetric = (value: number, suffix = "") =>
    `${new Intl.NumberFormat(locale).format(value)}${suffix}`;
  const copy = isEnglish
    ? {
        title: criticalAlerts.length === 0
          ? "No critical alerts pending"
          : criticalAlerts.length === 1
            ? "1 critical alert needs action"
            : `${criticalAlerts.length} critical alerts need action`,
        intro: `${activeTrips.length} active transfers remain under agent monitoring. Intervene only by exception.`,
        priority: "Critical priority",
        alerts: criticalAlerts.length > 0 ? "Handle critical alert" : "View alerts",
        noAlerts: "No critical alerts pending",
        tracking: "Transfers",
        transfers: "Active transfers",
        activeTransfers: `${activeTrips.length} in progress · route, ETA and activity`,
        openTransfers: "Open transfers",
        metrics: "Agent metrics",
        demo: "Mock estimates",
        saved: "Time saved",
        resolved: "Orders resolved",
        calls: "Agent calls",
        escalations: "Critical escalations",
        tooltip: "Mock estimate: 12 min per call and 18 min per completed transfer",
      }
    : {
        title: criticalAlerts.length === 0
          ? "No hay alertas críticas pendientes"
          : criticalAlerts.length === 1
            ? "1 alerta crítica requiere acción"
            : `${criticalAlerts.length} alertas críticas requieren acción`,
        intro: `${activeTrips.length} traslados activos siguen bajo monitoreo del agente. Intervení solo por excepción.`,
        priority: "Prioridad crítica",
        alerts: criticalAlerts.length > 0 ? "Atender alerta crítica" : "Ver alertas",
        noAlerts: "No hay alertas críticas pendientes",
        tracking: "Traslados",
        transfers: "Traslados activos",
        activeTransfers: `${activeTrips.length} en curso · recorrido, ETA y actividad`,
        openTransfers: "Abrir traslados",
        metrics: "Métricas del agente",
        demo: "Estimaciones mock",
        saved: "Tiempo ahorrado",
        resolved: "Pedidos solucionados",
        calls: "Llamadas del agente",
        escalations: "Derivaciones críticas",
        tooltip: "Estimación mock: 12 min por llamada y 18 min por traslado finalizado",
      };

  return (
    <main className="ops-home">
      <header className="ops-home__header">
        <h1 id="ops-command-title">{copy.title}</h1>
        <p>{copy.intro}</p>
      </header>

      <section className="ops-command" aria-labelledby="ops-command-title">
        <div className="ops-command__alert">
          <span className="ops-command__priority"><i aria-hidden="true" />{copy.priority}</span>
          <h2>{primaryAlert?.titulo ?? copy.noAlerts}</h2>
          {primaryAlert && <p>{primaryAlert.ubicacion} · {primaryAlert.hace}</p>}

          <Link className="ops-primary-cta" to="/alertas?severity=critical">
            <span>{copy.alerts}</span>
            <ArrowUpRight size={17} aria-hidden="true" />
          </Link>
        </div>

        <OperationsPulse
          points={activityPoints}
          locale={locale}
        />
      </section>

      <section className="ops-transfer-entry" aria-label={copy.tracking}>
        <Link to="/pedidos">
          <span className="ops-transfer-entry__body">
            <strong>{copy.transfers}</strong>
            <span>{copy.activeTransfers}</span>
          </span>
          <span className="ops-transfer-entry__cta">{copy.openTransfers} <ArrowUpRight size={17} /></span>
        </Link>
      </section>

      <section className="ops-metrics" aria-label={copy.metrics}>
        <div className="ops-metrics__heading">
          <span>{copy.metrics}</span>
          <small>{copy.demo}</small>
        </div>
        <dl>
          <div className="ops-metrics__lead" title={copy.tooltip}>
            <dt>{copy.saved}</dt>
            <dd><span className="ops-metric__value">{formatMetric(timeSavedMinutes, " min")}</span></dd>
          </div>
          <div>
            <dt>{copy.resolved}</dt>
            <dd><span className="ops-metric__value">{formatMetric(completedTrips.length)}</span></dd>
          </div>
          <div>
            <dt>{copy.calls}</dt>
            <dd><span className="ops-metric__value">{formatMetric(agentCalls)}</span></dd>
          </div>
          <div>
            <dt>{copy.escalations}</dt>
            <dd><span className="ops-metric__value">{formatMetric(criticalAlerts.length)}</span></dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
