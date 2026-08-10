import { describe, it, expect } from "vitest";
import { fmtPct, fmtDate } from "../format";

describe("fmtPct", () => {
  it("rounds to nearest percent", () => {
    expect(fmtPct(0)).toBe("0%");
    expect(fmtPct(0.5)).toBe("50%");
    expect(fmtPct(0.666)).toBe("67%");
    expect(fmtPct(1)).toBe("100%");
  });
});

describe("fmtDate", () => {
  it("formats date-only and ISO timestamps", () => {
    expect(fmtDate("2026-06-25")).toBe("2026-06-25");
    expect(fmtDate("2026-06-25T12:34:56Z")).toBe("2026-06-25");
    expect(fmtDate(null)).toBe("—");
    expect(fmtDate("nonsense")).toBe("—");
  });
});
