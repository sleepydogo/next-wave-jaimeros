import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { Alert } from "./types/dashboard";

/** Overlay rojo a pantalla completa cuando entra una emergencia.
 *
 * El monitorista no esta mirando la tabla todo el tiempo: si el conductor
 * reporta un robo, la pantalla tiene que gritarlo. Se dispara con las alertas
 * que el agente marca como EMERGENCIA en vivo, mientras la llamada sigue.
 */
const YA_VISTAS = "nextwave.alertas.vistas";

function esEmergencia(a: Alert) {
  return a.tipo === "emergencia" && /emergencia/i.test(a.titulo);
}

export function AlertaCritica({ alerts }: { alerts: Alert[] }) {
  const [descartadas, setDescartadas] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(YA_VISTAS) ?? "[]");
    } catch {
      return [];
    }
  });
  const navigate = useNavigate();

  const activa = alerts.filter(esEmergencia).find((a) => !descartadas.includes(a.id));

  // sonido corto: el monitorista puede no estar mirando la pantalla
  useEffect(() => {
    if (!activa) return;
    try {
      const ctx = new AudioContext();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = 880;
      g.gain.value = 0.08;
      o.connect(g).connect(ctx.destination);
      o.start();
      o.stop(ctx.currentTime + 0.35);
    } catch {
      // si el navegador bloquea el audio, el overlay igual se ve
    }
  }, [activa?.id]);

  if (!activa) return null;

  const descartar = () => {
    const nuevas = [...descartadas, activa.id];
    setDescartadas(nuevas);
    try {
      localStorage.setItem(YA_VISTAS, JSON.stringify(nuevas.slice(-50)));
    } catch {
      /* sin localStorage se vuelve a mostrar al recargar, es aceptable */
    }
  };

  return (
    <div
      role="alertdialog"
      aria-live="assertive"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(185, 28, 28, 0.97)",
        color: "#fff",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 18,
        padding: 32,
        textAlign: "center",
        animation: "nwLatido 1.1s ease-in-out infinite",
      }}
    >
      <style>{`@keyframes nwLatido {
        0%,100% { background-color: rgba(185,28,28,0.97) }
        50%     { background-color: rgba(127,15,15,0.97) }
      }`}</style>

      <div style={{ fontSize: 13, letterSpacing: 3, fontWeight: 700, opacity: 0.85 }}>
        EMERGENCIA EN CURSO
      </div>
      <h1 style={{ fontSize: 40, fontWeight: 800, margin: 0, maxWidth: 900, lineHeight: 1.15 }}>
        {activa.titulo}
      </h1>
      <p style={{ fontSize: 19, margin: 0, maxWidth: 780, opacity: 0.95 }}>{activa.texto}</p>
      <p style={{ fontSize: 15, opacity: 0.8, margin: 0 }}>
        {activa.conductor} · viaje {activa.order} · {activa.hora} hs
      </p>

      <div
        style={{
          display: "flex",
          gap: 12,
          marginTop: 10,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        <button
          onClick={() => {
            descartar();
            navigate(`/alertas/${activa.id}`);
          }}
          style={{
            background: "#fff",
            color: "#b91c1c",
            border: 0,
            borderRadius: 10,
            padding: "13px 26px",
            fontSize: 15,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          Ver la llamada
        </button>
        <button
          onClick={descartar}
          style={{
            background: "transparent",
            color: "#fff",
            border: "1.5px solid rgba(255,255,255,.6)",
            borderRadius: 10,
            padding: "13px 26px",
            fontSize: 15,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Ya la vi
        </button>
      </div>
    </div>
  );
}
