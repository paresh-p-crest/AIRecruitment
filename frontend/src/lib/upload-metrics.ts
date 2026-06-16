export type CostDisplayMode = "usd" | "credits";

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function formatTokenCount(total: number | null | undefined): string {
  if (total == null) return "n/a";
  return total.toLocaleString();
}

export function formatTokenCell(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString();
}

export function formatCost(
  usd: number | null | undefined,
  credits: number | null | undefined,
  mode: CostDisplayMode = "usd"
): string {
  if (mode === "credits") {
    if (credits == null) return "—";
    return `${credits.toLocaleString(undefined, { maximumFractionDigits: 2 })} cr`;
  }
  if (usd == null) return "—";
  if (usd < 0.0001) return `$${usd.toFixed(6)}`;
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

export function shortModelName(model: string | null | undefined): string {
  if (!model) return "—";
  const slash = model.lastIndexOf("/");
  if (slash >= 0 && slash < model.length - 1) {
    return model.slice(slash + 1);
  }
  if (model.length > 22) {
    return `${model.slice(0, 20)}…`;
  }
  return model;
}
