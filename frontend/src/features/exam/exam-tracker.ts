// Tracks in-progress exam session ids in localStorage so the user can resume.
// Exam /history only returns finished sessions, so resume needs client tracking.
const KEY = "exam:active-sessions";

function read(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function write(ids: string[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify([...new Set(ids)]));
}

export function trackExam(id: string): void {
  write([id, ...read()]);
}

export function untrackExam(id: string): void {
  write(read().filter((x) => x !== id));
}

export function getTrackedExamIds(): string[] {
  return read();
}
