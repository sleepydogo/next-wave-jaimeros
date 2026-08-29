import type { Alert } from "../../types/dashboard";
import { ALERT_META } from "../../constants/theme";
import { alerts as defaultAlerts } from "../../data/mockData";

interface AlertasSectionProps {
  alerts?: Alert[];
}

export function AlertasSection({
  alerts = defaultAlerts,
}: AlertasSectionProps) {
  return (
    <div className="flex flex-col bg-white rounded-xl border border-neutral-200 p-4 shadow-sm">
      {alerts.map((a, i) => {
        const meta = ALERT_META[a.tipo];
        const Icon = meta.icon;
        return (
          <div
            key={a.id}
            className={`flex items-center gap-3 py-3.5 ${
              i !== alerts.length - 1 ? "border-b border-neutral-200" : ""
            }`}
          >
            <Icon size={16} style={{ color: meta.color }} />
            <p className="flex-1 text-[14px] text-neutral-800">{a.texto}</p>
            <p className="text-[13px] text-neutral-400 tabular-nums">
              {a.hora}
            </p>
          </div>
        );
      })}
    </div>
  );
}
