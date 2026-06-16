"use client";

import { useCallback, useEffect, useState } from "react";
import { DollarSign, Loader2, Save } from "lucide-react";
import {
  getModelPricing,
  saveModelPricing,
  type CostDisplayMode,
  type ModelPricingEntry,
} from "@/lib/api";

interface ModelPricingSectionProps {
  apiOnline: boolean;
}

export function ModelPricingSection({ apiOnline }: ModelPricingSectionProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [displayMode, setDisplayMode] = useState<CostDisplayMode>("usd");
  const [creditsPerUsd, setCreditsPerUsd] = useState(1000);
  const [rows, setRows] = useState<ModelPricingEntry[]>([]);

  const load = useCallback(async () => {
    if (!apiOnline) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getModelPricing();
      setDisplayMode(data.cost_display_mode);
      setCreditsPerUsd(data.credits_per_usd);
      setRows(data.model_pricing);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pricing");
    } finally {
      setLoading(false);
    }
  }, [apiOnline]);

  useEffect(() => {
    load();
  }, [load]);

  const updateRow = (index: number, patch: Partial<ModelPricingEntry>) => {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await saveModelPricing({
        cost_display_mode: displayMode,
        credits_per_usd: creditsPerUsd,
        model_pricing: rows,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save pricing");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading model pricing…
      </div>
    );
  }

  if (!apiOnline) {
    return (
      <p className="text-sm text-slate-500">
        Connect to the backend to configure per-model token pricing.
      </p>
    );
  }

  return (
    <section className="glass rounded-2xl p-6 shadow-card">
      <div className="mb-6">
        <h2 className="flex items-center gap-2 font-display text-xl font-semibold text-white">
          <DollarSign className="h-5 w-5 text-brand-400" />
          Model pricing
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Choose how upload costs are displayed. Configure USD token rates or credits conversion —
          only one mode is shown at a time to keep settings clear.
        </p>
      </div>

      <div className="mb-6 max-w-sm">
        <label className="flex flex-col gap-1.5 text-sm text-slate-300">
          Cost display mode
          <select
            value={displayMode}
            onChange={(e) => {
              setDisplayMode(e.target.value as CostDisplayMode);
              setSaved(false);
            }}
            className="rounded-lg border border-white/15 bg-slate-900 px-3 py-2 text-white"
          >
            <option value="usd">USD ($)</option>
            <option value="credits">Credits</option>
          </select>
        </label>
      </div>

      {displayMode === "usd" ? (
        <div className="overflow-x-auto">
          <p className="mb-3 text-sm app-help-text">
            Set USD cost per million input and output tokens for each model.
          </p>
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-2 py-2 font-medium">Model</th>
                <th className="px-2 py-2 font-medium">Input / 1M (USD)</th>
                <th className="px-2 py-2 font-medium">Output / 1M (USD)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.model_id} className="border-b border-white/5 last:border-0">
                  <td className="px-2 py-2.5">
                    <p className="font-medium text-white">{row.label || row.model_id}</p>
                    <p className="text-xs text-slate-500">{row.model_id}</p>
                  </td>
                  <td className="px-2 py-2.5">
                    <div className="flex items-center gap-1">
                      <span className="text-slate-500">$</span>
                      <input
                        type="number"
                        min={0}
                        step={0.001}
                        value={row.input_per_million_usd}
                        onChange={(e) =>
                          updateRow(index, {
                            input_per_million_usd: parseFloat(e.target.value) || 0,
                          })
                        }
                        className="w-24 rounded border border-white/15 bg-slate-900 px-2 py-1 text-white"
                      />
                    </div>
                  </td>
                  <td className="px-2 py-2.5">
                    <div className="flex items-center gap-1">
                      <span className="text-slate-500">$</span>
                      <input
                        type="number"
                        min={0}
                        step={0.001}
                        value={row.output_per_million_usd}
                        onChange={(e) =>
                          updateRow(index, {
                            output_per_million_usd: parseFloat(e.target.value) || 0,
                          })
                        }
                        className="w-24 rounded border border-white/15 bg-slate-900 px-2 py-1 text-white"
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="max-w-md">
          <p className="mb-3 text-sm app-help-text">
            Upload history will show estimated cost in credits. Token rates in USD are still used
            internally — set how many credits equal one US dollar.
          </p>
          <label className="flex flex-col gap-1.5 text-sm text-slate-300">
            Credits per USD
            <input
              type="number"
              min={0.01}
              step={1}
              value={creditsPerUsd}
              onChange={(e) => {
                setCreditsPerUsd(parseFloat(e.target.value) || 1000);
                setSaved(false);
              }}
              className="rounded-lg border border-white/15 bg-slate-900 px-3 py-2 text-white"
            />
          </label>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-red-300">{error}</p>}

      <div className="mt-6 flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-400 disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save pricing
        </button>
        {saved && <span className="text-sm text-emerald-400">Pricing saved.</span>}
      </div>
    </section>
  );
}
