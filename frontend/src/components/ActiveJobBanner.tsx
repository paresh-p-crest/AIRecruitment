"use client";

import { Briefcase } from "lucide-react";
import { cn } from "@/lib/utils";

interface ActiveJobBannerProps {
  jobId?: number | null;
  jobTitle?: string | null;
  matchCount?: number;
  className?: string;
  compact?: boolean;
}

export function ActiveJobBanner({
  jobId,
  jobTitle,
  matchCount,
  className,
  compact,
}: ActiveJobBannerProps) {
  if (!jobTitle) return null;

  const label = jobTitle.length > 64 ? `${jobTitle.slice(0, 63)}…` : jobTitle;

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border border-brand-500/25 bg-brand-500/10 px-4 py-3 text-sm text-brand-100",
        className
      )}
    >
      <Briefcase className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" />
      <div className="min-w-0">
        <p className="font-medium text-white">
          {compact ? "Matching against: " : "Active job for matching"}
        </p>
        <p className="truncate text-brand-100">
          {label}
          {jobId != null && (
            <span className="ml-2 text-xs text-brand-300/80">#{jobId}</span>
          )}
        </p>
        {!compact && matchCount != null && (
          <p className="app-help-text mt-1">
            {matchCount} stored match{matchCount === 1 ? "" : "es"} for this job · candidates are
            shared across all jobs
          </p>
        )}
      </div>
    </div>
  );
}
