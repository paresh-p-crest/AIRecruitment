"use client";

import {
  Activity,
  Briefcase,
  Code2,
  FileText,
  Layers,
  Target,
  Users,
} from "lucide-react";
import {
  ChartLegend,
  DonutChart,
  HorizontalBarChart,
  ScoreGauge,
  type ChartSegment,
} from "@/components/dashboard/DashboardCharts";
import type { DashboardSnapshot } from "@/lib/api";
import { cn } from "@/lib/utils";

interface DashboardPanelProps {
  data: DashboardSnapshot | null;
  loading: boolean;
  disabled?: boolean;
  onGoToTab?: (tab: "upload" | "job" | "matching" | "candidates") => void;
}

const MATCH_COLORS = {
  matched: "#34d399",
  unmatched: "#475569",
};

const SKILL_CHART_COLORS = [
  "#38bdf8",
  "#34d399",
  "#a78bfa",
  "#f472b6",
  "#fbbf24",
  "#fb7185",
  "#22d3ee",
  "#4ade80",
];

function StatRow({
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
    <div className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
      <div
        className={cn(
          "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
          tone === "success" && "bg-emerald-500/15 text-emerald-400",
          tone === "warn" && "bg-amber-500/15 text-amber-400",
          tone === "default" && "bg-brand-500/15 text-brand-300"
        )}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-0.5 text-lg font-semibold text-white">{value}</p>
        {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      </div>
    </div>
  );
}

function scoreBarColor(score: number): string {
  if (score >= 85) return "#34d399";
  if (score >= 70) return "#38bdf8";
  if (score >= 55) return "#fbbf24";
  return "#f87171";
}

export function DashboardPanel({
  data,
  loading,
  disabled,
  onGoToTab,
}: DashboardPanelProps) {
  if (loading) {
    return (
      <div className="grid gap-6 lg:grid-cols-[minmax(280px,340px)_1fr]">
        <div className="space-y-4">
          <div className="app-surface-card h-64 animate-pulse" />
          <div className="app-surface-card h-48 animate-pulse" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="app-surface-card h-20 animate-pulse" />
          ))}
        </div>
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

  const hasActiveJob = data.has_active_job;

  const matchSegments: ChartSegment[] = hasActiveJob
    ? [
        { label: "Matched", value: data.matched_candidates, color: MATCH_COLORS.matched },
        {
          label: "Awaiting match",
          value: data.unmatched_candidates,
          color: MATCH_COLORS.unmatched,
        },
      ]
    : [];

  const topScoreSegments: ChartSegment[] = data.top_matches.map((match) => ({
    label: match.candidate_name || match.filename || `Resume ${match.resume_id}`,
    value: match.final_score,
    color: scoreBarColor(match.final_score),
  }));

  const skillSegments: ChartSegment[] = data.top_skills.map((item, index) => ({
    label: item.skill,
    value: item.percent,
    color: SKILL_CHART_COLORS[index % SKILL_CHART_COLORS.length],
  }));

  const matchRate =
    hasActiveJob && data.total_candidates > 0
      ? Math.round((data.matched_candidates / data.total_candidates) * 100)
      : 0;

  const showMatchCoverage =
    hasActiveJob && data.total_candidates > 0 && data.matched_candidates + data.unmatched_candidates > 0;
  const showAvgScore =
    hasActiveJob && data.matched_candidates > 0 && data.avg_match_score != null;
  const showSkillsChart = data.total_candidates > 0 && skillSegments.length > 0;
  const showTopScoresChart =
    hasActiveJob && topScoreSegments.length > 0;
  const showLeftCharts =
    showMatchCoverage || showAvgScore || showSkillsChart || showTopScoresChart;

  const docBackends = Object.entries(data.doc_extraction_backends)
    .filter(([, on]) => on)
    .map(([name]) => name.replace("_", " "))
    .join(", ");

  const activeJobLabel = data.active_job_title ?? "No active job";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-xl font-semibold text-white">Recruitment pipeline</h2>
        <p className="mt-1 text-sm text-slate-400">
          {hasActiveJob ? (
            <>
              Match metrics for{" "}
              <span className="text-slate-200">{activeJobLabel}</span>
              {data.job_posting_count > 1 && ` · ${data.job_posting_count} job postings`}
            </>
          ) : (
            <>
              No active job for matching
              {data.job_posting_count > 0 &&
                ` · ${data.job_posting_count} saved posting${data.job_posting_count !== 1 ? "s" : ""}`}
            </>
          )}
        </p>
      </div>

      <div
        className={cn(
          "grid gap-6",
          showLeftCharts && "lg:grid-cols-[minmax(280px,340px)_1fr]"
        )}
      >
        {showLeftCharts && (
        <div className="space-y-4">
          {showMatchCoverage && (
          <section className="app-surface-card">
            <div className="mb-4">
              <h3 className="text-sm font-medium text-slate-300">Match coverage</h3>
              <p className="mt-1 text-xs text-slate-500">Scores for: {activeJobLabel}</p>
            </div>
            <div className="flex justify-center py-1">
              <DonutChart
                segments={matchSegments.filter((segment) => segment.value > 0)}
                centerValue={`${matchRate}%`}
                centerLabel="matched"
              />
            </div>
            <ChartLegend
              items={matchSegments}
              className="mt-4 border-t border-white/10 pt-4"
            />
          </section>
          )}

          {showAvgScore && (
          <section className="app-surface-card">
            <div className="mb-3">
              <h3 className="text-sm font-medium text-slate-300">Average match score</h3>
              <p className="mt-1 text-xs text-slate-500">For {activeJobLabel}</p>
            </div>
            <div className="flex justify-center py-2">
              <ScoreGauge score={data.avg_match_score} />
            </div>
            <p className="mt-2 text-center text-xs text-slate-500">
              Across {data.matched_candidates} ranked candidate
              {data.matched_candidates !== 1 ? "s" : ""}
            </p>
          </section>
          )}

          {showSkillsChart && (
          <section className="app-surface-card">
            <div className="mb-4">
              <h3 className="flex items-center gap-2 text-sm font-medium text-slate-300">
                <Code2 className="h-4 w-4 text-brand-400" />
                Top skills in talent pool
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                % of {data.total_candidates} candidate{data.total_candidates !== 1 ? "s" : ""} with
                each skill
              </p>
            </div>
            <HorizontalBarChart items={skillSegments} maxValue={100} valueSuffix="%" />
          </section>
          )}

          {showTopScoresChart && (
            <section className="app-surface-card lg:hidden">
              <h3 className="mb-1 text-sm font-medium text-slate-300">Top match scores</h3>
              <p className="mb-4 text-xs text-slate-500">{activeJobLabel}</p>
              <HorizontalBarChart items={topScoreSegments} maxValue={100} />
            </section>
          )}
        </div>
        )}

        <div className="space-y-4">
          <section className="app-surface-card space-y-3">
            <h3 className="text-sm font-medium text-slate-300">Pipeline details</h3>
            <StatRow
              label="Candidates"
              value={data.total_candidates}
              hint={
                hasActiveJob
                  ? `${data.matched_candidates} matched · ${data.unmatched_candidates} awaiting match`
                  : `${data.total_candidates} in talent pool`
              }
              icon={Users}
            />
            <StatRow
              label="Active job"
              value={
                hasActiveJob
                  ? (data.active_job_title ?? "Active")
                  : "None selected"
              }
              hint={
                hasActiveJob
                  ? data.job_description_valid
                    ? "Valid for matching"
                    : "Add skills or requirements on Job tab"
                  : "Set or disable active job on Job tab"
              }
              icon={FileText}
              tone={hasActiveJob ? (data.job_description_valid ? "success" : "warn") : "warn"}
            />
            <StatRow
              label="Avg experience"
              value={
                data.avg_years_experience != null ? `${data.avg_years_experience} yrs` : "—"
              }
              hint="From extracted work history"
              icon={Briefcase}
            />
            <StatRow
              label="Extraction mode"
              value={
                data.extraction_chunking_enabled
                  ? `Chunked >${Math.round(data.extraction_chunk_threshold / 1000)}k chars`
                  : "Single pass"
              }
              hint={docBackends ? `.doc backends: ${docBackends}` : "Install office-oxide for .doc"}
              icon={Activity}
            />
            <StatRow
              label="Resume files"
              value={Object.values(data.file_types).reduce((sum, n) => sum + n, 0)}
              hint={["pdf", "doc", "docx"]
                .map((ext) => `${ext.toUpperCase()}: ${data.file_types[ext] ?? 0}`)
                .join(" · ")}
              icon={Layers}
            />
          </section>

          {data.top_skills.length > 0 && (
            <section className="app-surface-card">
              <h3 className="mb-3 text-sm font-medium text-slate-300">Skill breakdown</h3>
              <ul className="space-y-2">
                {data.top_skills.map((item) => (
                  <li
                    key={item.skill}
                    className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm"
                  >
                    <span className="text-slate-300">{item.skill}</span>
                    <span className="shrink-0 text-slate-400">
                      {item.candidate_count} · {item.percent}%
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {showTopScoresChart ? (
            <section className="app-surface-card">
              <div className="mb-4 flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-medium text-slate-300">Top matches</h3>
                  <p className="mt-0.5 text-xs text-slate-500">{activeJobLabel}</p>
                </div>
                <Target className="h-4 w-4 text-brand-400" />
              </div>
              <div className="hidden lg:block">
                <HorizontalBarChart items={topScoreSegments} maxValue={100} />
              </div>
              <ul className="mt-4 space-y-2 border-t border-white/10 pt-4 lg:mt-0 lg:border-0 lg:pt-0">
                {data.top_matches.map((match) => (
                  <li
                    key={`${match.resume_id}-${match.rank}`}
                    className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm"
                  >
                    <span className="min-w-0 truncate text-slate-300">
                      {match.rank != null && (
                        <span className="mr-2 text-slate-500">#{match.rank}</span>
                      )}
                      {match.candidate_name || match.filename || `Resume ${match.resume_id}`}
                    </span>
                    <span
                      className="shrink-0 font-semibold"
                      style={{ color: scoreBarColor(match.final_score) }}
                    >
                      {match.final_score}%
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {data.archive_doc_files != null && (
            <p className="text-xs text-slate-500">
              Archive folder: {data.archive_doc_files} sample .doc/.docx files for local parsing
              tests.
            </p>
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
      </div>
    </div>
  );
}
