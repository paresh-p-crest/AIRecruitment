"use client";

import { Briefcase, Eye, Loader2, Mail, Play, RefreshCw, Target, Trash2, User } from "lucide-react";
import { JobContextSelector } from "@/components/JobContextSelector";
import { useDialog } from "@/components/DialogProvider";
import type { MatchResultDetail, ResumeListItem } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

interface CandidateScoresTableProps {
  candidates: ResumeListItem[];
  matchResults: MatchResultDetail[];
  selectedId: number | null;
  runningAll?: boolean;
  runningId?: number | null;
  deletingId?: number | null;
  resetting?: boolean;
  loading?: boolean;
  disabled?: boolean;
  selectedJobId?: number | null;
  onJobChange?: (jobId: number, jobTitle: string) => void;
  onView: (candidate: ResumeListItem) => void;
  onDelete: (candidateId: number, listId?: number) => void;
  onResetAll?: () => void;
  onRefresh: () => void;
  onRunAll: (rematchAll?: boolean) => void;
  onRunOne: (resumeId: number) => void;
}

function scoreBadgeClass(score: number): string {
  if (score >= 85) return "text-emerald-300 bg-emerald-500/15 ring-emerald-500/30";
  if (score >= 70) return "text-brand-200 bg-brand-500/15 ring-brand-500/30";
  if (score >= 55) return "text-amber-200 bg-amber-500/15 ring-amber-500/30";
  return "text-red-300 bg-red-500/15 ring-red-500/30";
}

