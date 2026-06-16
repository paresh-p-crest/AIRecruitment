"use client";

import type { ComponentScoreBreakdown, MatchResultDetail } from "@/lib/api";
import { cn } from "@/lib/utils";

function barColor(score: number): string {
  if (score >= 85) return "bg-emerald-500";
  if (score >= 70) return "bg-brand-500";
  if (score >= 55) return "bg-amber-500";
  return "bg-red-500";
}

function ScoreRow({ item }: { item: ComponentScoreBreakdown }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="text-slate-300">
          {item.label}{" "}
          <span className="text-slate-500">({item.weight_percent}% weight)</span>
        </span>
        <span className="shrink-0 font-medium text-white">
          {item.score.toFixed(0)}%
          <span className="ml-2 text-xs text-brand-300">
            → {item.weighted_points.toFixed(1)} pts
          </span>
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className={cn("h-full rounded-full transition-all", barColor(item.score))}
          style={{ width: `${Math.min(100, item.score)}%` }}
        />
      </div>
    </div>
  );
}

interface MatchScoreBreakdownProps {
  match: MatchResultDetail;
  compact?: boolean;
}

export function MatchScoreBreakdown({ match, compact }: MatchScoreBreakdownProps) {
  return (
    <div className={cn("space-y-4", compact && "space-y-3")}>
      <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
          PRD scoring breakdown
        </p>
        <div className="space-y-4">
          {match.component_breakdown.map((item) => (
            <ScoreRow key={item.key} item={item} />
          ))}
        </div>

        <div className="mt-4 space-y-1 border-t border-white/10 pt-3 text-sm">
          <div className="flex justify-between text-slate-400">
            <span>Weighted subtotal</span>
            <span className="font-medium text-slate-200">
              {match.subtotal_score.toFixed(1)} / 100
            </span>
          </div>
          {match.red_flag_penalty > 0 && (
            <div className="flex justify-between text-red-300">
              <span>Red-flag penalty</span>
              <span className="font-medium">−{match.red_flag_penalty.toFixed(1)}</span>
            </div>
          )}
          <div className="flex justify-between font-semibold text-white">
            <span>Final match score</span>
            <span className="text-brand-200">{match.final_score.toFixed(1)} / 100</span>
          </div>
        </div>
      </div>

      {match.red_flags.length > 0 && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-red-300">
            Red flags
          </p>
          <ul className="space-y-2">
            {match.red_flags.map((flag) => (
              <li key={`${flag.type}-${flag.description}`} className="text-sm text-slate-300">
                <span className="font-medium text-red-200">
                  −{flag.penalty.toFixed(0)}%
                </span>{" "}
                {flag.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
