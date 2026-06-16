"use client";

import { Briefcase, Mail, RefreshCw, Target, Trash2, User } from "lucide-react";
import { useDialog } from "@/components/DialogProvider";
import type { ResumeListItem } from "@/lib/api";
import { cn, formatDate, initials } from "@/lib/utils";

interface CandidateListProps {
  candidates: ResumeListItem[];
  selectedId: number | null;
  onSelect: (candidate: ResumeListItem) => void;
  onDelete: (candidateId: number, listId?: number) => void;
  onResetAll?: () => void;
  onRefresh: () => void;
  deletingId?: number | null;
  resetting?: boolean;
  loading?: boolean;
}

export function CandidateList({
  candidates,
  selectedId,
  onSelect,
  onDelete,
  onResetAll,
  onRefresh,
  deletingId,
  resetting,
  loading,
}: CandidateListProps) {
  const { confirm } = useDialog();

  const handleDelete = async (
    e: React.MouseEvent,
    candidate: ResumeListItem
  ) => {
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

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-4 flex shrink-0 items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-xl font-semibold text-white">Candidates</h2>
          <p className="mt-1 text-sm text-slate-400">
            {candidates.length} candidate{candidates.length !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {candidates.length > 0 && onResetAll && (
            <button
              type="button"
              onClick={handleResetAll}
              disabled={resetting || loading}
              className="flex items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-500/20 disabled:opacity-50"
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
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-white/10 hover:text-white disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
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
            <p className="mt-1 max-w-[200px] text-xs text-slate-500">
              Go to the Upload tab to add a resume
            </p>
          </div>
        )}

        {candidates.map((candidate) => (
          <div
            key={`${candidate.candidate_id}-${candidate.id}`}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(candidate)}
            onKeyDown={(e) => e.key === "Enter" && onSelect(candidate)}
            className={cn(
              "group w-full cursor-pointer rounded-xl border p-4 text-left transition-all duration-150",
              selectedId === candidate.id
                ? "border-brand-500/60 bg-brand-500/10 shadow-glow"
                : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]"
            )}
          >
            <div className="flex items-start gap-3">
              <div
                className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold",
                  selectedId === candidate.id
                    ? "bg-brand-500 text-white"
                    : "bg-slate-800 text-slate-300"
                )}
              >
                {initials(candidate.candidate_name)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-white">
                  {candidate.candidate_name ?? "Unknown Candidate"}
                </p>
                {candidate.candidate_email && (
                  <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-slate-400">
                    <Mail className="h-3 w-3 shrink-0" />
                    {candidate.candidate_email}
                  </p>
                )}
                {!candidate.has_resume && (
                  <p className="mt-1 text-xs text-amber-400/90">No resume file attached</p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {candidate.match_score != null && (
                    <span className="inline-flex items-center gap-1 rounded-md bg-brand-500/15 px-2 py-0.5 text-xs font-medium text-brand-200 ring-1 ring-brand-500/25">
                      <Target className="h-3 w-3" />
                      {Math.round(candidate.match_score)}% match
                      {candidate.match_rank != null && ` · #${candidate.match_rank}`}
                    </span>
                  )}
                  {candidate.total_years_of_experience != null && (
                    <span className="inline-flex items-center gap-1 rounded-md bg-slate-800/80 px-2 py-0.5 text-xs text-brand-300">
                      <Briefcase className="h-3 w-3" />
                      {candidate.total_years_of_experience} yrs exp
                    </span>
                  )}
                  <span className="text-xs text-slate-500">
                    {formatDate(candidate.created_at)}
                  </span>
                </div>
              </div>
              <button
                type="button"
                title="Delete candidate"
                onClick={(e) => handleDelete(e, candidate)}
                disabled={deletingId === candidate.id}
                className="shrink-0 rounded-lg p-2 text-slate-500 opacity-0 transition hover:bg-red-500/15 hover:text-red-400 group-hover:opacity-100 disabled:opacity-50"
              >
                {deletingId === candidate.id ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
