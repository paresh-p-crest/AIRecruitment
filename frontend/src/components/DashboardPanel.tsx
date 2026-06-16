"use client";

import {
  Activity,
  Briefcase,
  FileText,
  Layers,
  Target,
  Users,
} from "lucide-react";
import type { DashboardSnapshot } from "@/lib/api";
import { cn } from "@/lib/utils";

interface DashboardPanelProps {
  data: DashboardSnapshot | null;
  loading: boolean;
  disabled?: boolean;
  onGoToTab?: (tab: "upload" | "job" | "matching" | "candidates") => void;
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: typeof Users;
  tone?: "default" | "success" | "warn";
}) {
  return (
    <div className="app-surface-card">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {label}
        </span>
        <Icon
          className={cn(
            "h-4 w-4",
            tone === "success" && "text-emerald-400",
            tone === "warn" && "text-amber-400",
            tone === "default" && "text-brand-400"
          )}
        />
      </div>
      <p className="text-2xl font-semibold text-white">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function DashboardPanel({
  data,
  loading,
  disabled,
  onGoToTab,
}: DashboardPanelProps) {
  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="app-surface-card h-24 animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <p className="text-sm text-slate-500">
        {disabled ? "Connect the API to load the dashboard." : "Dashboard unavailable."}
      </p>
    );
  }

  const docBackends = Object.entries(data.doc_extraction_backends)
    .filter(([, on]) => on)
    .map(([name]) => name.replace("_", " "))
    .join(", ");

  const fileSummary = ["pdf", "doc", "docx"]
    .map((ext) => `${ext.toUpperCase()}: ${data.file_types[ext] ?? 0}`)
    .join(" · ");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Recruitment pipeline</h2>
        <p className="mt-1 text-sm text-slate-400">
          Live snapshot — SQLite storage, local doc parsing, chunked LLM extraction for long resumes.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label="Candidates"
          value={data.total_candidates}
          hint={`${data.matched_candidates} matched · ${data.unmatched_candidates} awaiting match`}
          icon={Users}
        />
        <StatCard
          label="Avg match score"
          value={data.avg_match_score != null ? `${data.avg_match_score}%` : "—"}
          hint={data.matched_candidates > 0 ? "Across ranked candidates" : "Run matching to populate"}
          icon={Target}
          tone={data.matched_candidates > 0 ? "success" : "default"}
        />
        <StatCard
          label="Avg experience"
          value={
            data.avg_years_experience != null
              ? `${data.avg_years_experience} yrs`
              : "—"
          }
          hint="From extracted work history"
          icon={Briefcase}
        />
        <StatCard
          label="Job description"
          value={data.active_job_title ?? (data.job_description_valid ? "Ready" : "Incomplete")}
          hint={
            data.job_posting_count > 1
              ? `${data.job_posting_count} postings · active job scores shown`
              : data.job_description_valid
                ? "Valid for matching"
                : "Add skills or requirements on Job tab"
          }
          icon={FileText}
          tone={data.job_description_valid ? "success" : "warn"}
        />
        <StatCard
          label="Resume formats"
          value={fileSummary}
          hint="Uploaded default resumes"
          icon={Layers}
        />
        <StatCard
          label="Extraction"
          value={
            data.extraction_chunking_enabled
              ? `Chunked >${Math.round(data.extraction_chunk_threshold / 1000)}k chars`
              : "Single pass"
          }
          hint={docBackends ? `.doc backends: ${docBackends}` : "Install office-oxide for .doc"}
          icon={Activity}
        />
      </div>

      {data.archive_doc_files != null && (
        <p className="text-xs text-slate-500">
          Archive folder: {data.archive_doc_files} sample .doc/.docx files available for local parsing tests.
        </p>
      )}

      {data.top_matches.length > 0 && (
        <div className="app-surface-card">
          <h3 className="mb-3 text-sm font-medium text-slate-300">Top matches</h3>
          <ul className="space-y-2">
            {data.top_matches.map((match) => (
              <li
                key={`${match.resume_id}-${match.rank}`}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="truncate text-slate-300">
                  {match.rank != null && (
                    <span className="mr-2 text-slate-500">#{match.rank}</span>
                  )}
                  {match.candidate_name || match.filename || `Resume ${match.resume_id}`}
                </span>
                <span className="shrink-0 font-medium text-brand-300">
                  {match.final_score}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {onGoToTab && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onGoToTab("upload")}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
          >
            Upload resumes
          </button>
          <button
            type="button"
            onClick={() => onGoToTab("job")}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
          >
            Edit job description
          </button>
          <button
            type="button"
            onClick={() => onGoToTab("matching")}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
          >
            Run matching
          </button>
          <button
            type="button"
            onClick={() => onGoToTab("candidates")}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
          >
            View candidates
          </button>
        </div>
      )}
    </div>
  );
}
