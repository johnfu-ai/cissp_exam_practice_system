import { describe, it, expect } from "vitest";
import {
  initialRunnerState,
  toggleSelection,
  canSubmit,
  markSubmitted,
} from "@/features/practice/runner-machine";
import type { AnswerResult } from "@/lib/api/types";

const result: AnswerResult = {
  is_correct: true,
  correct_indexes: [0],
  selected_indexes: [0],
  correct_rationale: { en: "because", zh: null },
  key_point_summary: { en: null, zh: null },
  per_option: [],
  mapping: {},
  history: [],
};

describe("runner machine", () => {
  it("fresh question starts selecting with no selection", () => {
    const s = initialRunnerState(null);
    expect(s.phase).toBe("selecting");
    expect(s.selected).toEqual([]);
    expect(canSubmit(s)).toBe(false);
  });

  it("rehydrates an already-answered question as submitted with its prior selection", () => {
    const s = initialRunnerState({ selected: [2], is_correct: false });
    expect(s.phase).toBe("submitted");
    expect(s.selected).toEqual([2]);
    expect(canSubmit(s)).toBe(false);
  });

  it("single_choice selection replaces the prior choice", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 1, "single_choice");
    s = toggleSelection(s, 3, "single_choice");
    expect(s.selected).toEqual([3]);
    expect(canSubmit(s)).toBe(true);
  });

  it("true_false selection replaces the prior choice", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 0, "true_false");
    s = toggleSelection(s, 1, "true_false");
    expect(s.selected).toEqual([1]);
  });

  it("multiple_choice toggles selections in and out, kept sorted", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 2, "multiple_choice");
    s = toggleSelection(s, 0, "multiple_choice");
    expect(s.selected).toEqual([0, 2]);
    s = toggleSelection(s, 2, "multiple_choice");
    expect(s.selected).toEqual([0]);
  });

  it("cannot toggle after submitting", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 1, "single_choice");
    s = markSubmitted(s, result);
    const after = toggleSelection(s, 2, "single_choice");
    expect(after.selected).toEqual([1]);
    expect(after.phase).toBe("submitted");
  });

  it("markSubmitted captures the result and locks the phase", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 0, "single_choice");
    s = markSubmitted(s, result);
    expect(s.phase).toBe("submitted");
    expect(s.result).toBe(result);
    expect(canSubmit(s)).toBe(false);
  });
});
