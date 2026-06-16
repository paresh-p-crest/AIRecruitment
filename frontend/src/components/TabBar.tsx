"use client";

import { cn } from "@/lib/utils";

export type HomeTabId = "dashboard" | "upload" | "job" | "search" | "matching" | "candidates";

interface TabBarProps<T extends string> {
  tabs: { id: T; label: string; count?: number; badge?: string }[];
  active: T;
  onChange: (id: T) => void;
}

export function TabBar<T extends string>({ tabs, active, onChange }: TabBarProps<T>) {
  return (
    <div className="app-tab-bar flex gap-1 rounded-xl border border-white/10 bg-slate-900/60 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={cn(
            "relative flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition sm:flex-none sm:px-6",
            active === tab.id
              ? "bg-brand-500 text-white shadow-glow"
              : "app-tab-inactive text-slate-400 hover:bg-white/5 hover:text-white"
          )}
        >
          {tab.label}
          {tab.badge && (
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                active === tab.id
                  ? "bg-white/25 text-white"
                  : "bg-brand-500/20 text-brand-300"
              )}
            >
              {tab.badge}
            </span>
          )}
          {tab.count != null && tab.count > 0 && (
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-xs",
                active === tab.id
                  ? "bg-white/20 text-white"
                  : "bg-slate-800 text-slate-400"
              )}
            >
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
