"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Loader2,
  MinusCircle,
  Upload,
} from "lucide-react";
import { DuplicateComparisonPanel } from "@/components/DuplicateComparisonPanel";
import { UploadHistory } from "@/components/UploadHistory";
import {
  bulkUploadCandidates,
  confirmSingleUpload,
  getModelPricing,
  getResume,
  scanCandidateUploads,
  singleUploadCandidate,
  type CandidateProcessResult,
  type CostDisplayMode,
  type DuplicatePolicy,
  type PrescanFileResult,
  type ResumeDetail,
} from "@/lib/api";
import {
  formatCost,
  formatDuration,
  formatTokenCell,
  shortModelName,
} from "@/lib/upload-metrics";
import { cn } from "@/lib/utils";

interface UploadZoneProps {
  onUploadComplete: (resumes: ResumeDetail[]) => void;
  onOpenCandidate?: (candidateId: number) => void;
  disabled?: boolean;
  compact?: boolean;
}

type FileItemStatus = "pending" | "scanning" | "ok" | "warning" | "error" | "uploading" | "success" | "ignored";

interface FileUploadItem {
  id: string;
  file: File;
  status: FileItemStatus;
  message?: string;
  scanResult?: PrescanFileResult;
  durationMs?: number | null;
  inputTokens?: number | null;
  outputTokens?: number | null;
  totalTokens?: number | null;
  llmModel?: string | null;
  estimatedCostUsd?: number | null;
  estimatedCostCredits?: number | null;
}

type ZoneState = "idle" | "dragging" | "scanning" | "review" | "processing" | "done";

const ACCEPTED = ".pdf,.docx,.doc";
const MAX_FILES = 50;

const POLICY_LABELS: Record<DuplicatePolicy, string> = {
  ignore: "Ignore duplicates",
  add_as_default: "Replace default resume",
  add_as_new_resume: "Add as additional resume",
};

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".docx") || name.endsWith(".doc");
}

function statusIcon(status: FileItemStatus) {
  switch (status) {
    case "scanning":
    case "uploading":
      return <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-400" />;
    case "success":
    case "ok":
      return <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />;
    case "warning":
    case "ignored":
      return <MinusCircle className="h-4 w-4 shrink-0 text-amber-400" />;
    case "error":
      return <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />;
    default:
      return <FileText className="h-4 w-4 shrink-0 text-slate-500" />;
  }
}

function mapScanStatus(status: PrescanFileResult["status"]): FileItemStatus {
  if (status === "ok") return "ok";
  if (status === "warning") return "warning";
  return "error";
}

function isProcessableScan(result: PrescanFileResult): boolean {
  if (result.processable !== undefined) return result.processable;
  return result.status === "ok" || (result.status === "warning" && !result.duplicate_of_filename);
}

function metricsFromOutcome(outcome: CandidateProcessResult): Partial<FileUploadItem> {
  return {
    durationMs: outcome.duration_ms,
    inputTokens: outcome.input_tokens,
    outputTokens: outcome.output_tokens,
    totalTokens: outcome.total_tokens,
    llmModel: outcome.llm_model,
    estimatedCostUsd: outcome.estimated_cost_usd,
    estimatedCostCredits: outcome.estimated_cost_credits,
  };
}

