"use client";

import { CheckCircle2, Copy, Loader2, Save } from "lucide-react";
import { DUPLICATE_FIELD_OPTIONS } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SectionHeader } from "./settings-fields";

export interface DuplicateDetectionSectionProps {
  primaryFields: string[];
  onTogglePrimary: (field: string) => void;
  saving: boolean;
  saved: boolean;
  onSave: () => void;
}

export function DuplicateDetectionSection({
  primaryFields,
  onTogglePrimary,
  saving,
  saved,
  onSave,
}: DuplicateDetectionSectionProps) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-display text-2xl font-semibold text-white">
          Duplicate Detection
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">
          Choose which candidate fields trigger duplicate review on upload and warnings when
          editing profiles.
        </p>
      </div>

      <section className="glass rounded-2xl p-6 shadow-card sm:p-8">
        <SectionHeader icon={Copy} title="Matching rules" />

        <p className="mb-6 text-sm text-slate-400">
          Email and phone are used to detect the same person during upload and when saving profile
          changes. At least one field must stay enabled.
        </p>

        <div className="mb-6">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Match on
          </p>
          <div className="flex flex-wrap gap-2">
            {DUPLICATE_FIELD_OPTIONS.map((opt) => (
              <label
                key={opt.id}
                className={cn(
                  "cursor-pointer rounded-lg border px-3 py-1.5 text-sm",
                  primaryFields.includes(opt.id)
                    ? "border-brand-500/40 bg-brand-500/15 text-brand-200"
                    : "border-white/10 text-slate-400"
                )}
              >
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={primaryFields.includes(opt.id)}
                  onChange={() => onTogglePrimary(opt.id)}
                />
                {opt.label}
              </label>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={onSave}
          disabled={saving || primaryFields.length === 0}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-400 disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : saved ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          {saved ? "Duplicate rules saved" : "Save duplicate rules"}
        </button>
      </section>
    </div>
  );
}
