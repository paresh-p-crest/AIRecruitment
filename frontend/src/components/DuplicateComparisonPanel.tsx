"use client";

import type { CandidateProcessResult } from "@/lib/api";
import { cn } from "@/lib/utils";

const IDENTITY_ROWS: { key: string; label: string }[] = [
  { key: "first_name", label: "First name" },
  { key: "last_name", label: "Last name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "linkedin_url", label: "LinkedIn" },
  { key: "current_location", label: "Location" },
  { key: "country", label: "Country" },
  { key: "title", label: "Title" },
];

function readIdentity(
  source: Record<string, unknown> | null | undefined
): Record<string, string> {
  if (!source) return {};
  const identity = (source.identity as Record<string, unknown> | undefined) ?? source;
  const personal =
    (source.extracted_data as { Personal_Info?: Record<string, unknown> } | undefined)
      ?.Personal_Info ?? {};

  const fullName = String(personal.Name ?? "");
  const nameParts = fullName.trim().split(/\s+/);

  return {
    first_name: String(identity.first_name ?? nameParts[0] ?? ""),
    last_name: String(identity.last_name ?? nameParts.slice(1).join(" ") ?? ""),
    email: String(identity.email ?? personal.Email ?? ""),
    phone: String(identity.phone ?? personal.Phone ?? ""),
    linkedin_url: String(identity.linkedin_url ?? ""),
    current_location: String(identity.current_location ?? personal.Location ?? ""),
    country: String(identity.country ?? ""),
    title: String(
      identity.title ?? personal["Current Designation"] ?? personal.Current_Designation ?? ""
    ),
  };
}

function cellClass(existing: string, incoming: string): string {
  if (!existing && !incoming) return "";
  if (existing && incoming && existing.toLowerCase() === incoming.toLowerCase()) {
    return "text-slate-400";
  }
  if (existing !== incoming) return "bg-amber-500/10 text-amber-100";
  return "";
}

interface DuplicateComparisonPanelProps {
  review: CandidateProcessResult;
  incomingLabel?: string;
  existingLabel?: string;
  onOpenExisting?: (candidateId: number) => void;
}

export function DuplicateComparisonPanel({
  review,
  incomingLabel = "New upload (parsed)",
  existingLabel = "Existing candidate",
  onOpenExisting,
}: DuplicateComparisonPanelProps) {
  const incoming = readIdentity(review.parsed_preview ?? undefined);
  const existing = readIdentity(review.existing_snapshot ?? undefined);
  const existingId =
    review.existing_candidate_id ??
    (review.existing_snapshot?.candidate_id as number | undefined);

  return (
    <div className="overflow-hidden rounded-xl border border-amber-500/30 bg-amber-500/5">
      <div className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-3">
        <p className="font-medium text-amber-100">Compare duplicate candidates</p>
        <p className="mt-0.5 text-xs text-slate-400">
          Review parsed identity fields, then choose a duplicate policy and confirm.
        </p>
        {existingId && onOpenExisting && (
          <button
            type="button"
            onClick={() => onOpenExisting(existingId)}
            className="mt-2 text-xs font-medium text-brand-300 underline hover:text-brand-200"
          >
            Open existing candidate record
          </button>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 bg-white/[0.03] text-xs uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2 font-medium">Field</th>
              <th className="px-3 py-2 font-medium">{existingLabel}</th>
              <th className="px-3 py-2 font-medium">{incomingLabel}</th>
            </tr>
          </thead>
          <tbody>
            {IDENTITY_ROWS.map(({ key, label }) => {
              const left = existing[key] || "—";
              const right = incoming[key] || "—";
              const diff = cellClass(existing[key] ?? "", incoming[key] ?? "");
              return (
                <tr key={key} className="border-b border-white/5">
                  <td className="px-3 py-2 text-xs font-medium text-slate-500">{label}</td>
                  <td className={cn("px-3 py-2 text-slate-200", diff && existing[key] !== incoming[key] && "bg-slate-800/40")}>
                    {left}
                  </td>
                  <td className={cn("px-3 py-2 text-slate-200", diff)}>{right}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
