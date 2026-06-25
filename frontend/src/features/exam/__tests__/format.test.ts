import { describe, it, expect } from "vitest";
import { fmtCountdown, readinessLabel, isTimeCritical } from "../format";

describe("exam format helpers", () => {
  it("formats countdown as MM:SS under an hour and H:MM:SS over", () => {
    expect(fmtCountdown(0)).toBe("00:00");
    expect(fmtCountdown(9_000)).toBe("00:09");
    expect(fmtCountdown(90_000)).toBe("01:30");
    expect(fmtCountdown(3_661_000)).toBe("1:01:01");
    expect(fmtCountdown(10_800_000)).toBe("3:00:00");
  });

  it("clamps negative remaining time to zero", () => {
    expect(fmtCountdown(-5000)).toBe("00:00");
  });

  it("labels readiness levels with a fallback", () => {
    expect(readinessLabel("ready")).toBe("Ready");
    expect(readinessLabel(null)).toBe("—");
    expect(readinessLabel("some_new_level")).toBe("some new level");
  });

  it("flags the final five minutes as critical", () => {
    expect(isTimeCritical(6 * 60 * 1000)).toBe(false);
    expect(isTimeCritical(5 * 60 * 1000)).toBe(true);
    expect(isTimeCritical(1000)).toBe(true);
  });
});
