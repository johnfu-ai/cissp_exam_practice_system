import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen, act, within, waitFor } from "@testing-library/react";
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
// PRD v1.6 additions (FR-PAPER-05 restyle):
//  * the mode switch is a segmented control (practice|exam segments);
//  * big blue timer, green auto-save pill, paper-title header;
//  * bookmark toggles the question state; 纠错 submits question feedback.

const submitPractice = vi.fn();
const submitExam = vi.fn();
const push = vi.fn();
const replace = vi.fn();
const apiJson = vi.fn();
const setStateMutate = vi.fn();

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

const paperDetail = {
  id: "p1",
  name: "Paper One",
  description: null,
  duration_minutes: 60,
  total_score: 100,
  question_count: 3,
  status: "published" as const,
  domain_number: null,
  created_at: null,
  attempts: 0,
  best_score: null,
  max_score: 100,
  type_counts: {},
  questions: [],
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
}));
vi.mock("@/lib/api/preferences", () => ({
  usePreferences: () => ({ data: { language_mode: "bilingual" } }),
}));
vi.mock("@/lib/api/papers", () => ({
  usePaperDetail: () => ({ data: paperDetail }),
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
  useSetQuestionState: () => ({ mutate: setStateMutate, isPending: false }),
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
    expect(await screen.findByText("Question 1 of 3", {}, { timeout: 4000 })).toBeInTheDocument();

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
    expect(await screen.findByText("Stem 0", {}, { timeout: 4000 })).toBeInTheDocument();
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
    await userEvent.click(await screen.findByRole("button", { name: /选项乙/ }, { timeout: 4000 }));
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
    expect(await screen.findByText("Question 1 of 3", {}, { timeout: 4000 })).toBeInTheDocument();
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
    expect(await screen.findByText("Question 1 of 3", {}, { timeout: 4000 })).toBeInTheDocument();
    const region = screen.getByRole("region", { name: "Question palette" });
    expect(region.className).toContain("overflow-y-auto");
    expect(region.className).toMatch(/max-h-/);
  });
});

