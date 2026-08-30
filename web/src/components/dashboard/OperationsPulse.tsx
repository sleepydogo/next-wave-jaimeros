type ActivityPoint = {
  time: string;
  level: "normal" | "attention" | "critical";
};

type OperationsPulseProps = {
  points: ActivityPoint[];
  locale: "en" | "es";
};

const LEVEL_Y = {
  normal: 108,
  attention: 72,
  critical: 38,
};

export function OperationsPulse({ points, locale }: OperationsPulseProps) {
  const isEnglish = locale === "en";
  const visiblePoints = points.slice(-5);
  const coordinates = visiblePoints.map((point, index) => ({
    ...point,
    x: visiblePoints.length === 1 ? 210 : 34 + index * (352 / Math.max(visiblePoints.length - 1, 1)),
    y: LEVEL_Y[point.level],
  }));
  const linePath = coordinates.length
    ? `M 18 128 ${coordinates.map((point) => `L ${point.x} ${point.y}`).join(" ")} L 410 128`
    : "M 18 128 L 410 128";

  const copy = isEnglish
    ? {
        title: "Agent activity",
        live: "Current shift",
        description: "Live trace of backend agent calls during the current shift.",
      }
    : {
        title: "Actividad del agente",
        live: "Turno actual",
        description: "Traza en vivo de llamadas del backend durante el turno actual.",
      };

  return (
    <figure className="operations-pulse" aria-labelledby="operations-pulse-title">
      <figcaption className="operations-pulse__header">
        <span id="operations-pulse-title">{copy.title}</span>
        <span className="operations-pulse__live"><i aria-hidden="true" />{copy.live}</span>
      </figcaption>

      <svg
        className="operations-pulse__chart"
        viewBox="0 0 428 158"
        role="img"
        aria-label={copy.description}
      >
        <path className="operations-pulse__grid" d="M18 38H410 M18 72H410 M18 108H410 M18 128H410" />
        <path className="operations-pulse__area" d={`${linePath} L 410 140 L 18 140 Z`} />
        <path className="operations-pulse__line" d={linePath} />
        {coordinates.map((point, index) => (
          <g
            className={`operations-pulse__point operations-pulse__point--${point.level}`}
            key={`${point.time}-${index}`}
          >
            <circle cx={point.x} cy={point.y} r="5" />
            <circle className="operations-pulse__point-ring" cx={point.x} cy={point.y} r="10" />
            <text x={point.x} y="153" textAnchor="middle">{point.time}</text>
          </g>
        ))}
      </svg>

    </figure>
  );
}
