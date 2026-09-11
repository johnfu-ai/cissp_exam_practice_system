/** Pure presentation helpers shared by admin + question views. */

export function fmtPct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  // Accept date-only ("2026-06-25") or full ISO timestamps.
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toISOString().slice(0, 10);
}

export function fmtDurationMinutes(ms: number): string {
  const minutes = Math.round(ms / 60000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return rem ? `${hours}h ${rem}m` : `${hours}h`;
}
