import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render-with-providers";

// PRD v1.6: the dedicated "In progress" section is GONE. Re-entry happens via
// a continue-or-new prompt when starting a paper that already has an
// in-progress session (FR-PAPER-12), the page carries a paper-style stats
// row + attempt-status cards (FR-PAPER-03), and each paper opens an
// answer-records modal (FR-PAPER-14).

const push = vi.fn();
const apiJson = vi.fn();

// mutable via vi.hoisted so the mocked useInProgressSessions can be emptied
// per-test (vi.mock factories are hoisted above the module body)
const inProgress = vi.hoisted(() => ({
  items: [
    {
      session_id: "s9",
      kind: "practice",
      source: "paper",
      paper_id: "p1",
      paper_name: "模拟试卷一.安全与风险管理",
      dataset_slug: null,
      dataset_name: null,
      total: 173,
      answered: 42,
      started_at: "2026-09-25T10:00:00+00:00",
    },
  ] as Array<Record<string, unknown>>,
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", () => ({ apiJson: (...args: unknown[]) => apiJson(...args) }));

const paperSessions = {
  items: [
    {
      id: "ex1",
      kind: "exam",
      status: "completed",
      total_questions: 173,
      correct_count: 100,
      started_at: "2026-09-20T10:00:00+00:00",
      ended_at: "2026-09-20T13:00:00+00:00",
      answered: 173,
      score: 100,
      max_score: 173,
      passed: false,
      duration_seconds: 10800,
    },
    {
      id: "pr1",
      kind: "practice",
      status: "completed",
      total_questions: 173,
      correct_count: 120,
      started_at: "2026-09-21T10:00:00+00:00",
      ended_at: "2026-09-21T11:00:00+00:00",
      answered: 130,
      score: null,
      max_score: null,
      passed: null,
      duration_seconds: 3600,
    },
  ],
};

vi.mock("@/lib/api/papers", () => ({
  usePapers: () => ({
    data: {
      items: [
        {
          id: "p1",
          name: "模拟试卷一.安全与风险管理",
          description: null,
          duration_minutes: 180,
          total_score: 173,
          question_count: 173,
          status: "published",
          domain_number: 1,
          created_at: null,
          attempts: 2,
          best_score: 100,
          max_score: 173,
        },
      ],
    },
    isLoading: false,
    isError: false,
  }),
  useBanks: () => ({
    data: {
      items: [
        {
          dataset_slug: "osg10",
          name: "CISSP OSG v10",
          question_count: 320,
          languages: ["en", "zh"],
          has_papers: false,
        },
      ],
    },
    isLoading: false,
  }),
  useInProgressSessions: () => ({
    data: { items: inProgress.items },
    isLoading: false,
  }),
  usePaperSessions: () => ({ data: paperSessions, isLoading: false }),
}));
vi.mock("@/lib/api/wrong-book", () => ({
  useWrongBook: () => ({ data: { items: [], total: 7 } }),
}));

import { PapersView } from "../papers-view";

describe("<PapersView>", () => {
  beforeEach(() => {
    push.mockReset();
    apiJson.mockReset();
    inProgress.items = [
      {
        session_id: "s9",
        kind: "practice",
        source: "paper",
        paper_id: "p1",
        paper_name: "模拟试卷一.安全与风险管理",
        dataset_slug: null,
        dataset_name: null,
        total: 173,
        answered: 42,
        started_at: "2026-09-25T10:00:00+00:00",
      },
    ];
  });

  it("renders the stats row and paper-style paper cards", () => {
    renderWithProviders(<PapersView />);
    // stats: 1 paper, 1 completed (attempts>0), 7 wrong questions
    const stats = screen.getByTestId("papers-stats");
    expect(stats).toHaveTextContent("1");
    expect(stats).toHaveTextContent("7");
    expect(stats).toHaveTextContent("Papers");
    expect(stats).toHaveTextContent("Wrong questions");
    // card: meta + attempt status + best score + records button
    expect(screen.getByText("173 questions")).toBeInTheDocument();
    expect(screen.getByText("180 min")).toBeInTheDocument();
    expect(screen.getByText("173 points")).toBeInTheDocument();
    expect(screen.getByText("Taken 2x")).toBeInTheDocument();
    expect(screen.getByText("Best 100")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Records: 参考/ }),
    ).toBeInTheDocument();
  });

  it("no longer renders a dedicated in-progress section", () => {
    renderWithProviders(<PapersView />);
    expect(screen.queryByRole("heading", { name: "In progress" })).not.toBeInTheDocument();
    expect(screen.queryByText(/42\/173 answered/)).not.toBeInTheDocument();
  });

  it("starts a practice session directly when nothing is in progress", async () => {
    apiJson.mockResolvedValueOnce({ id: "sess-1" });
    inProgress.items = [];
    renderWithProviders(<PapersView />);
    await userEvent.click(
      screen.getByRole("button", { name: /Practice: 参考/ }),
    );
    expect(apiJson).toHaveBeenCalledWith(
      "/api/papers/p1/sessions",
      expect.objectContaining({ method: "POST" }),
    );
    expect(push).toHaveBeenCalledWith("/paper-play/sess-1?kind=practice&paper=p1");
  });

  it("prompts continue-or-new when an in-progress session exists (FR-PAPER-12)", async () => {
    apiJson.mockResolvedValueOnce({ id: "sess-1" });
    renderWithProviders(<PapersView />);
    await userEvent.click(
      screen.getByRole("button", { name: /Practice: 参考/ }),
    );
    // the continue dialog replaces a direct start
    const dialog = await screen.findByTestId("continue-dialog");
    expect(dialog).toBeVisible();
    expect(screen.getByText("Continue answering")).toBeInTheDocument();
    expect(
      screen.getByText(/You have an unfinished attempt for this paper/),
    ).toBeInTheDocument();
    // no session was created yet
    expect(apiJson).not.toHaveBeenCalled();

    // Continue last attempt routes straight to the existing session
    await userEvent.click(
      screen.getByRole("button", { name: "Continue last attempt" }),
    );
    expect(push).toHaveBeenCalledWith("/paper-play/s9?kind=practice&paper=p1");
    expect(apiJson).not.toHaveBeenCalled();
  });

  it("start-over in the prompt creates a fresh session", async () => {
    apiJson.mockResolvedValueOnce({ id: "sess-2" });
    renderWithProviders(<PapersView />);
    await userEvent.click(
      screen.getByRole("button", { name: /Practice: 参考/ }),
    );
    await screen.findByTestId("continue-dialog");
    await userEvent.click(screen.getByRole("button", { name: "Start over" }));
    expect(apiJson).toHaveBeenCalledWith(
      "/api/papers/p1/sessions",
      expect.objectContaining({ method: "POST" }),
    );
    expect(push).toHaveBeenCalledWith("/paper-play/sess-2?kind=practice&paper=p1");
  });

  it("does not prompt for a mode without an in-progress session", async () => {
    apiJson.mockResolvedValueOnce({ id: "sess-3" });
    renderWithProviders(<PapersView />);
    // only a practice session is in progress -> Exam starts directly
    await userEvent.click(screen.getByRole("button", { name: /Exam: 参考/ }));
    expect(
      screen.queryByTestId("continue-dialog"),
    ).not.toBeInTheDocument();
    expect(apiJson).toHaveBeenCalledWith(
      "/api/papers/p1/sessions",
      expect.objectContaining({ method: "POST" }),
    );
    expect(push).toHaveBeenCalledWith("/paper-play/sess-3?kind=exam&paper=p1");
  });

  it("opens the answer-records modal with stats and history (FR-PAPER-14)", async () => {
    renderWithProviders(<PapersView />);
    await userEvent.click(screen.getByRole("button", { name: /Records: 参考/ }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeVisible();
    // stats over exam attempts (one exam, score 100)
    expect(within(dialog).getByText("Attempts")).toBeInTheDocument();
    expect(within(dialog).getByText("Best")).toBeInTheDocument();
    // history table renders both rows with score + verdict + detail link
    expect(within(dialog).getByText("100/173")).toBeInTheDocument();
    expect(within(dialog).getByText("Not passed")).toBeInTheDocument();
    expect(within(dialog).getByText("Practice")).toBeInTheDocument();
    const detail = within(dialog).getByRole("link", { name: "Detail" });
    expect(detail).toHaveAttribute("href", "/paper-play/ex1/report");
  });

  it("renders free-practice banks and starts a dataset-scoped session", async () => {
    apiJson.mockResolvedValueOnce({ id: "bank-sess" });
    renderWithProviders(<PapersView />);
    expect(screen.getByText("CISSP OSG v10")).toBeInTheDocument();
    expect(screen.getByText("320 questions")).toBeInTheDocument();
    // default count 20, sequential order
    await userEvent.click(
      screen.getByRole("button", { name: /Sequential: CISSP OSG v10/ }),
    );
    expect(apiJson).toHaveBeenCalledWith(
      "/api/practice/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          dataset_slug: "osg10",
          count: 20,
          order_mode: "sequential",
        }),
      }),
    );
    expect(push).toHaveBeenCalledWith("/paper-play/bank-sess?kind=practice");
  });

  it("starts a random bank session when Random is chosen", async () => {
    apiJson.mockResolvedValueOnce({ id: "bank-rand" });
    renderWithProviders(<PapersView />);
    await userEvent.click(
      screen.getByRole("button", { name: /Random: CISSP OSG v10/ }),
    );
    expect(apiJson).toHaveBeenCalledWith(
      "/api/practice/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          dataset_slug: "osg10",
          count: 20,
          order_mode: "random",
        }),
      }),
    );
  });
});
