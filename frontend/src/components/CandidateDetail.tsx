"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Briefcase,
  CheckCircle2,
  ChevronDown,
  Code2,
  GraduationCap,
  Loader2,
  Play,
  Save,
  Sparkles,
  Target,
  Trash2,
  User,
  X,
} from "lucide-react";
import { useDialog } from "@/components/DialogProvider";
import { MatchScoreBreakdown } from "@/components/MatchScoreBreakdown";
import type {
  CandidateDetailResponse,
  CandidateProfileUpdate,
  DuplicateFieldWarning,
  MatchResultDetail,
  ResumeDetail,
} from "@/lib/api";
import { updateCandidateProfile } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

interface CandidateDetailProps {
  resume: ResumeDetail | null;
  candidateId?: number | null;
  profile?: CandidateDetailResponse | null;
  matchResult?: MatchResultDetail | null;
  jobDescriptionReady?: boolean;
  loading?: boolean;
  deleting?: boolean;
  matching?: boolean;
  onClose?: () => void;
  onDelete?: (candidateId: number) => void;
  onRunMatch?: () => void;
  onGoToJob?: () => void;
  onProfileSaved?: (response: { candidate: CandidateDetailResponse; resume: ResumeDetail }) => void;
  onOpenCandidate?: (candidateId: number) => void;
}

type ProfileForm = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  current_location: string;
  country: string;
  title: string;
};

function profileFromSources(
  profile: CandidateDetailResponse | null | undefined,
  resume: ResumeDetail
): ProfileForm {
  const info = resume.extracted_data.Personal_Info ?? {};
  return {
    first_name: profile?.first_name ?? "",
    last_name: profile?.last_name ?? "",
    email: profile?.email ?? info.Email ?? "",
    phone: profile?.phone ?? info.Phone ?? "",
    linkedin_url: profile?.linkedin_url ?? "",
    current_location: profile?.current_location ?? info.Location ?? "",
    country: profile?.country ?? "",
    title: profile?.title ?? info["Current Designation"] ?? "",
  };
}

function DetailPanel({
  icon: Icon,
  title,
  children,
  className,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn("rounded-xl border border-white/10 bg-white/[0.03]", className)}
    >
      <div className="border-b border-white/10 px-4 py-3">
        <h3 className="flex items-center gap-2 font-display text-sm font-semibold uppercase tracking-wide text-brand-300">
          <Icon className="h-4 w-4 shrink-0" />
          {title}
        </h3>
      </div>
      <div className="px-4 pb-4 pt-3">{children}</div>
    </section>
  );
}

function CollapsibleSection({
  icon: Icon,
  title,
  children,
  defaultOpen = false,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="rounded-xl border border-white/10 bg-white/[0.03]">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <h3 className="flex items-center gap-2 font-display text-sm font-semibold uppercase tracking-wide text-brand-300">
          <Icon className="h-4 w-4 shrink-0" />
          {title}
        </h3>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-slate-500 transition-transform",
            open && "rotate-180"
          )}
        />
      </button>
      {open && (
        <div className="border-t border-white/10 px-4 pb-4 pt-3">{children}</div>
      )}
    </section>
  );
}

function EducationList({
  education,
}: {
  education: ResumeDetail["extracted_data"]["Education"];
}) {
  if (!education.length) {
    return <p className="text-sm text-slate-500">Not extracted</p>;
  }
  return (
    <div className="space-y-3">
      {education.map((edu, i) => (
        <div key={`${edu.College}-${i}`}>
          <p className="font-medium text-white">
            {edu.Degree}
            {edu.Specialisation && (
              <span className="font-normal text-slate-400"> in {edu.Specialisation}</span>
            )}
          </p>
          <p className="text-sm text-slate-400">{edu.College}</p>
          <p className="text-xs text-slate-500">
            {edu["Start Year"]} — {edu["End Year"]}
            {edu["Grade/CGPA"] && ` · ${edu["Grade/CGPA"]}`}
          </p>
        </div>
      ))}
    </div>
  );
}

