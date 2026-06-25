import { describe, it, expect } from "vitest";
import { statusVariant, availableActions, STATUS_LABELS } from "../labels";

describe("question labels + state machine", () => {
  it("maps status to a badge variant", () => {
    expect(statusVariant("published")).toBe("success");
    expect(statusVariant("needs_revision")).toBe("destructive");
    expect(statusVariant("draft")).toBe("default");
    expect(statusVariant("archived")).toBe("outline");
  });

  it("offers the right review actions per status", () => {
    expect(availableActions("draft").map((a) => a.action)).toEqual(["submit"]);
    expect(availableActions("pending_review").map((a) => a.action)).toEqual([
      "approve",
      "request_changes",
    ]);
    expect(availableActions("published").map((a) => a.action)).toEqual(["archive"]);
    expect(availableActions("archived").map((a) => a.action)).toEqual(["restore"]);
  });

  it("has a label for every status", () => {
    expect(STATUS_LABELS.pending_review).toBe("Pending review");
    expect(STATUS_LABELS.published).toBe("Published");
  });
});
