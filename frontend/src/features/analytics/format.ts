// Pure presentation helpers for analytics — no React, fully unit-testable.
import type { TFn } from "@/lib/i18n/types";
import type { MasteryLevel } from "@/lib/api/types";

export function fmtPct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export function fmtDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  // Accept date-only ("2026-06-25") or full ISO timestamps.
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(0, 10);
}

// Tailwind classes for mastery badges (variant-agnostic; used with className).
export const MASTERY_CLASSES: Record<MasteryLevel, string> = {
  mastered: "bg-emerald-100 text-emerald-800",
  reviewing: "bg-sky-100 text-sky-800",
  learning: "bg-amber-100 text-amber-800",
  not_started: "bg-muted text-muted-foreground",
};

/** Resolve a dictionary entry keyed by the raw enum value; fall back to the raw key. */
function lookup(t: TFn, scope: string, key: string): string {
  const k = `${scope}.${key}`;
  const v = t(k);
  return v === k ? key : v;
}

export function masteryLabel(t: TFn, level: MasteryLevel): string {
  return lookup(t, "mastery", level);
}

export function errorTypeLabel(t: TFn, key: string | null): string {
  if (key === null) return t("errorType.unclassified");
  return lookup(t, "errorType", key);
}

// Color for an accuracy ratio — used by bars. Mirrors mastery thresholds.
export function accuracyColor(acc: number): string {
  if (acc >= 0.8) return "bg-emerald-500";
  if (acc >= 0.6) return "bg-sky-500";
  if (acc >= 0.4) return "bg-amber-500";
  return "bg-rose-500";
}
