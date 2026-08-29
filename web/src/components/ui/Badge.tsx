import React from "react";

interface BadgeProps {
  color: string;
  children: React.ReactNode;
}

export function Badge({ color, children }: BadgeProps) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide"
      style={{ backgroundColor: `${color}1A`, color }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {children}
    </span>
  );
}
