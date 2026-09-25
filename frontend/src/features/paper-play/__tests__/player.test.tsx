import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render-with-providers";

// Player invariants (mirrors the CAT no-advance contract):
//  * the bilingual language toggle is pure client state — it never advances
//    the item and never submits.
//  * practice submit shows the feedback panel; the answer sheet marks wrong.
// PRD v1.5 additions (FR-PAPER-11..13):
//  * the answer sheet never collapses while the next question loads;
//  * the palette is a bounded scrollable region;
//  * resume state seeds the sheet/timer/position and the player heartbeats;
//  * mode switch posts and routes to the converted session.

const submitPractice = vi.fn();
const submitExam = vi.fn();
const push = vi.fn();
const replace = vi.fn();
const apiJson = vi.fn();

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

// per-position delivery stubs; tests mutate `questions` directly
const questions: Record<number, { data?: ReturnType<typeof makeQuestion>; isLoading: boolean }> = {};

function setState(position: number, q?: ReturnType<typeof makeQuestion>, isLoading = false) {
  questions[position] = { data: q, isLoading };
}

const defaultResumeState = {
  session_id: "s1",
  kind: "practice",
  status: "in_progress",
  paper_id: "p1",
  paper_name: "P",
  total: 3,
  answered_positions: [] as number[],
  wrong_positions: [] as number[],
  elapsed_seconds: 0,
  deadline_at: null as string | null,
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
}));
vi.mock("@/lib/api/preferences", () => ({
  usePreferences: () => ({ data: { language_mode: "bilingual" } }),
}));
vi.mock("@/lib/api/sessions", () => ({
  usePracticeQuestion: (_sid: string, position: number) =>
    questions[position] ?? { data: undefined, isLoading: true },
  useExamQuestion: (_sid: string, position: number) =>
    questions[position] ?? { data: undefined, isLoading: true },
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
  apiJson: (...args: unknown[]) => apiJson(...args),
}));

import { PaperPlayer } from "../player";

function setupDefaultQuestion() {
  setState(0, makeQuestion(0));
}

describe("<PaperPlayer> language-mode invariant", () => {
  beforeEach(() => {
    submitPractice.mockReset();
    submitExam.mockReset();
    setupDefaultQuestion();
    apiJson.mockResolvedValue(defaultResumeState);
  });

  it("toggling the language mode never advances or submits", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(await screen.findByText("Question 1 of 3")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "language mode" }));
    // still question 1, nothing submitted
    expect(screen.getByText("Question 1 of 3")).toBeInTheDocument();
    expect(submitPractice).not.toHaveBeenCalled();
    expect(submitExam).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "language mode" }));
    expect(screen.getByText("Question 1 of 3")).toBeInTheDocument();
    expect(submitPractice).not.toHaveBeenCalled();
  });

  it("renders both languages in bilingual mode", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(await screen.findByText("Stem 0")).toBeInTheDocument();
    expect(screen.getByText("题干 0")).toBeInTheDocument();
  });
});

describe("<PaperPlayer> practice flow", () => {
  beforeEach(() => {
    submitPractice.mockReset();
    setupDefaultQuestion();
    apiJson.mockResolvedValue(defaultResumeState);
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
    await userEvent.click(await screen.findByRole("button", { name: /选项乙/ }));
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    await screen.findByText("Incorrect");
    expect(submitPractice).toHaveBeenCalledTimes(1);
    // answer sheet: cell 1 (position 0) now wrong
    expect(
      screen.getByRole("button", { name: "question 1 wrong" }),
    ).toBeInTheDocument();
  });
});

