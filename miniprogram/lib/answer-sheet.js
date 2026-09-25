// Answer-sheet state machine shared by the paper player pages (mirrors the
// web implementation in features/paper-play/answer-sheet.ts — FR-PAPER-05).

const CELL_STATUSES = ["answered", "wrong", "unanswered", "flagged"];

function emptySheet() {
  return { answered: {}, wrong: {}, flagged: {} };
}

function cellStatus(sheet, position) {
  if (sheet.wrong[position]) return "wrong";
  if (sheet.answered[position]) return "answered";
  if (sheet.flagged[position]) return "flagged";
  return "unanswered";
}

function sheetCounts(sheet, total) {
  const counts = { answered: 0, wrong: 0, unanswered: 0, flagged: 0 };
  for (let i = 0; i < total; i += 1) {
    counts[cellStatus(sheet, i)] += 1;
  }
  return counts;
}

function formatClock(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(seconds)}`
    : `${pad(minutes)}:${pad(seconds)}`;
}

function remainingMs(deadlineEpoch, nowEpoch) {
  return Math.max(0, deadlineEpoch - nowEpoch);
}

module.exports = {
  CELL_STATUSES,
  emptySheet,
  cellStatus,
  sheetCounts,
  formatClock,
  remainingMs,
};
