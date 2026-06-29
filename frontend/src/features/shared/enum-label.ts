// Shared enum-label helper for UI chrome. Looks up a dictionary entry keyed by
// the raw enum value under `scope` (e.g. `qStatus.pending_review`); falls back
// to a Title-Case rendering of the raw value (mirrors the old `labelize`) when
// no entry exists, so unmapped enums still render readably.
import type { TFn } from "@/lib/i18n/types";

function titleize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function enumLabel(
  t: TFn,
  scope: string,
  key: string | null | undefined,
): string {
  if (!key) return "—";
  const k = `${scope}.${key}`;
  const v = t(k);
  return v === k ? titleize(key) : v;
}