function TagList({ items, color = "brand" }: { items: string[]; color?: "brand" | "slate" }) {
  const visible = [...new Set(items.map((item) => item?.trim()).filter(Boolean))] as string[];
  if (!visible.length) {
    return <p className="text-sm text-slate-500">Not extracted</p>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {visible.map((item, index) => (
        <span
          key={`${item}-${index}`}
          className={`rounded-md px-2 py-0.5 text-xs ${
            color === "brand"
              ? "bg-brand-500/15 text-brand-200 ring-1 ring-brand-500/25"
              : "bg-slate-800 text-slate-300 ring-1 ring-slate-700"
          }`}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

export function CandidateDetail({
  resume,
  candidateId,
  profile,
  matchResult,
  jobDescriptionReady = false,
  loading,
  deleting,
  matching,
  onClose,
  onDelete,
  onRunMatch,
  onGoToJob,
  onProfileSaved,
  onOpenCandidate,
}: CandidateDetailProps) {
  const { alert, confirm } = useDialog();
  const [form, setForm] = useState<ProfileForm | null>(null);
  const [fieldWarnings, setFieldWarnings] = useState<Record<string, DuplicateFieldWarning>>({});
  const [saveWarnings, setSaveWarnings] = useState<DuplicateFieldWarning[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveToast, setSaveToast] = useState<{
    message: string;
    variant: "success" | "warning";
  } | null>(null);
  useEffect(() => {
    if (!resume) {
      setForm(null);
      return;
    }
    setForm(profileFromSources(profile, resume));
  }, [resume, profile, candidateId]);

  useEffect(() => {
    setFieldWarnings({});
    setSaveWarnings([]);
    setSaveToast(null);
  }, [candidateId]);

  useEffect(() => {
    if (!saveToast) return;
    const timer = setTimeout(() => setSaveToast(null), 3000);
    return () => clearTimeout(timer);
  }, [saveToast]);

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-slate-500">
        <Sparkles className="mb-3 h-8 w-8 animate-pulse-soft text-brand-400" />
        <p className="text-sm">Loading profile…</p>
      </div>
    );
  }

  if (!resume) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 text-center">
        <User className="mb-4 h-12 w-12 text-slate-600" />
        <p className="font-medium text-slate-400">Select a candidate</p>
        <p className="mt-1 max-w-[240px] text-sm text-slate-500">
          Click a candidate from the list or upload a new resume to view extracted data
        </p>
      </div>
    );
  }

  const { Personal_Info: info } = resume.extracted_data;
  const displayName =
    [form?.first_name, form?.last_name].filter(Boolean).join(" ") || info.Name || "Unknown Candidate";

  const handleSaveProfile = async () => {
    if (!candidateId || !form || !resume) return;
    setSaving(true);
    setFieldWarnings({});
    try {
      const payload: CandidateProfileUpdate = {
        first_name: form.first_name.trim() || null,
        last_name: form.last_name.trim() || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        linkedin_url: form.linkedin_url.trim() || null,
        current_location: form.current_location.trim() || null,
        country: form.country.trim() || null,
        title: form.title.trim() || null,
      };
      const result = await updateCandidateProfile(candidateId, payload);
      const updatedResume: ResumeDetail = {
        ...resume,
        extracted_data: result.candidate.extracted_data,
        calculated_metrics: result.candidate.calculated_metrics,
      };
      setForm(profileFromSources(result.candidate, updatedResume));

      if (result.duplicate_warnings.length) {
        const byField: Record<string, DuplicateFieldWarning> = {};
        result.duplicate_warnings.forEach((w) => {
          byField[w.field] = w;
        });
        setFieldWarnings(byField);
        setSaveWarnings(result.duplicate_warnings);
        setSaveToast({
          message: "Profile saved — check duplicate warnings",
          variant: "warning",
        });
      } else {
        setFieldWarnings({});
        setSaveWarnings([]);
        setSaveToast({ message: "Profile saved", variant: "success" });
      }

      window.setTimeout(() => {
        onProfileSaved?.({ candidate: result.candidate, resume: updatedResume });
      }, 0);
    } catch (err) {
      await alert({
        title: "Could not save profile",
        message: err instanceof Error ? err.message : "Save failed.",
        variant: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const experience = resume.extracted_data.Professional_Experience ?? [];
  const education = resume.extracted_data.Education ?? [];
  const skills = resume.extracted_data.Skills ?? {};
  const years = resume.calculated_metrics.Total_Years_Of_Experience;
  const activeMatch =
    matchResult && matchResult.resume_id === resume.id ? matchResult : null;

  const renderField = (
    field: keyof ProfileForm,
    label: string,
    type: "text" | "email" = "text"
  ) => {
    if (!form) return null;
    const warning = fieldWarnings[field];
    return (
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-500">{label}</label>
        <input
          type={type}
          value={form[field]}
          onChange={(e) => setForm({ ...form, [field]: e.target.value })}
          className={`w-full rounded-lg border bg-slate-900/60 px-3 py-2 text-sm text-white outline-none transition focus:ring-2 focus:ring-brand-500/40 ${
            warning ? "border-amber-500/60" : "border-white/10"
          }`}
        />
        {warning && (
          <p className="mt-1 text-xs text-amber-300">
            {warning.message}{" "}
            {onOpenCandidate ? (
              <button
                type="button"
                onClick={() => onOpenCandidate(warning.conflicting_candidate_id)}
                className="font-medium text-brand-300 underline hover:text-brand-200"
              >
                View existing:{" "}
                {warning.conflicting_candidate_name ||
                  warning.conflicting_candidate_email ||
                  `Candidate #${warning.conflicting_candidate_id}`}
              </button>
            ) : null}
          </p>
        )}
      </div>
    );
  };

  const conflictingLabel = (warning: DuplicateFieldWarning) =>
    warning.conflicting_candidate_name ||
    warning.conflicting_candidate_email ||
    `Candidate #${warning.conflicting_candidate_id}`;

  const hasMatch = Boolean(activeMatch);

  const handleMatchClick = () => {
    if (!jobDescriptionReady) {
      onGoToJob?.();
      return;
    }
    onRunMatch?.();
  };

  const matchAnalysisContent = activeMatch ? (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-brand-500/15 px-3 py-1 text-sm font-semibold text-brand-200 ring-1 ring-brand-500/30">
          {activeMatch.final_score.toFixed(0)} / 100
        </span>
        {activeMatch.rank != null && (
          <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-400">
            Rank #{activeMatch.rank}
          </span>
        )}
        {activeMatch.red_flag_penalty > 0 && (
          <span className="rounded-full bg-red-500/10 px-3 py-1 text-xs text-red-300">
            −{activeMatch.red_flag_penalty.toFixed(0)} red-flag penalty
          </span>
        )}
      </div>
      {activeMatch.summary && (
        <p className="mb-3 text-sm leading-relaxed text-slate-300">{activeMatch.summary}</p>
      )}
      {activeMatch.component_breakdown?.length > 0 && (
        <div className="mb-4">
          <MatchScoreBreakdown match={activeMatch} />
        </div>
      )}
      <div className="grid gap-3">
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase text-emerald-400/90">Strengths</p>
          {activeMatch.strengths.length ? (
            <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
              {activeMatch.strengths.map((item, index) => (
                <li key={`strength-${index}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">Not available</p>
          )}
        </div>
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase text-amber-400/90">
            Gaps / weaknesses
          </p>
          {activeMatch.weaknesses.length ? (
            <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
              {activeMatch.weaknesses.map((item, index) => (
                <li key={`weakness-${index}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">Not available</p>
          )}
        </div>
      </div>
      <div className="mt-3 space-y-3">
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase text-slate-500">Matching skills</p>
          <TagList items={activeMatch.matching_skills} />
        </div>
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase text-slate-500">Missing skills</p>
          <TagList
            items={activeMatch.missing_skills}
            color={activeMatch.missing_skills.length ? "slate" : "brand"}
          />
        </div>
      </div>
    </>
  ) : (
    <div className="space-y-2 text-sm text-slate-500">
      <p>
        No match score for this candidate yet.{" "}
        {onRunMatch ? (
          <button
            type="button"
            onClick={handleMatchClick}
            disabled={matching}
            className="font-medium text-brand-300 underline hover:text-brand-200 disabled:opacity-50"
          >
            Match
          </button>
        ) : (
          <span className="text-brand-300">Match</span>
        )}{" "}
        this candidate against the job description.
      </p>
      {!jobDescriptionReady && (
        <p className="text-amber-300/90">
          Job description is missing or incomplete.{" "}
          {onGoToJob ? (
            <button
              type="button"
              onClick={onGoToJob}
              className="font-medium text-brand-300 underline hover:text-brand-200"
            >
              Add job description
            </button>
          ) : (
            "Add a job description on the Job Description tab first."
          )}
          .
        </p>
      )}
    </div>
  );

  const identityFormContent =
    form && candidateId != null ? (
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          {renderField("first_name", "First name")}
          {renderField("last_name", "Last name")}
          {renderField("email", "Email", "email")}
          {renderField("phone", "Phone")}
          {renderField("linkedin_url", "LinkedIn URL")}
          {renderField("current_location", "Location")}
          {renderField("country", "Country")}
          {renderField("title", "Title")}
        </div>
        <button
          type="button"
          disabled={saving}
          onClick={handleSaveProfile}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-400 disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save profile
        </button>
        <p className="text-xs text-slate-500">
          Duplicate values warn on save and link to the existing candidate (save is not blocked).
        </p>
      </div>
    ) : (
      <p className="text-sm text-slate-500">Profile editing unavailable.</p>
    );

  const skillsContent = (
    <div className="space-y-3">
      <div>
        <p className="mb-1.5 text-xs font-medium uppercase text-slate-500">Technical</p>
        <TagList items={skills["Technical Skills"] ?? []} />
      </div>
      <div>
        <p className="mb-1.5 text-xs font-medium uppercase text-slate-500">Soft</p>
        <TagList items={skills["Soft Skills"] ?? []} color="slate" />
      </div>
    </div>
  );

  const experienceContent =
    experience.length === 0 ? (
      <p className="text-sm text-slate-500">Not extracted</p>
    ) : (
      <div className="space-y-4">
        {experience.map((job, i) => (
          <div
            key={`${job["Company Name"]}-${i}`}
            className="border-l-2 border-brand-500/40 pl-4"
          >
            <p className="font-medium text-white">{job["Job Title"] ?? "Role"}</p>
            <p className="text-sm text-slate-300">
              {job["Company Name"]}
              {job["Employment Type"] && (
                <span className="text-slate-500"> · {job["Employment Type"]}</span>
              )}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              {job["Start Date"]} — {job["End Date"] ?? "Present"}
            </p>
            {job["Technologies Used"]?.length ? (
              <div className="mt-2">
                <TagList items={job["Technologies Used"]} />
              </div>
            ) : null}
            {job.Responsibilities?.length ? (
              <ul className="mt-2 list-inside list-disc space-y-0.5 text-xs text-slate-400">
                {job.Responsibilities.slice(0, 4).map((r, index) => (
                  <li key={`resp-${i}-${index}`}>{r}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>
    );

  return (
    <div className="relative flex h-full flex-col animate-fade-in">
      {saveWarnings.length > 0 && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 shadow-lg"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
            <div className="min-w-0 flex-1 space-y-2">
              <p className="text-sm font-medium text-amber-100">
                Profile saved with duplicate warning
                {saveWarnings.length > 1 ? "s" : ""}
              </p>
              <ul className="space-y-1.5 text-sm text-amber-100/90">
                {saveWarnings.map((warning) => (
                  <li key={warning.field}>
                    <span className="font-medium text-amber-200">{warning.label}:</span>{" "}
                    {warning.message}{" "}
                    {onOpenCandidate ? (
                      <button
                        type="button"
                        onClick={() => onOpenCandidate(warning.conflicting_candidate_id)}
                        className="font-medium text-brand-300 underline hover:text-brand-200"
                      >
                        {conflictingLabel(warning)}
                      </button>
                    ) : (
                      <span className="text-amber-200">{conflictingLabel(warning)}</span>
                    )}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-amber-200/80">
                Email duplicates are not applied. Other fields were saved.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSaveWarnings([])}
              className="shrink-0 rounded-lg p-1 text-amber-300/80 hover:bg-amber-500/20 hover:text-amber-100"
              aria-label="Dismiss duplicate warnings"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl font-semibold text-white">
            {displayName}
          </h2>
          {info["Current Designation"] && (
            <p className="mt-1 text-brand-300">{info["Current Designation"]}</p>
          )}
          {info["Current Company"] && (
            <p className="text-sm text-slate-400">at {info["Current Company"]}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {saveToast && (
            <div
              role="status"
              aria-live="polite"
              className={cn(
                "animate-fade-in inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold ring-1",
                saveToast.variant === "success"
                  ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/40"
                  : "bg-amber-500/15 text-amber-200 ring-amber-500/40"
              )}
            >
              {saveToast.variant === "success" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <AlertTriangle className="h-4 w-4 shrink-0" />
              )}
              {saveToast.message}
            </div>
          )}
          {onRunMatch && (
            <button
              type="button"
              title="Match this candidate against job description"
              disabled={matching}
              onClick={handleMatchClick}
              className="inline-flex items-center gap-1.5 rounded-lg border border-brand-500/30 bg-brand-500/10 px-3 py-1.5 text-xs font-medium text-brand-200 transition hover:bg-brand-500/20 disabled:opacity-50"
            >
              {matching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              Match
            </button>
          )}
          {onDelete && resume && candidateId != null && (
            <button
              type="button"
              title="Delete candidate"
              disabled={deleting}
              onClick={async () => {
                const name = info.Name ?? "this candidate";
                const confirmed = await confirm({
                  title: "Delete candidate?",
                  message: `Delete "${name}" and release their email for new uploads? This cannot be undone.`,
                  confirmLabel: "Delete",
                  variant: "danger",
                });
                if (confirmed) onDelete(candidateId);
              }}
              className="rounded-lg p-2 text-slate-400 transition hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
            >
              {deleting ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Trash2 className="h-5 w-5" />
              )}
            </button>
          )}
          {onClose && (
            <button
              type="button"
              title="Close detail"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-500/15 px-3 py-1 text-sm font-medium text-brand-200 ring-1 ring-brand-500/30">
          <Briefcase className="h-3.5 w-3.5" />
          {years} years experience
        </span>
        <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-400">
          {resume.filename}
        </span>
        <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-400">
          {formatDate(resume.created_at)}
        </span>
      </div>

      <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto pr-1">
        {hasMatch ? (
          <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
            <DetailPanel icon={Target} title="Job Match Analysis">
              {matchAnalysisContent}
            </DetailPanel>
            <div className="flex flex-col gap-4">
              <DetailPanel icon={User} title="Identity (editable)">
                {identityFormContent}
              </DetailPanel>
              <DetailPanel icon={Code2} title="Skills">
                {skillsContent}
              </DetailPanel>
              <DetailPanel icon={GraduationCap} title="Education">
                <EducationList education={education} />
              </DetailPanel>
            </div>
          </div>
        ) : (
          <div key={`unmatched-${candidateId ?? resume.id}`} className="space-y-4">
            <DetailPanel icon={Target} title="Job Match Analysis">
              {matchAnalysisContent}
            </DetailPanel>
            <DetailPanel icon={User} title="Identity (editable)">
              {identityFormContent}
            </DetailPanel>
            <DetailPanel icon={Code2} title="Skills">
              {skillsContent}
            </DetailPanel>
            <DetailPanel icon={GraduationCap} title="Education">
              <EducationList education={education} />
            </DetailPanel>
          </div>
        )}

        <DetailPanel icon={Briefcase} title="Professional Experience">
          {experienceContent}
        </DetailPanel>

        <CollapsibleSection icon={BookOpen} title="Raw Text Preview" defaultOpen={false}>
          <p className="max-h-32 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-slate-500 scrollbar-thin">
            {resume.raw_text.slice(0, 800)}
            {resume.raw_text.length > 800 && "…"}
          </p>
        </CollapsibleSection>
      </div>

    </div>
  );
}
