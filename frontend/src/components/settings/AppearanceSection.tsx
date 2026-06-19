"use client";

import { CheckCircle2, Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/ThemeProvider";
import type { AppTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const THEME_OPTIONS: {
  id: AppTheme;
  label: string;
  description: string;
  icon: React.ElementType;
}[] = [
  {
    id: "dark",
    label: "Dark",
    description: "Default — easier on the eyes in low light",
    icon: Moon,
  },
  {
    id: "light",
    label: "Light",
    description: "Bright surfaces for well-lit environments",
    icon: Sun,
  },
];

export function AppearanceSection() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-semibold text-white">Appearance</h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">
          Choose how Easy AI Recruitment looks. Dark is the default; your choice is saved in this browser.
        </p>
      </div>

      <section className="glass rounded-2xl p-6 shadow-card">
        <h3 className="mb-4 flex items-center gap-2 font-display text-sm font-semibold uppercase tracking-wide text-brand-300">
          <Monitor className="h-4 w-4" />
          Theme
        </h3>

        <div className="grid gap-3 sm:grid-cols-2">
          {THEME_OPTIONS.map((option) => {
            const Icon = option.icon;
            const selected = theme === option.id;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => setTheme(option.id)}
                className={cn(
                  "flex items-start gap-3 rounded-xl border px-4 py-4 text-left transition",
                  selected
                    ? "border-brand-500/40 bg-brand-500/15 shadow-sm"
                    : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/5"
                )}
              >
                <Icon
                  className={cn(
                    "mt-0.5 h-5 w-5 shrink-0",
                    selected ? "text-brand-300" : "text-slate-500"
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 text-sm font-medium text-white">
                    {option.label}
                    {selected && <CheckCircle2 className="h-4 w-4 text-brand-400" />}
                  </span>
                  <span className="mt-1 block text-xs text-slate-400">{option.description}</span>
                </span>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
