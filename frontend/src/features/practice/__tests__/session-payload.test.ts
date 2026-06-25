import { describe, it, expect } from "vitest";
import {
  buildSessionPayload,
  defaultSessionFormState,
  type SessionFormState,
} from "@/features/practice/session-payload";

describe("buildSessionPayload", () => {
  it("emits only count/subset/order_mode when nothing else is set", () => {
    const payload = buildSessionPayload({ ...defaultSessionFormState, count: 10 });
    expect(payload).toEqual({ count: 10, subset: "all", order_mode: "random" });
  });

  it("includes scope fields only when present, using backend field names", () => {
    const form: SessionFormState = {
      count: 25,
      subset: "wrong",
      orderMode: "easy_to_hard",
      domainId: "d1",
      bookId: "b1",
      chapterIds: ["c1", "c2"],
      questionType: "single_choice",
      difficulty: 3,
      tagId: "t1",
      languageMode: null,
    };
    expect(buildSessionPayload(form)).toEqual({
      count: 25,
      subset: "wrong",
      order_mode: "easy_to_hard",
      domain_id: "d1",
      book_id: "b1",
      chapter_ids: ["c1", "c2"],
      question_type: "single_choice",
      difficulty: 3,
      tag_id: "t1",
    });
  });

  it("includes language_mode when languageMode is set", () => {
    const payload = buildSessionPayload({
      ...defaultSessionFormState,
      count: 10,
      languageMode: "zh",
    });
    expect(payload).toEqual({
      count: 10,
      subset: "all",
      order_mode: "random",
      language_mode: "zh",
    });
  });

  it("supports bilingual language_mode", () => {
    const payload = buildSessionPayload({
      ...defaultSessionFormState,
      languageMode: "bilingual",
    });
    expect(payload.language_mode).toBe("bilingual");
  });

  it("omits language_mode when languageMode is null", () => {
    const payload = buildSessionPayload({
      ...defaultSessionFormState,
      languageMode: null,
    });
    expect(payload).not.toHaveProperty("language_mode");
  });

  it("omits empty chapter_ids and null difficulty", () => {
    const payload = buildSessionPayload({
      ...defaultSessionFormState,
      count: 5,
      domainId: "d1",
      chapterIds: [],
      difficulty: null,
    });
    expect(payload).toEqual({ count: 5, subset: "all", order_mode: "random", domain_id: "d1" });
    expect(payload).not.toHaveProperty("chapter_ids");
    expect(payload).not.toHaveProperty("difficulty");
  });
});
