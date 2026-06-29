// Pure presentation helpers for the exam feature — no React.
import type { TFn } from "@/lib/i18n/types";

/** Format a millisecond countdown as H:MM:SS (or MM:SS under an hour). */
export function fmtCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  if (h > 0) return `${h}:${mm}:${ss}`;
  return `${mm}:${ss}`;
}

export function readinessLabel(t: TFn, level: string | null): string {
  if (!level) return "—";
  const k = `readiness.${level}`;
  const v = t(k);
  // Unknown levels fall back to a lowercased space-joined rendering of the key.
  return v === k ? level.replace(/_/g, " ") : v;
}

/** True when the remaining time is in the final warning window (<= 5 min). */
export function isTimeCritical(ms: number): boolean {
  return ms <= 5 * 60 * 1000;
}
