import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { CostData } from "../../types/dashboard";
import { COLOR } from "../../constants/theme";
import { Card } from "../ui/Card";
import { costData as defaultCostData } from "../../data/mockData";
import type { Metrics } from "../../api";

interface CostosSectionProps {
  data?: CostData[];
  metrics?: Metrics | null;
}

export function CostosSection({
  data = defaultCostData,
  metrics,
}: CostosSectionProps) {
  const totalAgente = metrics?.costo_agente_usd ?? 0;
  const totalHumano = metrics?.costo_humano_equivalente_usd ?? 0;
  const ahorro = totalHumano - totalAgente;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-5">
          <p className="text-[13px] text-neutral-500">Costo del día (agente)</p>
          <p className="mt-1 text-[32px] font-semibold text-neutral-900">
            ${totalAgente.toFixed(2)}
          </p>
        </Card>

        <Card className="p-5">
          <p className="text-[13px] text-neutral-500">
            Hubiera costado (monitorista)
          </p>
          <p className="mt-1 text-[32px] font-semibold text-neutral-400">
            ${totalHumano.toFixed(2)}
          </p>
        </Card>

        <Card className="p-5">
          <p className="text-[13px] text-neutral-500">Ahorro acumulado</p>
          <p
            className="mt-1 text-[32px] font-semibold"
            style={{ color: COLOR.success }}
          >
            ${ahorro.toFixed(2)}
          </p>
        </Card>
      </div>

      <Card className="p-5">
        <p className="mb-4 text-[13px] font-medium text-neutral-600">
          Costo acumulado por evento gestionado
        </p>

        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data} margin={{ left: -20, right: 10 }}>
            <XAxis
              dataKey="hora"
              tick={{ fontSize: 12, fill: "#6B6B6B" }}
              axisLine={{ stroke: "#E5E5E5" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 12, fill: "#6B6B6B" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #E5E5E5",
                fontSize: 12,
              }}
              formatter={(value) => [`$${Number(value ?? 0).toFixed(2)}`, ""]}
            />
            <Line
              type="monotone"
              dataKey="agente"
              stroke={COLOR.accent}
              strokeWidth={2}
              dot={false}
              name="Agente"
            />
            <Line
              type="monotone"
              dataKey="humano"
              stroke="#B0B0B0"
              strokeWidth={2}
              dot={false}
              name="Monitorista"
              strokeDasharray="4 4"
            />
          </LineChart>
        </ResponsiveContainer>

        <div className="mt-3 flex gap-5 text-[12px] text-neutral-500">
          <span className="flex items-center gap-1.5">
            <span
              className="h-0.5 w-4"
              style={{ backgroundColor: COLOR.accent }}
            />{" "}
            Agente
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="h-0.5 w-4"
              style={{ backgroundColor: "#B0B0B0" }}
            />{" "}
            Monitorista
          </span>
        </div>
      </Card>
    </div>
  );
}
