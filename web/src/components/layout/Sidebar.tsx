import type { NavKey } from "../../types/dashboard";
import { NAV } from "../../constants/navigation";
import { COLOR } from "../../constants/theme";

interface SidebarProps {
  activeSection: NavKey;
  onSelectSection: (key: NavKey) => void;
}

export function Sidebar({ activeSection, onSelectSection }: SidebarProps) {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-neutral-200 bg-white px-3 py-5">
      <div className="mb-6 flex items-center gap-2 px-2">
        <div
          className="flex h-7 w-7 items-center justify-center rounded-md"
          style={{ backgroundColor: COLOR.accent }}
        >
          <span className="text-[13px] font-semibold text-white">N</span>
        </div>
        <span className="text-[15px] font-semibold text-neutral-900">
          NextWave
        </span>
      </div>

      <nav className="flex flex-col gap-0.5">
        {NAV.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onSelectSection(item.key)}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[14px] transition-colors ${
                isActive
                  ? "bg-neutral-100 font-medium text-neutral-900"
                  : "text-neutral-500 hover:bg-neutral-50"
              }`}
            >
              <Icon size={16} />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
