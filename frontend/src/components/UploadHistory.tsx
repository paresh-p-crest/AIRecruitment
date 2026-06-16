"use client";



import { useCallback, useEffect, useState } from "react";

import {

  AlertCircle,

  CheckCircle2,

  Clock,

  History,

  Loader2,

  MinusCircle,

  RefreshCw,

  Sparkles,

  Trash2,

} from "lucide-react";

import { useDialog } from "@/components/DialogProvider";

import {

  clearUploadHistory,

  deleteUploadHistoryItem,

  getModelPricing,

  getUploadHistory,

  type CostDisplayMode,

  type UploadHistoryItem,

} from "@/lib/api";

import {

  formatCost,

  formatDuration,

  formatTokenCell,

  shortModelName,

} from "@/lib/upload-metrics";

import { cn } from "@/lib/utils";



function formatWhen(iso: string): string {

  try {

    return new Date(iso).toLocaleString(undefined, {

      month: "short",

      day: "numeric",

      hour: "numeric",

      minute: "2-digit",

    });

  } catch {

    return iso;

  }

}



function statusIcon(status: string | null | undefined) {

  switch (status) {

    case "success":

      return <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />;

    case "ignored":

      return <MinusCircle className="h-4 w-4 shrink-0 text-amber-400" />;

    case "duplicate_review":

      return <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />;

    case "error":

      return <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />;

    default:

      return <History className="h-4 w-4 shrink-0 text-slate-500" />;

  }

}



interface UploadHistoryProps {

  refreshKey?: number;

}