describe("<PaperPlayer> paper layout (FR-PAPER-05, v1.6)", () => {
  beforeEach(() => {
    setupDefaultQuestion();
    apiJson.mockResolvedValue(defaultResumeState);
    setStateMutate.mockReset();
  });

  it("renders the big blue timer, auto-save pill, and paper header", async () => {
    renderWithProviders(
      <PaperPlayer sessionId="s1" kind="practice" paperId="p1" />,
    );
    expect(await screen.findByText("Question 1 of 3", {}, { timeout: 4000 })).toBeInTheDocument();
    const timer = screen.getByLabelText("timer");
    expect(timer.className).toContain("text-primary");
    // green auto-save pill
    const pill = screen.getByText("Auto-save on");
    expect(pill.className).toContain("text-success");
    // paper-title header with duration/score/count meta
    expect(screen.getByText("Paper One")).toBeInTheDocument();
    expect(screen.getByText("60 min")).toBeInTheDocument();
    expect(screen.getByText("100 points")).toBeInTheDocument();
    expect(screen.getByText("3 questions")).toBeInTheDocument();
  });

  it("shows the type tag, 纠错/标记/收藏 icon actions, and radio options", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(await screen.findByText("Question 1 of 3", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText("Single Choice")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Report error" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Flag" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bookmark" })).toBeInTheDocument();
    // radio indicators render inside the options
    const option = screen.getByRole("button", { name: /选项甲/ });
    expect(option.querySelector("span.rounded-full")).not.toBeNull();
  });

  it("bookmark toggle PUTs the question state", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(await screen.findByText("Question 1 of 3", {}, { timeout: 4000 })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Bookmark" }));
    expect(setStateMutate).toHaveBeenCalledWith({
      question_id: "q0",
      is_bookmarked: true,
    });
    expect(
      screen.getByRole("button", { name: "Bookmarked" }),
    ).toBeInTheDocument();
  });

  it("纠错 submits question feedback via the dialog", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    expect(await screen.findByText("Question 1 of 3", {}, { timeout: 4000 })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Report error" }));
    const dialog = await screen.findByRole("dialog");
    const comment = within(dialog).getByLabelText("Details (optional)");
    await userEvent.type(comment, "typo in option B");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Submit" }),
    );
    await screen.findByText(/Thanks — the editors will review it/);
    expect(apiJson).toHaveBeenCalledWith(
      "/api/questions/q0/feedback",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          feedback_type: "unclear_explanation",
          comment: "typo in option B",
        }),
      }),
    );
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
    expect(await screen.findByText("Question 3 of 3", {}, { timeout: 4000 })).toBeInTheDocument();
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

  it("posts heartbeats to the unified papers endpoint, immediately and every 20s", async () => {
    vi.useFakeTimers();
    try {
      apiJson.mockResolvedValue(defaultResumeState);
      renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
      // the mount heartbeat fires right away (truncates the away window)
      await act(async () => {});
      const mountCall = apiJson.mock.calls.find(
        (c) => String(c[0]).includes("/heartbeat"),
      );
      expect(mountCall).toBeDefined();
      expect(String(mountCall![0])).toBe("/api/papers/sessions/s1/heartbeat");
      expect(mountCall![1]).toMatchObject({ method: "POST" });

      await act(async () => {
        vi.advanceTimersByTime(21_000);
      });
      const calls = apiJson.mock.calls.filter((c) =>
        String(c[0]).includes("/heartbeat"),
      );
      const last = calls[calls.length - 1];
      expect(last).toBeDefined();
      const body = JSON.parse(last![1].body);
      expect(body.elapsed_seconds).toBeGreaterThanOrEqual(20);
      expect(body.elapsed_seconds).toBeLessThan(120);
    } finally {
      vi.useRealTimers();
    }
  });

  it("heartbeats for exam sessions too (active-time budget)", async () => {
    apiJson.mockResolvedValue(defaultResumeState);
    renderWithProviders(<PaperPlayer sessionId="s1" kind="exam" />);
    await act(async () => {});
    const call = apiJson.mock.calls.find((c) =>
      String(c[0]).includes("/heartbeat"),
    );
    expect(call).toBeDefined();
    expect(String(call![0])).toBe("/api/papers/sessions/s1/heartbeat");
  });

  it("derives the exam countdown from the active-time budget (v1.7)", async () => {
    setState(0, makeQuestion(0));
    apiJson.mockResolvedValue({
      ...defaultResumeState,
      kind: "exam",
      elapsed_seconds: 600,
      duration_budget_seconds: 3600,
      deadline_at: new Date(Date.now() + 3600_000).toISOString(),
    });
    renderWithProviders(<PaperPlayer sessionId="s1" kind="exam" />);
    // 3600 − 600 = 50 minutes remaining, NOT the 60-minute wall deadline
    await waitFor(
      () => expect(screen.getByLabelText("timer").textContent).toMatch(/^50:0/),
      { timeout: 4000 },
    );
  });

  it("re-hydrates a saved essay answer text", async () => {
    setState(1, makeQuestion(1, {
      question_type: "essay",
      options: [],
      previous_answer: { selected: [], text: "SAVED TEXT", is_correct: null },
    }));
    apiJson.mockResolvedValue(defaultResumeState);
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    await screen.findByText("Question 1 of 3", {}, { timeout: 4000 });
    await userEvent.click(
      screen.getByRole("button", { name: "question 2 unanswered" }),
    );
    const textarea = await screen.findByLabelText("essay answer", {}, { timeout: 4000 });
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

  it("switches practice to exam via the segment and routes to the converted session", async () => {
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
    // segmented control: practice active (pressed), exam clickable
    const group = await screen.findByRole("group", { name: "Mode switch" }, { timeout: 4000 });
    expect(group).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Practice" }),
    ).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(
      screen.getByRole("button", { name: "Exam" }),
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
      await screen.findByRole("button", { name: "Practice" }, { timeout: 4000 }),
    );
    expect(replace).toHaveBeenCalledWith(
      "/paper-play/s3?kind=practice&paper=p1",
    );
  });

  it("hides the segmented switch without a paper", async () => {
    renderWithProviders(<PaperPlayer sessionId="s1" kind="practice" />);
    await screen.findByText("Question 1 of 3", {}, { timeout: 4000 });
    expect(
      screen.queryByRole("group", { name: "Mode switch" }),
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
      await screen.findByRole("button", { name: "Exam" }, { timeout: 4000 }),
    );
    expect(await screen.findByText(/exam time exhausted/)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});

afterEach(() => {
  Object.keys(questions).forEach((k) => delete questions[Number(k)]);
});