export function UploadZone({
  onUploadComplete,
  onOpenCandidate,
  disabled,
  compact,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [zoneState, setZoneState] = useState<ZoneState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<FileUploadItem[]>([]);
  const [scanSummary, setScanSummary] = useState<{
    ready: number;
    warnings: number;
    errors: number;
    canProceed: boolean;
    aiCallsAvoided?: number;
    estimatedTokensSaved?: number;
  } | null>(null);
  const [duplicatePolicy, setDuplicatePolicy] = useState<DuplicatePolicy>("add_as_default");
  const [duplicateReview, setDuplicateReview] = useState<CandidateProcessResult | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [costMode, setCostMode] = useState<CostDisplayMode>("usd");

  useEffect(() => {
    getModelPricing()
      .then((pricing) => setCostMode(pricing.cost_display_mode))
      .catch(() => undefined);
  }, [historyRefreshKey]);

  const bumpHistory = useCallback(() => {
    setHistoryRefreshKey((key) => key + 1);
  }, []);

  const updateItem = useCallback((id: string, patch: Partial<FileUploadItem>) => {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }, []);

  const resetFlow = useCallback(() => {
    setZoneState("idle");
    setItems([]);
    setScanSummary(null);
    setDuplicateReview(null);
    setPendingFile(null);
    setError(null);
  }, []);

  const fetchResumeDetails = async (resumeIds: number[]): Promise<ResumeDetail[]> => {
    const details: ResumeDetail[] = [];
    for (const id of resumeIds) {
      try {
        details.push(await getResume(id));
      } catch {
        // skip failed fetches
      }
    }
    return details;
  };

  const processAfterScan = useCallback(
    async (queue: FileUploadItem[], policy: DuplicatePolicy) => {
      setZoneState("processing");
      setDuplicateReview(null);

      const skipped = queue.filter(
        (item) => item.scanResult && !isProcessableScan(item.scanResult)
      );
      skipped.forEach((item) => {
        updateItem(item.id, {
          status: "ignored",
          message: item.scanResult?.message ?? "Skipped during pre-scan",
        });
      });

      const processable = queue.filter(
        (item) => item.scanResult && isProcessableScan(item.scanResult)
      );
      if (processable.length === 0) {
        setError("No processable resumes in this batch.");
        setZoneState("review");
        return;
      }

      const files = processable.map((item) => item.file);

      if (files.length === 1) {
        const item = processable[0];
        updateItem(item.id, { status: "uploading" });

        try {
          const outcome = await singleUploadCandidate(item.file);
          if (outcome.status === "duplicate_review") {
            setDuplicateReview(outcome);
            setPendingFile(item.file);
            setZoneState("review");
            updateItem(item.id, { status: "warning", message: outcome.message ?? "Duplicate found" });
            return;
          }

          if (outcome.status === "success" && outcome.resume_id) {
            updateItem(item.id, {
              status: "success",
              message: outcome.message ?? undefined,
              ...metricsFromOutcome(outcome),
            });
            const resumes = await fetchResumeDetails([outcome.resume_id]);
            setZoneState("done");
            bumpHistory();
            if (resumes.length) onUploadComplete(resumes);
          } else {
            updateItem(item.id, {
              status: outcome.status === "ignored" ? "ignored" : "error",
              message: outcome.message ?? undefined,
              ...metricsFromOutcome(outcome),
            });
            setZoneState("done");
            bumpHistory();
          }
        } catch (err) {
          updateItem(item.id, {
            status: "error",
            message: err instanceof Error ? err.message : "Upload failed",
          });
          setZoneState("done");
        }
        return;
      }

      for (const item of processable) {
        updateItem(item.id, { status: "uploading" });
      }

      try {
        const bulk = await bulkUploadCandidates(files, policy);
        const resumeIds: number[] = [];

        bulk.results.forEach((result, index) => {
          const item = processable[index];
          if (!item) return;
          if (result.status === "success") {
            updateItem(item.id, {
              status: "success",
              message: result.message ?? undefined,
              ...metricsFromOutcome(result),
            });
            if (result.resume_id) resumeIds.push(result.resume_id);
          } else if (result.status === "ignored") {
            updateItem(item.id, {
              status: "ignored",
              message: result.message ?? undefined,
              ...metricsFromOutcome(result),
            });
          } else {
            updateItem(item.id, {
              status: "error",
              message: result.message ?? "Failed",
              ...metricsFromOutcome(result),
            });
          }
        });

        setZoneState("done");
        bumpHistory();
        if (resumeIds.length) {
          const resumes = await fetchResumeDetails(resumeIds);
          if (resumes.length) onUploadComplete(resumes);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Bulk upload failed");
        setZoneState("review");
      }
    },
    [bumpHistory, onUploadComplete, updateItem]
  );

  const runScan = useCallback(
    async (files: File[]) => {
      const accepted = files.filter(isAcceptedFile);
      if (accepted.length === 0) {
        setError("Only PDF, DOCX, and DOC files are supported.");
        return;
      }
      if (accepted.length > MAX_FILES) {
        setError(`You can upload up to ${MAX_FILES} resumes at once.`);
        return;
      }

      setError(null);
      setZoneState("scanning");
      setDuplicateReview(null);
      setPendingFile(null);

      const queue: FileUploadItem[] = accepted.map((file, index) => ({
        id: `${file.name}-${file.size}-${index}`,
        file,
        status: "scanning",
      }));
      setItems(queue);

      try {
        const report = await scanCandidateUploads(accepted);

        report.results.forEach((result, index) => {
          const item = queue[index];
          if (!item) return;
          updateItem(item.id, {
            status: mapScanStatus(result.status),
            message: result.message ?? undefined,
            scanResult: result,
          });
        });

        setScanSummary({
          ready: report.ready,
          warnings: report.warnings,
          errors: report.errors,
          canProceed: report.can_proceed,
          aiCallsAvoided: report.ai_calls_avoided,
          estimatedTokensSaved: report.estimated_tokens_saved,
        });
        setZoneState("review");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Scan failed");
        setZoneState("idle");
        setItems([]);
      }
    },
    [updateItem]
  );

  const handleConfirmDuplicate = useCallback(async () => {
    if (!pendingFile || !duplicateReview) return;
    setZoneState("processing");
    setError(null);

    try {
      const outcome = await confirmSingleUpload(pendingFile, duplicatePolicy);
      if (outcome.status === "success" && outcome.resume_id) {
        const resumes = await fetchResumeDetails([outcome.resume_id]);
        setZoneState("done");
        setItems([
          {
            id: pendingFile.name,
            file: pendingFile,
            status: "success",
            message: outcome.message ?? undefined,
            ...metricsFromOutcome(outcome),
          },
        ]);
        bumpHistory();
        if (resumes.length) onUploadComplete(resumes);
      } else {
        setError(outcome.message ?? "Could not save candidate");
        setZoneState("review");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed");
      setZoneState("review");
    }
  }, [bumpHistory, duplicatePolicy, duplicateReview, onUploadComplete, pendingFile]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (disabled || zoneState === "scanning" || zoneState === "processing") return;
      setZoneState("idle");
      const files = Array.from(e.dataTransfer.files);
      if (files.length) runScan(files);
    },
    [disabled, runScan, zoneState]
  );

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled && zoneState !== "scanning" && zoneState !== "processing") {
      setZoneState("dragging");
    }
  };

  const onDragLeave = () => {
    if (zoneState === "dragging") setZoneState("idle");
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) runScan(files);
    e.target.value = "";
  };

  const openFilePicker = () => {
    if (!disabled && zoneState !== "scanning" && zoneState !== "processing") {
      inputRef.current?.click();
    }
  };

  const succeeded = items.filter((item) => item.status === "success").length;
  const ignored = items.filter((item) => item.status === "ignored").length;
  const failed = items.filter((item) => item.status === "error").length;
  const showList = zoneState !== "idle" && zoneState !== "dragging";

  return (
    <div className={cn("flex flex-col", compact ? "gap-4" : "gap-6")}>
      {!compact && (
        <div className="text-center">
          <h2 className="font-display text-2xl font-semibold text-white">Upload Resumes</h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">
            Pre-scan checks file type, email, and duplicates before AI extraction. Choose how to
            handle duplicates when processing.
          </p>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        multiple
        className="hidden"
        onChange={onFileChange}
        disabled={disabled || zoneState === "scanning" || zoneState === "processing"}
      />

      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        className={cn(
          "relative rounded-2xl border-2 border-dashed transition-all duration-200",
          compact ? "min-h-[200px] p-6" : "min-h-[240px] p-8",
          disabled && "opacity-50",
          zoneState === "dragging"
            ? "border-brand-400 bg-brand-500/10 shadow-glow"
            : "border-white/15 bg-white/[0.03]",
          zoneState === "done" && succeeded > 0 && "border-emerald-500/50 bg-emerald-500/5",
          zoneState === "done" && succeeded === 0 && "border-amber-500/40 bg-amber-500/5"
        )}
      >
        {showList ? (
          <div className="flex flex-col gap-4 animate-fade-in">
            <div className="text-center">
              <p className="font-medium text-white">
                {zoneState === "scanning" && "Scanning files…"}
                {zoneState === "review" && "Review scan results"}
                {zoneState === "processing" && "Running AI extraction…"}
                {zoneState === "done" && "Upload complete"}
              </p>
              {scanSummary && zoneState === "review" && (
                <p className="mt-1 text-sm text-slate-400">
                  {scanSummary.ready} ready · {scanSummary.warnings} warnings ·{" "}
                  {scanSummary.errors} errors
                  {scanSummary.aiCallsAvoided != null && scanSummary.aiCallsAvoided > 0 && (
                    <>
                      {" "}
                      · {scanSummary.aiCallsAvoided} duplicate
                      {scanSummary.aiCallsAvoided === 1 ? "" : "s"} skipped
                      {scanSummary.estimatedTokensSaved != null &&
                        scanSummary.estimatedTokensSaved > 0 && (
                          <> (~{scanSummary.estimatedTokensSaved.toLocaleString()} tokens saved)</>
                        )}
                    </>
                  )}
                </p>
              )}
              {zoneState === "done" && (
                <p className="mt-1 text-sm text-slate-400">
                  {succeeded} added · {ignored} ignored · {failed} failed
                </p>
              )}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full table-fixed text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                    <th className="w-[22%] px-2 py-2 font-medium">File</th>
                    <th className="w-[10%] px-2 py-2 font-medium">Status</th>
                    <th className="w-[8%] px-2 py-2 font-medium">Time</th>
                    <th className="w-[12%] px-2 py-2 font-medium">Model</th>
                    <th className="w-[7%] px-2 py-2 font-medium">In</th>
                    <th className="w-[7%] px-2 py-2 font-medium">Out</th>
                    <th className="w-[8%] px-2 py-2 font-medium">Total</th>
                    <th className="w-[8%] px-2 py-2 font-medium">Cost</th>
                    <th className="w-[18%] px-2 py-2 font-medium">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.id}
                      className="border-b border-white/5 text-slate-300 last:border-0"
                    >
                      <td className="truncate px-2 py-2.5 text-white" title={item.file.name}>
                        {item.file.name}
                      </td>
                      <td className="px-2 py-2.5">
                        <span className="inline-flex items-center gap-1 capitalize">
                          {statusIcon(item.status)}
                          <span className="hidden truncate sm:inline">{item.status}</span>
                        </span>
                      </td>
                      <td className="px-2 py-2.5 text-xs">{formatDuration(item.durationMs)}</td>
                      <td
                        className="truncate px-2 py-2.5 text-xs text-slate-400"
                        title={item.llmModel ?? undefined}
                      >
                        {shortModelName(item.llmModel)}
                      </td>
                      <td className="px-2 py-2.5 text-xs">{formatTokenCell(item.inputTokens)}</td>
                      <td className="px-2 py-2.5 text-xs">{formatTokenCell(item.outputTokens)}</td>
                      <td className="px-2 py-2.5 text-xs">{formatTokenCell(item.totalTokens)}</td>
                      <td className="px-2 py-2.5 text-xs">
                        {formatCost(
                          item.estimatedCostUsd,
                          item.estimatedCostCredits,
                          costMode
                        )}
                      </td>
                      <td className="truncate px-2 py-2.5 text-xs text-slate-400" title={item.message}>
                        {item.message ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {zoneState === "done" && (
              <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
                <p className="text-xs text-slate-500">
                  Saved to upload history below. Upload more when ready.
                </p>
                <button
                  type="button"
                  onClick={resetFlow}
                  className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-400"
                >
                  <Upload className="h-4 w-4" />
                  Upload more resumes
                </button>
              </div>
            )}

            {zoneState === "review" && duplicateReview && (
              <DuplicateComparisonPanel
                review={duplicateReview}
                onOpenExisting={onOpenCandidate}
              />
            )}

            {zoneState === "review" && (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <label className="flex flex-col gap-1 text-sm text-slate-300">
                  Duplicate policy
                  <select
                    value={duplicatePolicy}
                    onChange={(e) => setDuplicatePolicy(e.target.value as DuplicatePolicy)}
                    className="rounded-lg border border-white/15 bg-slate-900 px-3 py-2 text-white"
                  >
                    {(Object.keys(POLICY_LABELS) as DuplicatePolicy[]).map((key) => (
                      <option key={key} value={key}>
                        {POLICY_LABELS[key]}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={resetFlow}
                    className="rounded-xl border border-white/15 px-4 py-2 text-sm text-slate-300 hover:bg-white/5"
                  >
                    Cancel
                  </button>
                  {duplicateReview ? (
                    <button
                      type="button"
                      onClick={handleConfirmDuplicate}
                      className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-400"
                    >
                      Confirm upload
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={!scanSummary?.canProceed}
                      onClick={() => processAfterScan(items, duplicatePolicy)}
                      className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-400 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Process with AI
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center gap-5 py-4">
            <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-500/15 ring-1 ring-brand-500/30">
              <Upload className="h-9 w-9 text-brand-400" />
            </div>
            <div className="text-center">
              <p className="font-medium text-white">
                {zoneState === "dragging" ? "Drop resumes here" : "Drag & drop resumes"}
              </p>
              <p className="mt-1 text-sm text-slate-400">
                PDF, DOCX, or DOC — up to {MAX_FILES} files
              </p>
            </div>

            <button
              type="button"
              onClick={openFilePicker}
              disabled={disabled}
              className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-6 py-3 text-sm font-semibold text-white shadow-glow transition hover:bg-brand-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <FileText className="h-4 w-4" />
              Browse Files
            </button>
          </div>
        )}
      </div>

      {error && <p className="text-center text-sm text-red-300">{error}</p>}

      {disabled && (
        <p className="text-center text-xs text-amber-400/90">
          API offline — start the backend or check Settings before uploading.
        </p>
      )}

      <UploadHistory refreshKey={historyRefreshKey} />
    </div>
  );
}
