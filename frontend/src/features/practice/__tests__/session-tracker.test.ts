import { describe, it, expect, beforeEach } from "vitest";
import {
  trackSession,
  untrackSession,
  getTrackedSessionIds,
} from "@/features/practice/session-tracker";

beforeEach(() => {
  localStorage.clear();
});

describe("session tracker", () => {
  it("returns empty when nothing tracked", () => {
    expect(getTrackedSessionIds()).toEqual([]);
  });

  it("tracks ids most-recent-first and dedupes", () => {
    trackSession("a");
    trackSession("b");
    trackSession("a");
    expect(getTrackedSessionIds()).toEqual(["a", "b"]);
  });

  it("untracks an id", () => {
    trackSession("a");
    trackSession("b");
    untrackSession("a");
    expect(getTrackedSessionIds()).toEqual(["b"]);
  });

  it("recovers from corrupt storage", () => {
    localStorage.setItem("practice:active-sessions", "not-json");
    expect(getTrackedSessionIds()).toEqual([]);
  });
});
