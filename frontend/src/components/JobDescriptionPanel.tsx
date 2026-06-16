"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Archive,
  FileText,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Star,
  Trash2,
} from "lucide-react";
import { ActiveJobBanner } from "@/components/ActiveJobBanner";
import { JobContextSelector } from "@/components/JobContextSelector";
import { useDialog } from "@/components/DialogProvider";
import {
  activateJobDescription,
  createJobDescription,
  deleteJobDescription,
  getJobDescription,
  getJobMatchResults,
  getSampleJobDescription,
  listJobDescriptions,
  saveJobDescription,
  type JobDescription,
  type JobDescriptionListItem,
  type MatchResultDetail,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface JobDescriptionPanelProps {
  disabled?: boolean;
  onSaved?: () => void;
  onJobChanged?: () => void;
}

export function JobDescriptionPanel({
  disabled,
  onSaved,
  onJobChanged,
}: JobDescriptionPanelProps) {
  const { confirm } = useDialog();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [activating, setActivating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [parsed, setParsed] = useState<JobDescription["parsed"] | null>(null);
  const [jobs, setJobs] = useState<JobDescriptionListItem[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [currentJob, setCurrentJob] = useState<JobDescription | null>(null);
  const [storedMatches, setStoredMatches] = useState<MatchResultDetail[]>([]);
  const [loadingMatches, setLoadingMatches] = useState(false);

  const loadJobs = useCallback(async () => {
    try {
      setJobs(await listJobDescriptions());
    } catch {
      setJobs([]);
    }
  }, []);

  const loadJob = useCallback(async (jobId?: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getJobDescription(jobId);
      setCurrentJob(data);
      setSelectedJobId(data.id);
      setText(data.raw_text);
      setTitle(data.title);
      setParsed(data.parsed);
      setLoadingMatches(true);
      try {
        const matches = await getJobMatchResults(data.id);
        setStoredMatches(matches.results);
      } catch {
        setStoredMatches([]);
      } finally {
        setLoadingMatches(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job description");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    loadJob();
  }, [loadJob, loadJobs]);

  const handleSelectJob = async (jobId: number) => {
    await loadJob(jobId);
  };

  const handleSave = async () => {
    if (!selectedJobId) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const data = await saveJobDescription(text, {
        title: title.trim() || undefined,
        jobId: currentJob?.is_active ? undefined : selectedJobId,
      });
      setCurrentJob(data);
      setParsed(data.parsed);
      setTitle(data.title);
      setSaved(true);
      await loadJobs();
      onSaved?.();
      if (!data.is_active) onJobChanged?.();
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAsNew = async () => {
    setCreating(true);
    setError(null);
    try {
      const data = await createJobDescription(text, {
        title: title.trim() || undefined,
        setAsActive: true,
      });
      setCurrentJob(data);
      setSelectedJobId(data.id);
      setParsed(data.parsed);
      setTitle(data.title);
      setStoredMatches([]);
      await loadJobs();
      onSaved?.();
      onJobChanged?.();
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setCreating(false);
    }
  };

  const handleNewEmptyJob = async () => {
    setCreating(true);
    setError(null);
    try {
      const data = await createJobDescription("", { setAsActive: true });
      setCurrentJob(data);
      setSelectedJobId(data.id);
      setText("");
      setTitle(data.title);
      setParsed(data.parsed);
      setStoredMatches([]);
      await loadJobs();
      onJobChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedJobId || !currentJob) return;
    const ok = await confirm({
      title: "Delete job posting?",
      message: `Delete "${currentJob.title}" and its ${currentJob.match_count} stored match result${currentJob.match_count === 1 ? "" : "s"}? Candidate records will not be deleted.`,
      confirmLabel: "Delete job",
      variant: "error",
    });
    if (!ok) return;

    setDeleting(true);
    setError(null);
    try {
      await deleteJobDescription(selectedJobId);
      await loadJobs();
      await loadJob();
      onJobChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete job");
    } finally {
      setDeleting(false);
    }
  };

  const handleActivate = async () => {
    if (!selectedJobId) return;
    setActivating(true);
    setError(null);
    try {
      const data = await activateJobDescription(selectedJobId);
      setCurrentJob(data);
      await loadJob(data.id);
      await loadJobs();
      onJobChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to activate job");
    } finally {
      setActivating(false);
    }
  };

  const handleLoadSample = async () => {
    setError(null);
    try {
      const sample = await getSampleJobDescription();
      setText(sample.raw_text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sample");
    }
  };

  if (loading && !currentJob) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-500">
        <Loader2 className="mb-3 h-8 w-8 animate-spin" />
        <p className="text-sm">Loading job descriptions…</p>
      </div>
    );
  }

  const viewingArchived = currentJob && !currentJob.is_active;

  return (
    <div className="flex flex-col gap-6">
      <div className="text-center">
        <h2 className="font-display text-2xl font-semibold text-white">Job Descriptions</h2>
        <p className="mx-auto mt-2 max-w-2xl text-sm text-slate-400">
          Each job posting keeps its own match history. Candidates are shared — switch the active
          job to match against a different role, or review archived results below.
        </p>
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-stretch">
        <JobContextSelector
          className="flex-1"
          label="Job posting"
          helperText="Select a posting to edit. Match scores are preserved per job."
          selectedJobId={selectedJobId}
          onJobChange={(jobId) => handleSelectJob(jobId)}
          disabled={disabled || loading}
        />
        <button
          type="button"
          onClick={handleNewEmptyJob}
          disabled={disabled || creating}
          className="app-btn-secondary shrink-0 justify-center lg:self-center"
        >
          <Plus className="h-4 w-4" />
          New job
        </button>
      </div>

      {viewingArchived && (
        <div className="app-archived-job-banner">
          <p className="app-archived-job-banner-title flex items-center gap-2">
            <Archive className="h-4 w-4 shrink-0" />
            Viewing archived job — {currentJob.match_count} stored match
            {currentJob.match_count === 1 ? "" : "es"}
          </p>
          <p className="app-archived-job-banner-subtitle mt-1">
            Matching and candidate scores use the active job only. Set this job active to match
            candidates against it again.
          </p>
          <button
            type="button"
            onClick={handleActivate}
            disabled={disabled || activating}
            className="app-archived-job-btn mt-3 inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            {activating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Star className="h-3.5 w-3.5" />
            )}
            Set as active job
          </button>
        </div>
      )}

      {currentJob?.is_active && (
        <ActiveJobBanner
          jobId={currentJob.id}
          jobTitle={currentJob.title}
          matchCount={currentJob.match_count}
        />
      )}

      <label className="flex flex-col gap-1 text-sm text-slate-300">
        Display title
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={disabled || saving}
          placeholder="e.g. Senior Data Engineer"
          className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-2 text-white placeholder:text-slate-600 focus:border-brand-500/50 focus:outline-none"
        />
      </label>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled || saving}
        rows={16}
        placeholder="Senior Data Engineer/Team Lead&#10;Min. 6 Years&#10;AWS&#10;Python&#10;..."
        className="w-full resize-y rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3 font-mono text-sm leading-relaxed text-slate-200 placeholder:text-slate-600 focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:opacity-50"
      />

      {parsed && (parsed.job_title || parsed.required_skills?.length > 0) && (
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
          <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-brand-300">
            <Sparkles className="h-3.5 w-3.5" />
            Parsed preview
          </p>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            {parsed.job_title && (
              <div>
                <dt className="text-slate-500">Title</dt>
                <dd className="text-white">{parsed.job_title}</dd>
              </div>
            )}
            {parsed.min_years_experience != null && (
              <div>
                <dt className="text-slate-500">Min experience</dt>
                <dd className="text-white">{parsed.min_years_experience}+ years</dd>
              </div>
            )}
            <div className="sm:col-span-2">
              <dt className="text-slate-500">Required skills detected</dt>
              <dd className="mt-1 text-slate-300">
                {parsed.required_skills?.length
                  ? parsed.required_skills.slice(0, 12).join(" · ")
                  : "None — add skill lines or requirement bullets"}
                {(parsed.required_skills?.length ?? 0) > 12 && " …"}
              </dd>
            </div>
          </dl>
        </div>
      )}

      <div className="app-surface-card">
        <p className="mb-1 text-sm font-medium text-white">
          Preserved match results for this job
        </p>
        <p className="app-help-text mb-3">
          Scores stay linked to this job posting until you delete the job or re-run matching
          while it is active.
        </p>
        {loadingMatches ? (
          <div className="flex justify-center py-6 text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : storedMatches.length === 0 ? (
          <p className="text-sm text-slate-500">No matches stored for this job yet.</p>
        ) : (
          <ul className="max-h-48 space-y-2 overflow-y-auto">
            {storedMatches.map((match) => (
                <li
                  key={match.resume_id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm"
                >
                  <span className="truncate text-slate-300">
                    {match.rank != null && (
                      <span className="mr-2 text-slate-500">#{match.rank}</span>
                    )}
                    {match.candidate_name || match.filename || `Resume ${match.resume_id}`}
                  </span>
                  <span className={cn("shrink-0 font-medium text-brand-300")}>
                    {match.final_score.toFixed(0)}%
                  </span>
                </li>
              ))}
          </ul>
        )}
      </div>

      {error && <p className="text-center text-sm text-red-300">{error}</p>}
      {saved && (
        <p className="text-center text-sm text-emerald-300">Job description saved.</p>
      )}

      <div className="flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={handleLoadSample}
          disabled={disabled || saving || creating}
          className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-5 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-white/10 disabled:opacity-50"
        >
          <FileText className="h-4 w-4" />
          Load sample
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={disabled || saving || creating}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-6 py-2.5 text-sm font-semibold text-white shadow-glow transition hover:bg-brand-400 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </button>
        <button
          type="button"
          onClick={handleSaveAsNew}
          disabled={disabled || saving || creating}
          className="inline-flex items-center gap-2 rounded-xl border border-brand-500/40 bg-brand-500/10 px-5 py-2.5 text-sm font-medium text-brand-200 hover:bg-brand-500/20 disabled:opacity-50"
        >
          {creating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          Save as new job
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={disabled || saving || creating || deleting}
          className="app-btn-danger"
        >
          {deleting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
          Delete job
        </button>
      </div>
    </div>
  );
}