describe("<PaperPlayer> sheet stability + palette scroll (FR-PAPER-13)", () => {
  beforeEach(() => {
    setupDefaultQuestion();
    apiJson.mockResolvedValue(defaultResumeState);
  });

  it("keeps the answer sheet and finish button mounted while the next question loads", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(await screen.findByText("Question 1 of 3")).toBeInTheDocument();
    // position 1 has no cached delivery yet -> loading
    setState(1, undefined, true);
    await userEvent.click(
      screen.getByRole("button", { name: "question 2 unanswered" }),
    );
    // the sheet did NOT collapse: all cells and the finish button remain
    expect(
      screen.getByRole("button", { name: "question 3 unanswered" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finish" })).toBeInTheDocument();
  });

  it("renders the palette as a bounded scrollable region", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(await screen.findByText("Question 1 of 3")).toBeInTheDocument();
    const region = screen.getByRole("region", { name: "Question palette" });
    expect(region.className).toContain("overflow-y-auto");
    expect(region.className).toMatch(/max-h-/);
  });
});

describe("<PaperPlayer> resume (FR-PAPER-12)", () => {
  beforeEach(() => {
    setupDefaultQuestion();
  });

  it("seeds the sheet, timer base, and first-unanswered position from the resume state", async () => {
    setState(2, makeQuestion(2));
    apiJson.mockResolvedValue({
      ...defaultResumeState,
      answered_positions: [0, 1],
      wrong_positions: [1],
      elapsed_seconds: 600,
    });
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    // jumped to the first unanswered question (position 2)
    expect(await screen.findByText("Question 3 of 3")).toBeInTheDocument();
    // sheet restored from the server
    expect(
      screen.getByRole("button", { name: "question 1 answered" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "question 2 wrong" }),
    ).toBeInTheDocument();
    // timer continues from the accumulated 10 minutes
    expect(screen.getByLabelText("timer").textContent).toMatch(/^10:0/);
  });

  it("posts a practice heartbeat with the accumulated elapsed seconds", async () => {
    vi.useFakeTimers();
    try {
      apiJson.mockResolvedValue(defaultResumeState);
      renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
      await act(async () => {
        vi.advanceTimersByTime(21_000);
      });
      const call = apiJson.mock.calls.find(
        (c) => String(c[0]).includes("/heartbeat"),
      );
      expect(call).toBeDefined();
      expect(String(call![0])).toBe("/api/practice/sessions/s1/heartbeat");
      expect(call![1]).toMatchObject({ method: "POST" });
      const body = JSON.parse(call![1].body);
      expect(body.elapsed_seconds).toBeGreaterThanOrEqual(20);
      expect(body.elapsed_seconds).toBeLessThan(120);
    } finally {
      vi.useRealTimers();
    }
  });

  it("re-hydrates a saved essay answer text", async () => {
    setState(1, makeQuestion(1, {
      question_type: "essay",
      options: [],
      previous_answer: { selected: [], text: "SAVED TEXT", is_correct: null },
    }));
    apiJson.mockResolvedValue(defaultResumeState);
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    await screen.findByText("Question 1 of 3");
    await userEvent.click(
      screen.getByRole("button", { name: "question 2 unanswered" }),
    );
    const textarea = await screen.findByLabelText("essay answer");
    expect(textarea).toHaveValue("SAVED TEXT");
  });
});

describe("<PaperPlayer> mode switch (FR-PAPER-11)", () => {
  beforeEach(() => {
    setupDefaultQuestion();
    push.mockReset();
    replace.mockReset();
    apiJson.mockReset();
    apiJson.mockResolvedValue(defaultResumeState);
  });

  it("switches practice to exam and routes to the converted session", async () => {
    apiJson.mockImplementation((url: string) => {
      if (String(url).includes("/switch-mode")) {
        return Promise.resolve({
          session_id: "s2",
          kind: "exam",
          paper_id: "p1",
        });
      }
      return Promise.resolve(defaultResumeState);
    });
    renderWithProviders(
      <PaperPlayer sessionId="s1" kind="practice" paperId="p1" />,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Switch to exam" }),
    );
    expect(apiJson).toHaveBeenCalledWith(
      "/api/papers/sessions/s1/switch-mode",
      expect.objectContaining({ method: "POST" }),
    );
    expect(replace).toHaveBeenCalledWith(
      "/paper-play/s2?kind=exam&paper=p1",
    );
  });

  it("switches exam to practice", async () => {
    apiJson.mockImplementation((url: string) => {
      if (String(url).includes("/switch-mode")) {
        return Promise.resolve({
          session_id: "s3",
          kind: "practice",
          paper_id: "p1",
        });
      }
      return Promise.resolve({
        ...defaultResumeState,
        kind: "exam",
        deadline_at: new Date(Date.now() + 3600_000).toISOString(),
      });
    });
    renderWithProviders(
      <PaperPlayer sessionId="s1" kind="exam" paperId="p1" />,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Switch to practice" }),
    );
    expect(replace).toHaveBeenCalledWith(
      "/paper-play/s3?kind=practice&paper=p1",
    );
  });

  it("hides the switch without a paper", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    await screen.findByText("Question 1 of 3");
    expect(
      screen.queryByRole("button", { name: "Switch to exam" }),
    ).not.toBeInTheDocument();
  });

  it("shows switch failures inline without routing", async () => {
    apiJson.mockImplementation((url: string) => {
      if (String(url).includes("/switch-mode")) {
        return Promise.reject(new Error("422 exam time exhausted"));
      }
      return Promise.resolve(defaultResumeState);
    });
    renderWithProviders(
      <PaperPlayer sessionId="s1" kind="practice" paperId="p1" />,
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Switch to exam" }),
    );
    expect(await screen.findByText(/exam time exhausted/)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});

afterEach(() => {
  Object.keys(questions).forEach((k) => delete questions[Number(k)]);
});
