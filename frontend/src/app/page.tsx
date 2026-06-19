"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { DashboardPanel } from "@/components/DashboardPanel";
import { CandidateDetail } from "@/components/CandidateDetail";
import { CandidateScoresTable } from "@/components/CandidateScoresTable";
import { useDialog } from "@/components/DialogProvider";
import { ActiveProviderBadge } from "@/components/ActiveProviderBadge";
import { CandidateSearchPanel } from "@/components/CandidateSearchPanel";
import { Header } from "@/components/Header";
import { JobDescriptionPanel } from "@/components/JobDescriptionPanel";
import { MatchingPanel } from "@/components/MatchingPanel";
import { TabBar, type HomeTabId } from "@/components/TabBar";
import { UploadZone } from "@/components/UploadZone";
import {
  checkHealth,
  deleteCandidate,
  getDashboard,
  getCandidate,
  getJobDescription,
  getMatchResult,
  getMatchResults,
  getResume,
  getSettings,
  isJobDescriptionValid,
  listResumes,
  resetAllCandidates,
  runMatching,
  runMatchingForCandidate,
  type AppSettings,
  type DashboardSnapshot,
  type CandidateDetailResponse,
  type JobDescription,
  type MatchResultDetail,
  type ResumeDetail,
  type ResumeListItem,
} from "@/lib/api";
import { getActiveModel } from "@/lib/providers";
import { cn } from "@/lib/utils";

function CandidateIdFromUrl({
  listLoading,
  onOpen,
}: {
  listLoading: boolean;
  onOpen: (candidateId: number) => void;
}) {
  const searchParams = useSearchParams();

  useEffect(() => {
    const raw = searchParams.get("candidateId");
    if (!raw || listLoading) return;
    const candidateId = parseInt(raw, 10);
    if (Number.isNaN(candidateId)) return;
    void onOpen(candidateId);
  }, [searchParams, listLoading, onOpen]);

  return null;
}

