import { describe, it, expect, beforeEach } from "vitest";
import { trackExam, untrackExam, getTrackedExamIds } from "../exam-tracker";

beforeEach(() => window.localStorage.clear());

describe("exam-tracker", () => {
  it("tracks and reads ids most-recent-first without duplicates", () => {
    trackExam("a");
    trackExam("b");
    trackExam("a");
    expect(getTrackedExamIds()).toEqual(["a", "b"]);
  });

  it("untracks an id", () => {
    trackExam("a");
    trackExam("b");
    untrackExam("a");
    expect(getTrackedExamIds()).toEqual(["b"]);
  });

  it("returns an empty list when nothing is tracked", () => {
    expect(getTrackedExamIds()).toEqual([]);
  });
});