export function CandidateScoresTable({
  candidates,
  matchResults,
  selectedId,
  runningAll,
  runningId,
  deletingId,
  resetting,
  loading,
  disabled,
  selectedJobId,
  onJobChange,
  onView,
  onDelete,
  onResetAll,
  onRefresh,
  onRunAll,
  onRunOne,
}: CandidateScoresTableProps) {
  const { confirm } = useDialog();
  const matchByResumeId = new Map(matchResults.map((m) => [m.resume_id, m]));

  const rows = candidates.map((candidate) => ({
    candidate,
    match: matchByResumeId.get(candidate.resume_id ?? candidate.id) ?? null,
  }));

  const ranked = [...rows].sort((a, b) => {
    const scoreA = a.match?.final_score ?? a.candidate.match_score ?? -1;
    const scoreB = b.match?.final_score ?? b.candidate.match_score ?? -1;
    return scoreB - scoreA;
  });

  const unmatchedCount = rows.filter((row) => !row.match).length;
  const matchedCount = rows.length - unmatchedCount;

  const handleRematchAll = async () => {
    const confirmed = await confirm({
      title: "Rematch all candidates?",
      message: `Recalculate scores for all ${matchedCount} matched candidate${
        matchedCount !== 1 ? "s" : ""
      }? This replaces existing match results for the selected job.`,
      confirmLabel: "Rematch all",
      variant: "danger",
    });
    if (confirmed) onRunAll(true);
  };

  const handleResetAll = async () => {
    const confirmed = await confirm({
      title: "Delete all candidates?",
      message:
        "Delete every candidate, resume, and match result? This permanently clears the demo database.",
      confirmLabel: "Delete all",
      variant: "danger",
    });
    if (confirmed) onResetAll?.();
  };

  const handleDelete = async (e: React.MouseEvent, candidate: ResumeListItem) => {
    e.stopPropagation();
    const label = candidate.candidate_name ?? candidate.candidate_email ?? "this candidate";
    const confirmed = await confirm({
      title: "Delete candidate?",
      message: `Delete "${label}" and release their email for new uploads? This cannot be undone.`,
      confirmLabel: "Delete",
      variant: "danger",
    });
    if (confirmed) onDelete(candidate.candidate_id, candidate.id);
  };

  return (
    <div>
      {onJobChange && (
        <JobContextSelector
          selectedJobId={selectedJobId ?? null}
          onJobChange={onJobChange}
          disabled={disabled}
          className="mb-4"
          matchableOnly
        />
      )}

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-display text-xl font-semibold text-white">Candidates</h2>
          <p className="mt-1 text-sm text-slate-400">
            {candidates.length} candidate{candidates.length !== 1 ? "s" : ""} · ranked by job match
            score
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            Browse profiles, run matching, and open full details below
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {candidates.length > 0 && onResetAll && (
            <button
              type="button"
              onClick={handleResetAll}
              disabled={resetting || loading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-500/20 disabled:opacity-50"
            >
              {resetting ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              Delete all
            </button>
          )}
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-white/10 hover:text-white disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh
          </button>
          {matchedCount > 0 && (
            <button
              type="button"
              onClick={handleRematchAll}
              disabled={disabled || runningAll || candidates.length === 0}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-white/10 hover:text-white disabled:opacity-50"
            >
              {runningAll ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Rematch all
            </button>
          )}
          <button
            type="button"
            onClick={() => onRunAll(false)}
            disabled={disabled || runningAll || candidates.length === 0 || unmatchedCount === 0}
            title={
              unmatchedCount === 0
                ? "All candidates already matched for this job"
                : undefined
            }
            className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-400 disabled:opacity-50"
          >
            {runningAll ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            Match all
          </button>
        </div>
      </div>

      {loading && candidates.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
          <RefreshCw className="mb-3 h-8 w-8 animate-spin opacity-40" />
          <p className="text-sm">Loading candidates…</p>
        </div>
      )}

      {!loading && candidates.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 py-16 text-center">
          <User className="mb-3 h-10 w-10 text-slate-600" />
          <p className="text-sm font-medium text-slate-400">No candidates yet</p>
          <p className="mt-1 max-w-[240px] text-xs text-slate-500">
            Go to the Upload tab to add resumes
          </p>
        </div>
      )}

      {candidates.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-2 py-2 font-medium">Rank</th>
                <th className="px-2 py-2 font-medium">Candidate</th>
                <th className="px-2 py-2 font-medium">Email</th>
                <th className="px-2 py-2 font-medium">Match</th>
                <th className="px-2 py-2 font-medium">Yrs exp</th>
                <th className="px-2 py-2 font-medium">Skills</th>
                <th className="px-2 py-2 font-medium">Added</th>
                <th className="px-2 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map(({ candidate, match }) => {
                const isSelected = selectedId === candidate.id;
                const isRunning =
                  candidate.resume_id != null && runningId === candidate.resume_id;
                const isDeleting = deletingId === candidate.id;
                const skills = match?.component_scores?.skills;
                const displayScore =
                  match?.final_score ?? candidate.match_score ?? null;
                const displayRank = match?.rank ?? candidate.match_rank ?? null;

                return (
                  <tr
                    key={candidate.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => onView(candidate)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onView(candidate);
                      }
                    }}
                    className={cn(
                      "cursor-pointer border-b border-white/5 transition",
                      isSelected
                        ? "bg-brand-500/10 ring-1 ring-inset ring-brand-500/30"
                        : "hover:bg-white/[0.03]"
                    )}
                  >
                    <td className="px-2 py-3 text-slate-400">
                      {displayRank != null ? `#${displayRank}` : "—"}
                    </td>
                    <td className="px-2 py-3">
                      <p className="font-medium text-white">
                        {candidate.candidate_name ?? candidate.filename}
                      </p>
                      {!candidate.has_resume && (
                        <p className="mt-0.5 text-xs text-amber-400/90">No resume file</p>
                      )}
                    </td>
                    <td className="max-w-[200px] truncate px-2 py-3 text-slate-400">
                      {candidate.candidate_email ? (
                        <span className="inline-flex items-center gap-1">
                          <Mail className="h-3 w-3 shrink-0" />
                          {candidate.candidate_email}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-2 py-3">
                      {displayScore != null ? (
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1",
                            scoreBadgeClass(displayScore)
                          )}
                        >
                          <Target className="h-3 w-3" />
                          {displayScore.toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500">Not matched</span>
                      )}
                    </td>
                    <td className="px-2 py-3 text-slate-400">
                      {candidate.total_years_of_experience != null ? (
                        <span className="inline-flex items-center gap-1">
                          <Briefcase className="h-3 w-3" />
                          {candidate.total_years_of_experience}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-2 py-3 text-slate-400">
                      {skills != null ? `${skills.toFixed(0)}%` : "—"}
                    </td>
                    <td className="whitespace-nowrap px-2 py-3 text-xs text-slate-500">
                      {formatDate(candidate.created_at)}
                    </td>
                    <td className="px-2 py-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <button
                          type="button"
                          title="View candidate detail"
                          onClick={(e) => {
                            e.stopPropagation();
                            onView(candidate);
                          }}
                          className="inline-flex items-center gap-1 rounded-md border border-brand-500/30 bg-brand-500/10 px-2 py-1 text-xs font-medium text-brand-200 hover:bg-brand-500/20"
                        >
                          <Eye className="h-3 w-3" />
                          View
                        </button>
                        <button
                          type="button"
                          title="Run match for this candidate"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (candidate.resume_id) onRunOne(candidate.resume_id);
                          }}
                            disabled={
                              disabled ||
                              runningAll ||
                              isRunning ||
                              !candidate.resume_id
                            }
                          className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-50"
                        >
                          {isRunning ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Play className="h-3 w-3" />
                          )}
                          Match
                        </button>
                        <button
                          type="button"
                          title="Delete candidate"
                          onClick={(e) => handleDelete(e, candidate)}
                          disabled={isDeleting}
                          className="inline-flex items-center rounded-md border border-white/10 p-1 text-slate-500 hover:border-red-500/30 hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
                        >
                          {isDeleting ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
