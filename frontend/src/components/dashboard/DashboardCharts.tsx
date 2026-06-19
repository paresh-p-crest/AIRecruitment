"use client";

import { cn } from "@/lib/utils";

export interface ChartSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  segments: ChartSegment[];
  size?: number;
  centerValue?: string;
  centerLabel?: string;
  className?: string;
}

export function DonutChart({
  segments,
  size = 168,
  centerValue,
  centerLabel,
  className,
}: DonutChartProps) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const radius = 54;
  const stroke = 14;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let offset = 0;
  const arcs =
    total > 0
      ? segments.map((segment) => {
          const fraction = segment.value / total;
          const length = fraction * circumference;
          const arc = {
            ...segment,
            dasharray: `${length} ${circumference - length}`,
            dashoffset: -offset,
          };
          offset += length;
          return arc;
        })
      : [];

  return (
    <div
      className={cn("relative mx-auto shrink-0", className)}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="absolute inset-0 -rotate-90"
        aria-hidden
      >
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="app-chart-ring-track"
        />
        {arcs.map((arc) => (
          <circle
            key={arc.label}
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={arc.color}
            strokeWidth={stroke}
            strokeDasharray={arc.dasharray}
            strokeDashoffset={arc.dashoffset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        ))}
      </svg>
      {(centerValue || centerLabel) && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-2 text-center">
          {centerValue && (
            <span className="font-display text-2xl font-semibold leading-none app-chart-center-value">
              {centerValue}
            </span>
          )}
          {centerLabel && (
            <span className="mt-1 text-[11px] uppercase tracking-wide text-slate-500">
              {centerLabel}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

interface HorizontalBarChartProps {
  items: ChartSegment[];
  maxValue?: number;
  className?: string;
  valueSuffix?: string;
}

export function HorizontalBarChart({
  items,
  maxValue,
  className,
  valueSuffix = "",
}: HorizontalBarChartProps) {
  const peak = maxValue ?? Math.max(...items.map((item) => item.value), 1);

  return (
    <div className={cn("space-y-3", className)}>
      {items.map((item) => {
        const width = peak > 0 ? Math.round((item.value / peak) * 100) : 0;
        return (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-slate-400">{item.label}</span>
              <span className="font-medium text-slate-300">
                {item.value}
                {valueSuffix}
              </span>
            </div>
            <div className="app-chart-bar-track h-2 overflow-hidden rounded-full">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${width}%`, backgroundColor: item.color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface ChartLegendProps {
  items: ChartSegment[];
  className?: string;
}

export function ChartLegend({ items, className }: ChartLegendProps) {
  const total = items.reduce((sum, item) => sum + item.value, 0);

  return (
    <ul className={cn("space-y-2", className)}>
      {items.map((item) => {
        const pct = total > 0 ? Math.round((item.value / total) * 100) : 0;
        return (
          <li key={item.label} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex min-w-0 items-center gap-2 app-chart-legend-label">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="truncate">{item.label}</span>
            </span>
            <span className="shrink-0 app-chart-legend-value">
              {item.value}
              {total > 0 && <span className="ml-1 text-slate-600">({pct}%)</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

interface ScoreGaugeProps {
  score: number | null;
  size?: number;
  className?: string;
}

export function ScoreGauge({ score, size = 120, className }: ScoreGaugeProps) {
  const value = score ?? 0;
  const radius = 46;
  const stroke = 10;
  const circumference = 2 * Math.PI * radius;
  const filled = score != null ? (value / 100) * circumference : 0;
  const color =
    score == null
      ? "#64748b"
      : value >= 85
        ? "#34d399"
        : value >= 70
          ? "#38bdf8"
          : value >= 55
            ? "#fbbf24"
            : "#f87171";

  return (
    <div
      className={cn("relative mx-auto shrink-0", className)}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="absolute inset-0 -rotate-90"
        aria-hidden
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="app-chart-ring-track"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={`${filled} ${circumference}`}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-2 text-center">
        <span className="font-display text-xl font-semibold leading-none app-chart-center-value">
          {score != null ? `${score}%` : "—"}
        </span>
        <span className="mt-1 text-[10px] uppercase tracking-wide text-slate-500">Avg score</span>
      </div>
    </div>
  );
}