export function UploadHistory({ refreshKey = 0 }: UploadHistoryProps) {

  const { confirm } = useDialog();

  const [items, setItems] = useState<UploadHistoryItem[]>([]);

  const [loading, setLoading] = useState(true);

  const [deletingId, setDeletingId] = useState<number | null>(null);

  const [clearing, setClearing] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [costMode, setCostMode] = useState<CostDisplayMode>("usd");



  const load = useCallback(async () => {

    setLoading(true);

    setError(null);

    try {

      const [history, pricing] = await Promise.all([

        getUploadHistory(50),

        getModelPricing().catch(() => null),

      ]);

      setItems(history);

      if (pricing) setCostMode(pricing.cost_display_mode);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Failed to load upload history");

      setItems([]);

    } finally {

      setLoading(false);

    }

  }, []);



  useEffect(() => {

    load();

  }, [load, refreshKey]);



  const handleDeleteItem = async (item: UploadHistoryItem) => {

    const ok = await confirm({

      title: "Delete history entry?",

      message: `Remove "${item.filename}" from upload history? This does not delete the candidate.`,

      confirmLabel: "Delete",

      variant: "danger",

    });

    if (!ok) return;



    setDeletingId(item.id);

    setError(null);

    try {

      await deleteUploadHistoryItem(item.id);

      setItems((prev) => prev.filter((row) => row.id !== item.id));

    } catch (err) {

      setError(err instanceof Error ? err.message : "Failed to delete entry");

    } finally {

      setDeletingId(null);

    }

  };



  const handleClearAll = async () => {

    if (items.length === 0) return;

    const ok = await confirm({

      title: "Clear all upload history?",

      message:

        "This removes every history entry. Uploaded candidates and resumes are not deleted.",

      confirmLabel: "Clear all",

      variant: "danger",

    });

    if (!ok) return;



    setClearing(true);

    setError(null);

    try {

      await clearUploadHistory();

      setItems([]);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Failed to clear history");

    } finally {

      setClearing(false);

    }

  };



  return (

    <section className="glass rounded-2xl p-6 shadow-card">

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">

        <div>

          <h3 className="flex items-center gap-2 font-display text-lg font-semibold text-white">

            <History className="h-5 w-5 text-brand-400" />

            Upload history

          </h3>

          <p className="mt-1 text-sm text-slate-400">

            Recent extractions with model, tokens, and estimated cost per file.

          </p>

        </div>

        <div className="flex flex-wrap gap-2">

          <button

            type="button"

            onClick={load}

            disabled={loading || clearing}

            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/5 disabled:opacity-50"

          >

            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />

            Refresh

          </button>

          <button

            type="button"

            onClick={handleClearAll}

            disabled={loading || clearing || items.length === 0}

            className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-500/10 disabled:opacity-50"

          >

            {clearing ? (

              <Loader2 className="h-3.5 w-3.5 animate-spin" />

            ) : (

              <Trash2 className="h-3.5 w-3.5" />

            )}

            Clear all

          </button>

        </div>

      </div>



      {loading && items.length === 0 ? (

        <div className="flex items-center justify-center py-10 text-slate-500">

          <Loader2 className="mr-2 h-4 w-4 animate-spin" />

          Loading history…

        </div>

      ) : error ? (

        <p className="text-sm text-red-300">{error}</p>

      ) : items.length === 0 ? (

        <p className="text-sm text-slate-500">No uploads yet. Process a resume to see timing here.</p>

      ) : (

        <div className="overflow-x-auto">

          <table className="w-full table-fixed text-left text-sm">

            <thead>

              <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">

                <th className="w-[18%] px-2 py-2 font-medium">File</th>

                <th className="w-[9%] px-2 py-2 font-medium">Status</th>

                <th className="w-[7%] px-2 py-2 font-medium">Time</th>

                <th className="w-[12%] px-2 py-2 font-medium">Model</th>

                <th className="w-[7%] px-2 py-2 font-medium">In</th>

                <th className="w-[7%] px-2 py-2 font-medium">Out</th>

                <th className="w-[8%] px-2 py-2 font-medium">Total</th>

                <th className="w-[8%] px-2 py-2 font-medium">Cost</th>

                <th className="w-[12%] px-2 py-2 font-medium">When</th>

                <th className="w-[12%] px-2 py-2 text-right font-medium">Actions</th>

              </tr>

            </thead>

            <tbody>

              {items.map((item) => (

                <tr

                  key={item.id}

                  className="border-b border-white/5 text-slate-300 last:border-0"

                >

                  <td className="truncate px-2 py-2.5 text-white" title={item.filename}>

                    {item.filename}

                  </td>

                  <td className="px-2 py-2.5">

                    <span

                      className="inline-flex items-center gap-1 capitalize"

                      title={(item.process_status ?? "unknown").replace("_", " ")}

                    >

                      {statusIcon(item.process_status)}

                      <span className="hidden truncate lg:inline">

                        {(item.process_status ?? "unknown").replace("_", " ")}

                      </span>

                    </span>

                  </td>

                  <td className="px-2 py-2.5">

                    <span className="inline-flex items-center gap-1" title="Processing time">

                      <Clock className="h-3.5 w-3.5 shrink-0 text-slate-500" />

                      <span className="truncate text-xs">{formatDuration(item.duration_ms)}</span>

                    </span>

                  </td>

                  <td

                    className="truncate px-2 py-2.5 text-xs text-slate-400"

                    title={item.llm_model ?? undefined}

                  >

                    {shortModelName(item.llm_model)}

                  </td>

                  <td className="px-2 py-2.5 text-xs">{formatTokenCell(item.input_tokens)}</td>

                  <td className="px-2 py-2.5 text-xs">{formatTokenCell(item.output_tokens)}</td>

                  <td className="px-2 py-2.5">

                    <span className="inline-flex items-center gap-1 text-xs">

                      <Sparkles className="h-3 w-3 shrink-0 text-slate-500" />

                      {formatTokenCell(item.total_tokens)}

                    </span>

                  </td>

                  <td className="px-2 py-2.5 text-xs">

                    {formatCost(

                      item.estimated_cost_usd,

                      item.estimated_cost_credits,

                      costMode

                    )}

                  </td>

                  <td className="truncate px-2 py-2.5 text-xs text-slate-500" title={item.created_at}>

                    {formatWhen(item.created_at)}

                  </td>

                  <td className="px-2 py-2.5 text-right">

                    <button

                      type="button"

                      onClick={() => handleDeleteItem(item)}

                      disabled={deletingId === item.id || clearing}

                      className="inline-flex items-center justify-center rounded-lg border border-white/10 p-1.5 text-slate-400 hover:border-red-500/30 hover:bg-red-500/10 hover:text-red-300 disabled:opacity-50"

                      title="Delete this history entry"

                      aria-label="Delete this history entry"

                    >

                      {deletingId === item.id ? (

                        <Loader2 className="h-3.5 w-3.5 animate-spin" />

                      ) : (

                        <Trash2 className="h-3.5 w-3.5" />

                      )}

                    </button>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      )}

    </section>

  );

}

