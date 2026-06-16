"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Settings, Wifi, WifiOff } from "lucide-react";
import { ActiveProviderBadge } from "@/components/ActiveProviderBadge";
import { ThemeToggle } from "@/components/ThemeToggle";
import type { LlmProvider } from "@/lib/api";
import { cn } from "@/lib/utils";

interface HeaderProps {
  apiOnline: boolean;
  activeProvider?: LlmProvider | null;
  activeModel?: string | null;
}

export function Header({ apiOnline, activeProvider, activeModel }: HeaderProps) {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/90 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-[1800px] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="flex min-w-0 shrink-0 items-center gap-3 transition hover:opacity-90"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 shadow-glow">
            <Brain className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0 text-left">
            <h1 className="font-display text-lg font-semibold tracking-tight text-white sm:text-xl">
              SliceHRMS
            </h1>
            <p className="truncate text-xs text-slate-400 sm:text-sm">AI Recruitment Assistant</p>
          </div>
        </Link>

        <div className="flex shrink-0 items-center justify-end gap-2 sm:gap-3">
          {activeProvider && activeModel && apiOnline && (
            <ActiveProviderBadge
              provider={activeProvider}
              model={activeModel}
              size="sm"
              className="hidden lg:inline-flex"
            />
          )}

          <div
            className={cn(
              "flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium whitespace-nowrap",
              apiOnline
                ? "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/30"
                : "bg-red-500/10 text-red-400 ring-1 ring-red-500/30"
            )}
          >
            {apiOnline ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">API {apiOnline ? "Connected" : "Offline"}</span>
            <span className="sm:hidden">{apiOnline ? "Online" : "Offline"}</span>
          </div>

          <ThemeToggle />

          <Link
            href="/settings"
            className={cn(
              "flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium whitespace-nowrap transition",
              pathname === "/settings"
                ? "border-brand-500/50 bg-brand-500/15 text-brand-200"
                : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white"
            )}
          >
            <Settings className="h-4 w-4" />
            <span className="hidden sm:inline">Settings</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
