import { useState } from "react";
import { Play, Pause } from "lucide-react";
import type { Call } from "../../types/dashboard";
import { calls as defaultCalls } from "../../data/mockData";

interface LlamadasSectionProps {
  calls?: Call[];
}

export function LlamadasSection({
  calls = defaultCalls,
}: LlamadasSectionProps) {
  const [playingId, setPlayingId] = useState<string | null>(null);

  const togglePlay = (id: string) => {
    setPlayingId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="flex flex-col bg-white rounded-xl border border-neutral-200 p-4 shadow-sm">
      {calls.map((c, i) => {
        const isPlaying = playingId === c.id;
        return (
          <div
            key={c.id}
            className={`flex items-center gap-4 py-3.5 ${
              i !== calls.length - 1 ? "border-b border-neutral-200" : ""
            }`}
          >
            <button
              onClick={() => togglePlay(c.id)}
              className="flex h-8 w-8 items-center justify-center rounded-full border border-neutral-200 text-neutral-500 hover:border-neutral-300 transition-colors"
              aria-label={isPlaying ? "Pausar llamada" : "Reproducir llamada"}
            >
              {isPlaying ? (
                <Pause size={13} />
              ) : (
                <Play size={13} className="ml-0.5" />
              )}
            </button>

            <div className="flex-1">
              <p className="text-[14px] font-medium text-neutral-900">
                {c.conductor}
              </p>
              <p className="text-[13px] text-neutral-500">{c.patente}</p>
            </div>

            <p
              className={`text-[13px] ${
                c.resultado === "Contestó"
                  ? "text-neutral-600"
                  : "text-neutral-400"
              }`}
            >
              {c.resultado}
            </p>

            <p className="w-12 text-right text-[13px] text-neutral-400 tabular-nums">
              {c.duracion}
            </p>
            <p className="w-12 text-right text-[13px] text-neutral-400 tabular-nums">
              {c.hora}
            </p>
          </div>
        );
      })}
    </div>
  );
}
