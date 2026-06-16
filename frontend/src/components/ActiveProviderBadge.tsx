"use client";

import { Cloud, KeyRound, Sparkles } from "lucide-react";
import type { LlmProvider } from "@/lib/api";
import { PROVIDER_META } from "@/lib/providers";
import { cn } from "@/lib/utils";

const ICONS = {
  aws_bedrock: Cloud,
  openai: KeyRound,
  google: Sparkles,
} as const;

interface ActiveProviderBadgeProps {
  provider: LlmProvider;
  model: string;
  size?: "sm" | "md";
  showModel?: boolean;
  className?: string;
}

export function ActiveProviderBadge({
  provider,
  model,
  size = "md",
  showModel = true,
  className,
}: ActiveProviderBadgeProps) {
  const meta = PROVIDER_META[provider];
  const Icon = ICONS[provider];

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full font-medium ring-1",
        meta.colorClass,
        meta.ringClass,
        size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
        className
      )}
      title={`Active LLM: ${meta.label}${showModel ? ` · ${model}` : ""}`}
    >
      <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      <span>{meta.label}</span>
      {showModel && (
        <>
          <span className="opacity-40">·</span>
          <span className="max-w-[140px] truncate opacity-90 sm:max-w-[200px]">{model}</span>
        </>
      )}
    </div>
  );
}
