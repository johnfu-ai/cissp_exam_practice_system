import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render-with-providers";

// Player invariants (mirrors the CAT no-advance contract):
//  * the bilingual language toggle is pure client state — it never advances
//    the item and never submits.
//  * practice submit shows the feedback panel; the answer sheet marks wrong.

const submitPractice = vi.fn();
const submitExam = vi.fn();

function makeQuestion(position: number, overrides: Record<string, unknown> = {}) {
  return {
    session_id: "s1",
    position,
    total: 3,
    question_id: `q${position}`,
    question_type: "single_choice",
    available_languages: ["en", "zh"],
    language_mode: "bilingual",
    stem: { en: `Stem ${position}`, zh: `题干 ${position}` },
    options: [
      {
        id: "o0",
        order_index: 0,
        content: { en: "opt A en", zh: "选项甲" },
        content_format: { en: "markdown", zh: "markdown" },
      },
      {
        id: "o1",
        order_index: 1,
        content: { en: "opt B en", zh: "选项乙" },
        content_format: { en: "markdown", zh: "markdown" },
      },
    ],
    elapsed_ms: 1000,
    previous_answer: null,
    note: null,
    ...overrides,
  };
}

vi.mock("@/lib/api/preferences", () => ({
  usePreferences: () => ({ data: { language_mode: "bilingual" } }),
}));
vi.mock("@/lib/api/sessions", () => ({
  usePracticeQuestion: (_sid: string, position: number) => ({
    data: makeQuestion(position),
    isLoading: false,
  }),
  useExamQuestion: (_sid: string, position: number) => ({
    data: { ...makeQuestion(position), time_remaining_ms: 60000 },
    isLoading: false,
  }),
  useSubmitPracticeAnswer: () => ({
    mutateAsync: submitPractice,
    isPending: false,
  }),
  useSubmitExamAnswer: () => ({ mutateAsync: submitExam, isPending: false }),
  usePracticeSelfAssess: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useExamSelfAssess: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useFinishPractice: () => ({
    mutateAsync: vi.fn().mockResolvedValue({
      answered_count: 1,
      correct_count: 0,
      accuracy: 0,
    }),
    isPending: false,
  }),
  useFinishExam: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetQuestionState: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("@/lib/api", () => ({
  apiJson: vi.fn().mockResolvedValue({
    config: { deadline_at: new Date(Date.now() + 3600_000).toISOString() },
  }),
}));

import { PaperPlayer } from "../player";

describe("<PaperPlayer> language-mode invariant", () => {
  beforeEach(() => {
    submitPractice.mockReset();
    submitExam.mockReset();
  });

  it("toggling the language mode never advances or submits", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(screen.getByText("Question 1 of 3")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "language mode" }));
    // still question 1, nothing submitted
    expect(screen.getByText("Question 1 of 3")).toBeInTheDocument();
    expect(submitPractice).not.toHaveBeenCalled();
    expect(submitExam).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "language mode" }));
    expect(screen.getByText("Question 1 of 3")).toBeInTheDocument();
    expect(submitPractice).not.toHaveBeenCalled();
  });

  it("renders both languages in bilingual mode", () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(screen.getByText("Stem 0")).toBeInTheDocument();
    expect(screen.getByText("题干 0")).toBeInTheDocument();
  });
});

describe("<PaperPlayer> practice flow", () => {
  beforeEach(() => {
    submitPractice.mockReset();
  });

  it("submitting a wrong answer marks the cell wrong and shows feedback", async () => {
    submitPractice.mockResolvedValueOnce({
      is_correct: false,
      correct_indexes: [0],
      selected_indexes: [1],
      correct_rationale: { en: "rationale", zh: "解析" },
      key_point_summary: { en: null, zh: null },
      per_option: [],
      mapping: {},
      history: [],
    });
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    await userEvent.click(screen.getByRole("button", { name: /选项乙/ }));
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    await screen.findByText("Incorrect");
    expect(submitPractice).toHaveBeenCalledTimes(1);
    // answer sheet: cell 1 (position 0) now wrong
    expect(
      screen.getByRole("button", { name: "question 1 wrong" }),
    ).toBeInTheDocument();
  });
});
