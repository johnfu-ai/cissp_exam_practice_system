// Answer-sheet state for the paper-bank-style paper player (PRD v1.4 FR-PAPER-05).
// Pure helpers, unit-tested — the player component keeps these in React state.

export type CellStatus = "answered" | "wrong" | "unanswered" | "flagged";

export interface AnswerSheetState {
  /** positions with a saved answer (exam: saved selection; practice: submitted) */
  answered: Record<number, boolean>;
  /** practice-graded wrong positions */
  wrong: Record<number, boolean>;
  /** locally flagged positions (答题卡标记) */
  flagged: Record<number, boolean>;
}

export const emptySheet: AnswerSheetState = {
  answered: {},
  wrong: {},
  flagged: {},
};

/** Answer-sheet cell status: flagged wins the visual only when the cell is
 * otherwise plain — the reference design renders answered/wrong with a corner marker for
 * flags; the 4-state legend counts each cell once by primary status. */
export function cellStatus(
  sheet: AnswerSheetState,
  position: number,
): CellStatus {
  if (sheet.wrong[position]) return "wrong";
  if (sheet.answered[position]) return "answered";
  if (sheet.flagged[position]) return "flagged";
  return "unanswered";
}

export interface SheetCounts {
  answered: number;
  wrong: number;
  unanswered: number;
  flagged: number;
}

export function sheetCounts(sheet: AnswerSheetState, total: number): SheetCounts {
  const counts: SheetCounts = { answered: 0, wrong: 0, unanswered: 0, flagged: 0 };
  for (let i = 0; i < total; i += 1) {
    counts[cellStatus(sheet, i)] += 1;
  }
  return counts;
}

/** mm:ss / h:mm:ss clock format for the elapsed/remaining timers. */
export function formatClock(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(seconds)}`
    : `${pad(minutes)}:${pad(seconds)}`;
}

/**
 * Countdown tick helper — pure: given the deadline epoch ms and now, the
 * remaining time clamped at 0 (the player decides to auto-submit at 0).
 */
export function remainingMs(deadlineEpochMs: number, nowEpochMs: number): number {
  return Math.max(0, deadlineEpochMs - nowEpochMs);
}
