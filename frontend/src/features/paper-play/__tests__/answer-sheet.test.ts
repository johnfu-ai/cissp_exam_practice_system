import { describe, expect, it } from "vitest";
import {
  cellStatus,
  emptySheet,
  formatClock,
  remainingMs,
  sheetCounts,
  type AnswerSheetState,
} from "../answer-sheet";

describe("answer sheet statuses", () => {
  it("empty sheet is all unanswered", () => {
    expect(cellStatus(emptySheet, 0)).toBe("unanswered");
    expect(sheetCounts(emptySheet, 3)).toEqual({
      answered: 0,
      wrong: 0,
      unanswered: 3,
      flagged: 0,
    });
  });

  it("wrong dominates answered; flagged only colors unanswered cells", () => {
    const sheet: AnswerSheetState = {
      answered: { 0: true, 1: true },
      wrong: { 1: true },
      flagged: { 1: true, 2: true },
    };
    expect(cellStatus(sheet, 0)).toBe("answered");
    expect(cellStatus(sheet, 1)).toBe("wrong");
    expect(cellStatus(sheet, 2)).toBe("flagged");
    expect(sheetCounts(sheet, 3)).toEqual({
      answered: 1,
      wrong: 1,
      unanswered: 0,
      flagged: 1,
    });
  });
});

describe("formatClock", () => {
  it("formats mm:ss under an hour", () => {
    expect(formatClock(0)).toBe("00:00");
    expect(formatClock(65_000)).toBe("01:05");
    expect(formatClock(3_599_000)).toBe("59:59");
  });
  it("formats h:mm:ss at an hour and beyond", () => {
    expect(formatClock(3_600_000)).toBe("1:00:00");
    expect(formatClock(6_661_000)).toBe("1:51:01");
  });
  it("never goes negative", () => {
    expect(formatClock(-5_000)).toBe("00:00");
  });
});

describe("remainingMs", () => {
  it("counts down to the deadline and clamps at zero", () => {
    const deadline = 1_000_000;
    expect(remainingMs(deadline, deadline - 500)).toBe(500);
    expect(remainingMs(deadline, deadline + 10_000)).toBe(0);
  });
});
