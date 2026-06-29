import { describe, it, expect } from "vitest";
import { makeT } from "@/locales/t";
import { en } from "@/locales/en";
import {
  fmtPct,
  fmtDuration,
  fmtDate,
  errorTypeLabel,
  accuracyColor,
  masteryLabel,
} from "../format";

const t = makeT(en);

describe("analytics format helpers", () => {
  it("formats percentages by rounding", () => {
    expect(fmtPct(0)).toBe("0%");
    expect(fmtPct(0.5)).toBe("50%");
    expect(fmtPct(0.666)).toBe("67%");
    expect(fmtPct(1)).toBe("100%");
  });

  it("formats durations across seconds/minutes/hours", () => {
    expect(fmtDuration(0)).toBe("0s");
    expect(fmtDuration(45_000)).toBe("45s");
    expect(fmtDuration(90_000)).toBe("1m 30s");
    expect(fmtDuration(3_600_000)).toBe("1h 0m");
    expect(fmtDuration(5_430_000)).toBe("1h 30m");
  });

  it("formats date-only and full ISO, and handles null/invalid", () => {
    expect(fmtDate("2026-06-25")).toBe("2026-06-25");
    expect(fmtDate("2026-06-25T12:34:56Z")).toBe("2026-06-25");
    expect(fmtDate(null)).toBe("—");
    expect(fmtDate("nonsense")).toBe("—");
  });

  it("labels error types with a human string and an unclassified fallback", () => {
    expect(errorTypeLabel(t, "concept_unclear")).toBe("Concept unclear");
    expect(errorTypeLabel(t, null)).toBe("Unclassified");
    expect(errorTypeLabel(t, "unknown_key")).toBe("unknown_key");
  });

  it("maps accuracy to a color bucket", () => {
    expect(accuracyColor(0.9)).toBe("bg-emerald-500");
    expect(accuracyColor(0.7)).toBe("bg-sky-500");
    expect(accuracyColor(0.5)).toBe("bg-amber-500");
    expect(accuracyColor(0.2)).toBe("bg-rose-500");
  });

  it("has a label for every mastery level", () => {
    expect(masteryLabel(t, "mastered")).toBe("Mastered");
    expect(masteryLabel(t, "not_started")).toBe("Not started");
  });
});
