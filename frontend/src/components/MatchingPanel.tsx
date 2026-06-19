"use client";

import { useMemo, useState } from "react";
import {
  Clock,
  Loader2,
  Mail,
  Play,
  RefreshCw,
  Target,
  Trophy,
  User,
} from "lucide-react";
import { JobContextSelector } from "@/components/JobContextSelector";
import { MatchScoreBreakdown } from "@/components/MatchScoreBreakdown";
import { type MatchResultDetail, type ResumeListItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface MatchingPanelProps {
  disabled?: boolean;
  candidates: ResumeListItem[];
  matchResults: MatchResultDetail[];
  resultsLoading?: boolean;
  selectedJobId: number | null;
  onJobChange: (jobId: number, jobTitle: string) => void;
  onSelectCandidate?: (resumeId: number) => void;
  onRunOne?: (resumeId: number) => void;
  runningId?: number | null;
  runningAll?: boolean;
  onRefreshResults?: () => void;
}

function scoreColor(score: number): string {
  if (score >= 85) return "text-emerald-300 bg-emerald-500/15 ring-emerald-500/30";
  if (score >= 70) return "text-brand-200 bg-brand-500/15 ring-brand-500/30";
  if (score >= 55) return "text-amber-200 bg-amber-500/15 ring-amber-500/30";
  return "text-red-300 bg-red-500/15 ring-red-500/30";
}

function resumeKey(candidate: ResumeListItem): number {
  return candidate.resume_id ?? candidate.id;
}

export function MatchingPanel({
  disabled,
  candidates,
  matchResults,
  resultsLoading,
  selectedJobId,
  onJobChange,
  onSelectCandidate,
  onRunOne,
  runningId,
  runningAll,
  onRefreshResults,
}: MatchingPanelProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const running = Boolean(runningAll);

  const results = matchResults;

  const matchByResumeId = useMemo(
    () => new Map(results.map((m) => [m.resume_id, m])),
    [results]
  );

  const unmatchedCandidates = useMemo(
    () => candidates.filter((c) => !matchByResumeId.has(resumeKey(c))),
    [candidates, matchByResumeId]
  );

  const matchedCount = candidates.length - unmatchedCandidates.length;
  const unmatchedCount = unmatchedCandidates.length;

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      <JobContextSelector
        selectedJobId={selectedJobId}
        onJobChange={onJobChange}
        disabled={disabled}
        matchableOnly
      />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-display text-2xl font-semibold text-white">Match Summary</h2>
          <p className="mt-1 max-w-xl text-sm text-slate-400">
            Review ranked scores and who still needs matching. Run Match all or Rematch all from the
            Candidates tab.
          </p>
          {candidates.length > 0 && (
            <p className="mt-2 text-xs text-slate-500">
              {matchedCount} matched · {unmatchedCount} awaiting match
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={onRefreshResults}
            disabled={resultsLoading || running || !selectedJobId}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", resultsLoading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {candidates.length === 0 && (
        <p className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-200">
          Upload at least one resume before running matching.
        </p>
      )}

      {running && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-white/10 py-16 text-slate-400">
          <Loader2 className="mb-3 h-10 w-10 animate-spin text-brand-400" />
          <p className="font-medium text-white">Matching candidates…</p>
          <p className="mt-1 text-sm">Computing scores and generating AI analysis</p>
        </div>
      )}

      {!running && resultsLoading && candidates.length === 0 && (
        <div className="flex justify-center py-16 text-slate-500">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      )}

      {!running && !resultsLoading && candidates.length > 0 && (
        <div className="scrollbar-thin min-h-0 flex-1 space-y-6 overflow-y-auto pr-1">
          {unmatchedCandidates.length > 0 && (
            <section>
              <div className="mb-3 flex items-center gap-2">
                <Clock className="h-4 w-4 text-amber-400" />
                <h3 className="text-sm font-semibold text-white">
                  Awaiting match ({unmatchedCandidates.length})
                </h3>
              </div>
              <div className="space-y-2">
                {unmatchedCandidates.map((candidate) => {
                  const rid = resumeKey(candidate);
                  const isRunning = runningId === rid;
                  return (
                    <div
                      key={candidate.id}
                      className="flex items-center gap-4 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-800 text-slate-400">
                        <User className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <button
                          type="button"
                          onClick={() => onSelectCandidate?.(rid)}
                          className="font-medium text-white hover:text-brand-200"
                        >
                          {candidate.candidate_name ?? candidate.filename}
                        </button>
                        {candidate.candidate_email && (
                          <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-slate-400">
                            <Mail className="h-3 w-3 shrink-0" />
                            {candidate.candidate_email}
                          </p>
                        )}
                        <p className="mt-1 text-xs text-amber-200/80">Not matched for this job</p>
                      </div>
                      {onRunOne && (
                        <button
                          type="button"
                          onClick={() => onRunOne(rid)}
                          disabled={disabled || isRunning || running}
                          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-brand-500/30 bg-brand-500/10 px-3 py-1.5 text-xs font-medium text-brand-200 hover:bg-brand-500/20 disabled:opacity-50"
                        >
                          {isRunning ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                          Match
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {results.length > 0 && (
            <section>
              <div className="mb-3 flex items-center gap-2">
                <Trophy className="h-4 w-4 text-brand-400" />
                <h3 className="text-sm font-semibold text-white">
                  Ranked results ({results.length})
                </h3>
              </div>
              <div className="space-y-3">
                {results.map((result) => {
                  const expanded = expandedId === result.resume_id;
                  return (
                    <div
                      key={result.resume_id}
                      className="rounded-xl border border-white/10 bg-white/[0.03] transition hover:border-brand-500/30"
                    >
                      <div className="flex items-start gap-4 p-4">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-800 text-sm font-bold text-slate-300">
                          {result.rank ? (
                            result.rank <= 3 ? (
                              <Trophy className="h-4 w-4 text-amber-400" />
                            ) : (
                              `#${result.rank}`
                            )
                          ) : (
                            "—"
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={() => onSelectCandidate?.(result.resume_id)}
                              className="font-medium text-white hover:text-brand-200"
                            >
                              {result.candidate_name ?? result.filename ?? "Candidate"}
                            </button>
                            <span
                              className={cn(
                                "rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1",
                                scoreColor(result.final_score)
                              )}
                            >
                              {result.final_score.toFixed(0)}% match
                            </span>
                          </div>

                          {result.component_breakdown?.length > 0 && (
                            <div className="mt-3 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                              {result.component_breakdown.map((item) => (
                                <div
                                  key={item.key}
                                  className="flex items-center justify-between rounded-md bg-slate-900/60 px-2 py-1 text-xs"
                                >
                                  <span className="truncate text-slate-400">{item.label}</span>
                                  <span className="ml-2 shrink-0 font-medium text-slate-200">
                                    {item.score.toFixed(0)}%
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}

                          {result.summary && (
                            <p className="mt-2 line-clamp-2 text-sm text-slate-400">
                              {result.summary}
                            </p>
                          )}

                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedId(expanded ? null : result.resume_id)
                              }
                              className="text-xs font-medium text-brand-300 hover:text-brand-200"
                            >
                              {expanded ? "Hide breakdown" : "Show full breakdown"}
                            </button>
                            <button
                              type="button"
                              onClick={() => onSelectCandidate?.(result.resume_id)}
                              className="text-xs text-slate-500 hover:text-slate-300"
                            >
                              View candidate →
                            </button>
                          </div>
                        </div>
                      </div>

                      {expanded && result.component_breakdown?.length > 0 && (
                        <div className="border-t border-white/10 px-4 pb-4 pt-2">
                          <MatchScoreBreakdown match={result} compact />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {unmatchedCandidates.length === 0 && results.length === 0 && (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 py-16 text-center">
              <Target className="mb-3 h-10 w-10 text-slate-600" />
              <p className="text-sm font-medium text-slate-400">No match results yet</p>
              <p className="mt-1 max-w-sm text-xs text-slate-500">
                Click Match all to score candidates against the selected job.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
