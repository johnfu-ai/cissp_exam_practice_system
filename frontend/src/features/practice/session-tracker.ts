const KEY = "practice:active-sessions";

function read(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function write(ids: string[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(ids));
}

export function trackSession(id: string): void {
  const ids = read().filter((x) => x !== id);
  write([id, ...ids]);
}

export function untrackSession(id: string): void {
  write(read().filter((x) => x !== id));
}

export function getTrackedSessionIds(): string[] {
  return read();
}
