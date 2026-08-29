import type { NavKey } from "../../types/dashboard";
import { SECTION_TITLES } from "../../constants/navigation";
import { COLOR } from "../../constants/theme";

interface HeaderProps {
  section: NavKey;
  activeTripsCount?: number;
  accumulatedCostToday?: string;
  apiConnected?: boolean;
}

export function Header({
  section,
  activeTripsCount = 5,
  accumulatedCostToday = "$1.60",
  apiConnected = false,
}: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-neutral-200 bg-white px-8 py-4">
      <div>
        <h1 className="text-[20px] font-semibold text-neutral-900">
          {SECTION_TITLES[section]}
        </h1>
        <p className="text-[13px] text-neutral-500">
          Sábado 29 de agosto · {activeTripsCount} viajes activos
        </p>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: COLOR.success }}
          />
          <span className="text-[13px] text-neutral-600">
            {apiConnected ? "Backend conectado" : "Backend sin conexión"}
          </span>
        </div>

        <div className="text-right">
          <p className="text-[13px] text-neutral-500">Costo acumulado hoy</p>
          <p className="text-[15px] font-semibold text-neutral-900">
            {accumulatedCostToday}
          </p>
        </div>
      </div>
    </header>
  );
}
