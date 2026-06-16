"use client";

import Link from "next/link";
import { Copy, DollarSign, Home, Monitor, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export type SettingsSection = "llm" | "duplicate" | "appearance" | "pricing";

const NAV_ITEMS: {
  id: SettingsSection;
  label: string;
  description: string;
  icon: React.ElementType;
}[] = [
  {
    id: "llm",
    label: "LLM Model",
    description: "Providers & API keys",
    icon: Sparkles,
  },
  {
    id: "pricing",
    label: "Model pricing",
    description: "Token cost & credits",
    icon: DollarSign,
  },
  {
    id: "duplicate",
    label: "Duplicate Detection",
    description: "Upload & profile rules",
    icon: Copy,
  },
  {
    id: "appearance",
    label: "Appearance",
    description: "Theme & display",
    icon: Monitor,
  },
];

interface SettingsNavProps {
  active: SettingsSection;
  onChange: (section: SettingsSection) => void;
}

function NavButton({
  item,
  active,
  onChange,
  className,
}: {
  item: (typeof NAV_ITEMS)[number];
  active: SettingsSection;
  onChange: (section: SettingsSection) => void;
  className?: string;
}) {
  const Icon = item.icon;
  const isActive = active === item.id;

  return (
    <button
      type="button"
      onClick={() => onChange(item.id)}
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border px-3 py-3 text-left transition",
        isActive
          ? "border-brand-500/40 bg-brand-500/15 text-white shadow-sm"
          : "border-transparent text-slate-400 hover:border-white/10 hover:bg-white/5 hover:text-slate-200",
        className
      )}
    >
      <Icon
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0",
          isActive ? "text-brand-300" : "text-slate-500"
        )}
      />
      <span className="min-w-0">
        <span className="block text-sm font-medium">{item.label}</span>
        <span className="mt-0.5 block text-xs text-slate-500">{item.description}</span>
      </span>
    </button>
  );
}

function HomeNavLink({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border border-transparent px-3 py-3 text-left transition hover:border-white/10 hover:bg-white/5",
        className
      )}
    >
      <Home className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-slate-300">Recruitment</span>
        <span className="mt-0.5 block text-xs text-slate-500">Back to home dashboard</span>
      </span>
    </Link>
  );
}

export function SettingsNav({ active, onChange }: SettingsNavProps) {
  return (
    <>
      <aside className="hidden w-64 shrink-0 border-r border-white/10 bg-slate-950/40 lg:block">
        <div className="sticky top-[57px] flex h-[calc(100vh-57px)] flex-col p-4">
          <p className="mb-3 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Settings
          </p>
          <nav className="space-y-1">
            <HomeNavLink />
            <div className="my-2 border-t border-white/10" />
            {NAV_ITEMS.map((item) => (
              <NavButton
                key={item.id}
                item={item}
                active={active}
                onChange={onChange}
              />
            ))}
          </nav>
        </div>
      </aside>

      <div className="border-b border-white/10 bg-slate-950/40 px-4 py-3 lg:hidden">
        <div className="flex gap-2 overflow-x-auto">
          <HomeNavLink className="w-auto min-w-[180px] shrink-0" />
          {NAV_ITEMS.map((item) => (
            <NavButton
              key={item.id}
              item={item}
              active={active}
              onChange={onChange}
              className="w-auto min-w-[200px] shrink-0"
            />
          ))}
        </div>
      </div>
    </>
  );
}