export default function HomePage() {
  const { alert } = useDialog();
  const loadRequestRef = useRef(0);
  const detailPanelRef = useRef<HTMLDivElement>(null);

  const [apiOnline, setApiOnline] = useState(false);
  const [activeTab, setActiveTab] = useState<HomeTabId>("dashboard");
  const [dashboard, setDashboard] = useState<DashboardSnapshot | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [candidates, setCandidates] = useState<ResumeListItem[]>([]);
  const [matchResults, setMatchResults] = useState<MatchResultDetail[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedResume, setSelectedResume] = useState<ResumeDetail | null>(null);
  const [selectedMatch, setSelectedMatch] = useState<MatchResultDetail | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [resetting, setResetting] = useState(false);
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);
  const [selectedProfile, setSelectedProfile] = useState<CandidateDetailResponse | null>(null);
  const [matchingAll, setMatchingAll] = useState(false);
  const [matchingId, setMatchingId] = useState<number | null>(null);
  const [showMobileDetail, setShowMobileDetail] = useState(false);
  const [activeSettings, setActiveSettings] = useState<AppSettings | null>(null);
  const [jobDescription, setJobDescription] = useState<JobDescription | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedJobTitle, setSelectedJobTitle] = useState<string | null>(null);

  const refreshHealth = useCallback(async () => {
    setApiOnline(await checkHealth());
  }, []);

  const refreshActiveProvider = useCallback(async () => {
    try {
      const online = await checkHealth();
      if (!online) {
        setActiveSettings(null);
        return;
      }
      setActiveSettings(await getSettings());
    } catch {
      setActiveSettings(null);
    }
  }, []);

  const refreshMatchResults = useCallback(async (jobId?: number) => {
    try {
      const data = await getMatchResults(jobId ?? selectedJobId ?? undefined);
      setMatchResults(data.results);
      if (data.job_title) setSelectedJobTitle(data.job_title);
      if (data.job_description_id) setSelectedJobId(data.job_description_id);
    } catch {
      setMatchResults([]);
    }
  }, [selectedJobId]);

  const refreshJobDescription = useCallback(async () => {
    try {
      const jd = await getJobDescription();
      setJobDescription(jd);
      setSelectedJobId((prev) => prev ?? jd.id);
      setSelectedJobTitle((prev) => prev ?? jd.title);
    } catch {
      setJobDescription(null);
    }
  }, []);

  const fetchCandidates = useCallback(async (jobId?: number) => {
    try {
      return await listResumes(jobId);
    } catch {
      if (jobId != null) {
        return await listResumes();
      }
      throw new Error("Failed to load candidates");
    }
  }, []);

  const handleJobContextChange = useCallback(
    async (jobId: number, jobTitle: string) => {
      setSelectedJobId(jobId);
      setSelectedJobTitle(jobTitle);
      setListLoading(true);
      try {
        const [candidateData, matchData] = await Promise.all([
          fetchCandidates(jobId),
          getMatchResults(jobId),
        ]);
        setCandidates(candidateData);
        setMatchResults(matchData.results);
      } catch {
        setCandidates([]);
        setMatchResults([]);
      } finally {
        setListLoading(false);
      }
    },
    [fetchCandidates]
  );

  const ensureJobDescriptionForMatch = useCallback(async () => {
    const jd = await getJobDescription(selectedJobId ?? undefined);
    setJobDescription(jd);
    setSelectedJobId(jd.id);
    setSelectedJobTitle(jd.title);
    if (!isJobDescriptionValid(jd)) {
      await alert({
        title: "Job description required",
        message:
          "Add a valid job description (title, skills, experience, or requirements) on the Job Description tab before running matching.",
        variant: "error",
      });
      setActiveTab("job");
      return false;
    }
    return true;
  }, [alert, selectedJobId]);

  const refreshDashboard = useCallback(async () => {
    setDashboardLoading(true);
    try {
      setDashboard(await getDashboard());
    } catch {
      setDashboard(null);
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  const refreshCandidates = useCallback(async () => {
    setListLoading(true);
    try {
      const jobId = selectedJobId ?? undefined;
      const data = await fetchCandidates(jobId);
      setCandidates(data);
      await refreshMatchResults(jobId);
      await refreshDashboard();
    } catch {
      setCandidates([]);
    } finally {
      setListLoading(false);
    }
  }, [fetchCandidates, refreshMatchResults, refreshDashboard, selectedJobId]);

  const loadDetail = useCallback(
    async (listItem: ResumeListItem) => {
      const requestId = ++loadRequestRef.current;
      setDetailLoading(true);
      setSelectedMatch(null);
      setSelectedProfile(null);

      try {
        const resumeId = listItem.resume_id ?? listItem.id;
        let detail: ResumeDetail | null = null;
        const candidateProfile = await getCandidate(listItem.candidate_id);

        if (listItem.has_resume && listItem.resume_id) {
          detail = await getResume(listItem.resume_id);
        } else {
          const fallback = candidateProfile.resumes[0];
          detail = fallback ?? {
            id: listItem.candidate_id,
            filename: "(no resume file)",
            raw_text: "",
            extracted_data: candidateProfile.extracted_data,
            calculated_metrics: candidateProfile.calculated_metrics,
            created_at: candidateProfile.created_at,
          };
        }

        const match = listItem.resume_id
          ? await getMatchResult(
              listItem.resume_id,
              selectedJobId ?? undefined
            ).catch(() => null)
          : null;

        if (requestId !== loadRequestRef.current) return;

        setSelectedResume(detail);
        setSelectedProfile(candidateProfile);
        setSelectedMatch(
          match && match.resume_id === resumeId ? match : null
        );
      } catch {
        if (requestId !== loadRequestRef.current) return;
        setSelectedResume(null);
        setSelectedProfile(null);
        setSelectedMatch(null);
      } finally {
        if (requestId === loadRequestRef.current) {
          setDetailLoading(false);
        }
      }
    },
    [selectedJobId]
  );

  useEffect(() => {
    refreshHealth();
    refreshCandidates();
    refreshJobDescription();
    refreshActiveProvider();
    const interval = setInterval(() => {
      refreshHealth();
      refreshActiveProvider();
    }, 15000);
    return () => clearInterval(interval);
  }, [refreshHealth, refreshCandidates, refreshJobDescription, refreshActiveProvider]);

  useEffect(() => {
    if (activeTab === "job" || activeTab === "candidates" || activeTab === "matching") {
      refreshJobDescription();
    }
  }, [activeTab, refreshJobDescription]);

  const handleSelect = useCallback(
    (listItem: ResumeListItem, options?: { scrollToDetail?: boolean }) => {
      setSelectedId(listItem.id);
      setSelectedCandidateId(listItem.candidate_id);
      setSelectedMatch(null);
      setShowMobileDetail(true);
      loadDetail(listItem);
      if (options?.scrollToDetail) {
        requestAnimationFrame(() => {
          detailPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      }
    },
    [loadDetail]
  );

  const handleViewFromScores = useCallback(
    (listItem: ResumeListItem) => {
      handleSelect(listItem, { scrollToDetail: true });
    },
    [handleSelect]
  );

  const handleOpenCandidate = useCallback(
    async (candidateId: number) => {
      let item = candidates.find((c) => c.candidate_id === candidateId);
      if (!item) {
        try {
          const detail = await getCandidate(candidateId);
          const resumeId = detail.default_resume_id ?? detail.resumes[0]?.id;
          if (resumeId) {
            item = {
              id: resumeId,
              candidate_id: detail.id,
              resume_id: resumeId,
              filename: detail.resumes.find((r) => r.id === resumeId)?.filename ?? "",
              candidate_name:
                [detail.first_name, detail.last_name].filter(Boolean).join(" ") || null,
              candidate_email: detail.email,
              total_years_of_experience:
                detail.calculated_metrics?.Total_Years_Of_Experience ?? null,
              match_score: null,
              match_rank: null,
              has_resume: true,
              created_at: detail.created_at,
            };
          }
        } catch {
          return;
        }
      }
      if (item) {
        handleSelect(item);
        setActiveTab("candidates");
      }
    },
    [candidates, handleSelect]
  );

  const handleProfileSaved = ({
    candidate,
    resume,
  }: {
    candidate: CandidateDetailResponse;
    resume: ResumeDetail;
  }) => {
    setSelectedProfile(candidate);
    setSelectedResume(resume);
    refreshCandidates();
  };

  const handleRunMatchAll = async (rematchAll = false) => {
    if (!(await ensureJobDescriptionForMatch())) return;
    setMatchingAll(true);
    try {
      const data = await runMatching(true, selectedJobId ?? undefined, rematchAll);
      setMatchResults(data.results);
      if (data.job_title) setSelectedJobTitle(data.job_title);
      await refreshCandidates();
      if (selectedId) {
        const updated = data.results.find((r) => r.resume_id === selectedId);
        if (updated) setSelectedMatch(updated);
      }
      if (data.matched_new === 0 && !rematchAll) {
        await alert({
          title: "Already matched",
          message:
            "Every candidate already has a score for this job. Use Rematch all to recalculate.",
          variant: "default",
        });
      }
    } catch (err) {
      await alert({
        title: "Matching failed",
        message: err instanceof Error ? err.message : "Could not run matching.",
        variant: "error",
      });
    } finally {
      setMatchingAll(false);
    }
  };

  const handleRunMatchOne = async (resumeId: number) => {
    if (!(await ensureJobDescriptionForMatch())) return;
    setMatchingId(resumeId);
    try {
      const match = await runMatchingForCandidate(
        resumeId,
        true,
        selectedJobId ?? undefined
      );
      await refreshMatchResults();
      await refreshCandidates();
      if (selectedResume?.id === resumeId) {
        setSelectedMatch(match);
      }
    } catch (err) {
      await alert({
        title: "Matching failed",
        message: err instanceof Error ? err.message : "Could not match this candidate.",
        variant: "error",
      });
    } finally {
      setMatchingId(null);
    }
  };

  const handleUploadComplete = async (resumes: ResumeDetail[]) => {
    if (resumes.length === 0) return;
    const latest = resumes[resumes.length - 1];
    setSelectedMatch(null);
    setSelectedProfile(null);
    setSelectedResume(null);
    setSelectedCandidateId(null);
    setSelectedId(null);
    setActiveTab("candidates");
    setShowMobileDetail(true);

    try {
      const jobId = selectedJobId ?? undefined;
      const [candidateData] = await Promise.all([
        fetchCandidates(jobId),
        refreshDashboard(),
      ]);
      setCandidates(candidateData);
      await refreshMatchResults(jobId);

      const item = candidateData.find(
        (c) => c.resume_id === latest.id || c.id === latest.id
      );
      if (item) {
        handleSelect(item);
      }
    } catch {
      setSelectedResume(latest);
      setSelectedId(latest.id);
    }
  };

  const handleDelete = async (candidateId: number, listId?: number) => {
    setDeletingId(listId ?? candidateId);
    try {
      await deleteCandidate(candidateId);
      if (selectedCandidateId === candidateId) {
        setSelectedId(null);
        setSelectedCandidateId(null);
        setSelectedResume(null);
        setSelectedProfile(null);
        setSelectedMatch(null);
        setShowMobileDetail(false);
      }
      await refreshCandidates();
    } catch (err) {
      await alert({
        title: "Delete failed",
        message: err instanceof Error ? err.message : "Failed to delete record.",
        variant: "error",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const handleResetAll = async () => {
    setResetting(true);
    try {
      await resetAllCandidates();
      setSelectedId(null);
      setSelectedCandidateId(null);
      setSelectedResume(null);
      setSelectedProfile(null);
      setSelectedMatch(null);
      setMatchResults([]);
      setShowMobileDetail(false);
      await refreshCandidates();
    } catch (err) {
      await alert({
        title: "Delete all failed",
        message: err instanceof Error ? err.message : "Could not delete all candidates.",
        variant: "error",
      });
    } finally {
      setResetting(false);
    }
  };

  const activeMatch =
    selectedResume &&
    selectedMatch &&
    selectedMatch.resume_id === selectedResume.id
      ? selectedMatch
      : null;

  const activeModel = activeSettings ? getActiveModel(activeSettings) : null;

  return (
    <div className="flex min-h-screen flex-col">
      <Suspense fallback={null}>
        <CandidateIdFromUrl listLoading={listLoading} onOpen={handleOpenCandidate} />
      </Suspense>
      <Header
        apiOnline={apiOnline}
        activeProvider={activeSettings?.llm_provider}
        activeModel={activeModel}
      />

      <main className="mx-auto flex w-full max-w-[1800px] flex-1 flex-col px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-5 flex flex-col gap-3 rounded-2xl border border-brand-500/20 bg-brand-500/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <p className="text-sm text-brand-100">
            <span className="font-semibold">Recruitment Pipeline</span> — Upload resumes,
            set a job description, and run hybrid AI matching. Configure LLM in{" "}
            <a href="/settings" className="text-brand-300 underline hover:text-brand-200">
              Settings
            </a>
            .
          </p>
          {activeSettings && activeModel ? (
            <div className="flex shrink-0 flex-col gap-1 sm:items-end">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-brand-300/80">
                Extraction will use
              </span>
              <ActiveProviderBadge
                provider={activeSettings.llm_provider}
                model={activeModel}
                size="sm"
              />
            </div>
          ) : apiOnline ? null : (
            <span className="text-xs text-slate-500">Connect API to see active provider</span>
          )}
        </div>

        <div className="mb-5">
          <TabBar
            active={activeTab}
            onChange={setActiveTab}
            tabs={[
              { id: "dashboard", label: "Dashboard" },
              { id: "upload", label: "Upload" },
              { id: "search", label: "Search" },
              { id: "job", label: "Job Description" },
              { id: "candidates", label: "Candidates", count: candidates.length },
              { id: "matching", label: "Match Summary" },
            ]}
          />
        </div>

        {activeTab === "dashboard" && (
          <div className="glass w-full rounded-2xl p-6 shadow-card sm:p-8">
            <DashboardPanel
              data={dashboard}
              loading={dashboardLoading}
              disabled={!apiOnline}
              onGoToTab={setActiveTab}
            />
          </div>
        )}

        <div
          className={cn(
            "glass w-full rounded-2xl p-6 shadow-card sm:p-8",
            activeTab !== "upload" && "hidden"
          )}
          aria-hidden={activeTab !== "upload"}
        >
          <UploadZone
            onUploadComplete={handleUploadComplete}
            onOpenCandidate={handleOpenCandidate}
            disabled={!apiOnline}
          />
        </div>

        {activeTab === "search" && (
          <CandidateSearchPanel
            apiOnline={apiOnline}
            onOpenCandidate={handleOpenCandidate}
          />
        )}

        {activeTab === "job" && (
          <div className="glass w-full rounded-2xl p-6 shadow-card sm:p-8">
            <JobDescriptionPanel
              disabled={!apiOnline}
              onSaved={refreshJobDescription}
              onJobChanged={() => {
                refreshJobDescription();
                refreshCandidates();
                refreshMatchResults();
                refreshDashboard();
              }}
            />
          </div>
        )}

        {activeTab === "matching" && (
          <div className="glass min-h-[560px] w-full rounded-2xl p-6 shadow-card sm:p-8">
            <MatchingPanel
              disabled={!apiOnline}
              candidates={candidates}
              matchResults={matchResults}
              resultsLoading={listLoading}
              selectedJobId={selectedJobId}
              onJobChange={handleJobContextChange}
              runningAll={matchingAll}
              onSelectCandidate={(resumeId) => {
                const item = candidates.find(
                  (c) => c.resume_id === resumeId || c.id === resumeId
                );
                if (item) {
                  handleSelect(item);
                  setActiveTab("candidates");
                }
              }}
              onRunOne={handleRunMatchOne}
              runningId={matchingId}
              onRefreshResults={() => refreshMatchResults()}
            />
          </div>
        )}

        {activeTab === "candidates" && (
          <div className="flex min-h-0 flex-1 flex-col gap-4">
            <div className="glass w-full rounded-2xl border border-white/10 p-5 shadow-card">
              <CandidateScoresTable
                candidates={candidates}
                matchResults={matchResults}
                selectedId={selectedId}
                selectedJobId={selectedJobId}
                onJobChange={handleJobContextChange}
                runningAll={matchingAll}
                runningId={matchingId}
                deletingId={deletingId}
                resetting={resetting}
                loading={listLoading}
                disabled={!apiOnline}
                onView={handleViewFromScores}
                onDelete={handleDelete}
                onResetAll={handleResetAll}
                onRefresh={refreshCandidates}
                onRunAll={handleRunMatchAll}
                onRunOne={handleRunMatchOne}
              />
            </div>

            {(selectedResume || detailLoading) && (
              <div
                ref={detailPanelRef}
                className="glass w-full scroll-mt-24 rounded-2xl border border-brand-500/20 p-5 shadow-card"
              >
                <CandidateDetail
                  key={selectedCandidateId ?? selectedResume?.id ?? "none"}
                  resume={selectedResume}
                  candidateId={selectedCandidateId}
                  profile={selectedProfile}
                  matchResult={activeMatch}
                  jobDescriptionReady={
                    jobDescription ? isJobDescriptionValid(jobDescription) : false
                  }
                  loading={detailLoading}
                  deleting={deletingId === selectedId}
                  matching={matchingId === selectedResume?.id}
                  onGoToJob={() => setActiveTab("job")}
                  onClose={() => {
                    setShowMobileDetail(false);
                    setSelectedId(null);
                    setSelectedCandidateId(null);
                    setSelectedResume(null);
                    setSelectedProfile(null);
                    setSelectedMatch(null);
                  }}
                  onDelete={(candidateId) =>
                    handleDelete(candidateId, selectedId ?? undefined)
                  }
                  onRunMatch={
                    selectedResume?.id
                      ? () => handleRunMatchOne(selectedResume.id)
                      : undefined
                  }
                  onProfileSaved={handleProfileSaved}
                  onOpenCandidate={handleOpenCandidate}
                />
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="border-t border-white/5 py-4 text-center text-xs text-slate-600">
        Easy AI Recruitment · FastAPI + LangGraph + Next.js
      </footer>
    </div>
  );
}
