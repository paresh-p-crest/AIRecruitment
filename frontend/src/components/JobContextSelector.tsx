"use client";

import { useCallback, useEffect, useState } from "react";
import { Briefcase, Loader2 } from "lucide-react";
import {
  formatJobListLabel,
  getJobDescription,
  listJobDescriptions,
  type JobDescriptionListItem,
} from "@/lib/api";

interface JobContextSelectorProps {
  selectedJobId: number | null;
  onJobChange: (jobId: number, jobTitle: string) => void;
  disabled?: boolean;
  className?: string;
  label?: string;
  helperText?: string | null;
}

const DEFAULT_HELPER =
  "Scores and Run matching use this job. Switch jobs to view preserved results.";

export function JobContextSelector({
  selectedJobId,
  onJobChange,
  disabled,
  className,
  label = "Match against job",
  helperText = DEFAULT_HELPER,
}: JobContextSelectorProps) {
  const [jobs, setJobs] = useState<JobDescriptionListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const items = await listJobDescriptions();
      setJobs(items);
      if (!selectedJobId) {
        const active = items.find((job) => job.is_active) ?? items[0];
        if (active) onJobChange(active.id, active.title);
      }
    } catch {
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [onJobChange, selectedJobId]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const handleChange = async (jobId: number) => {
    const job = jobs.find((item) => item.id === jobId);
    if (job) {
      onJobChange(job.id, job.title);
      return;
    }
    try {
      const detail = await getJobDescription(jobId);
      onJobChange(detail.id, detail.title);
    } catch {
      // ignore
    }
  };

  return (
    <div
      className={`flex flex-col gap-2 rounded-xl border border-brand-500/25 bg-brand-500/10 px-4 py-3 sm:flex-row sm:items-center sm:gap-4 ${className ?? ""}`}
    >
      <div className="flex min-w-0 items-center gap-2 text-sm text-brand-100">
        <Briefcase className="h-4 w-4 shrink-0 text-brand-300" />
        <span className="font-medium text-white">{label}</span>
      </div>
      <div className="min-w-0 flex-1">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading jobs…
          </div>
        ) : (
          <select
            value={selectedJobId ?? ""}
            onChange={(e) => handleChange(Number(e.target.value))}
            disabled={disabled || jobs.length === 0}
            className="w-full rounded-lg border border-white/15 bg-slate-950 px-3 py-2 text-sm text-white"
          >
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {formatJobListLabel(job.title, job.match_count, job.is_active)}
              </option>
            ))}
          </select>
        )}
      </div>
      {selectedJobId != null && helperText && (
        <p className="app-help-text sm:max-w-[260px] sm:text-right">{helperText}</p>
      )}
    </div>
  );
}
