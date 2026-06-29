import { describe, it, expect } from "vitest";
import { makeT } from "@/locales/t";
import { en } from "@/locales/en";
import { statusVariant, availableActions, statusLabel } from "../labels";

const t = makeT(en);

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

  it("exposes a dotted labelKey per action resolved via t()", () => {
    expect(availableActions("draft")[0].labelKey).toBe("qAction.submitReview");
    expect(t(availableActions("draft")[0].labelKey)).toBe("Submit for review");
  });

  it("has a label for every status", () => {
    expect(statusLabel(t, "pending_review")).toBe("Pending review");
    expect(statusLabel(t, "published")).toBe("Published");
  });
});
