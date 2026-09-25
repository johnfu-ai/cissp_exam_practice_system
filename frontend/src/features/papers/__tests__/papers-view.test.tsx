import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render-with-providers";

const push = vi.fn();
const apiJson = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", () => ({ apiJson: (...args: unknown[]) => apiJson(...args) }));
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
    data: {
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
      ],
    },
    isLoading: false,
  }),
}));

import { PapersView } from "../papers-view";

describe("<PapersView>", () => {
  beforeEach(() => {
    push.mockReset();
    apiJson.mockReset();
  });

  it("renders paper cards with counts, duration, score, domain", () => {
    renderWithProviders(<PapersView />);
    // the name also appears in the in-progress resume card -> allBy
    expect(
      screen.getAllByText("模拟试卷一.安全与风险管理").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("173 questions")).toBeInTheDocument();
    expect(screen.getByText("180 min")).toBeInTheDocument();
    expect(screen.getByText("173 points")).toBeInTheDocument();
    expect(screen.getByText("Domain 1")).toBeInTheDocument();
  });

  it("starts a practice session and routes to the player", async () => {
    apiJson.mockResolvedValueOnce({ id: "sess-1" });
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

  it("starts an exam session with kind=exam", async () => {
    apiJson.mockResolvedValueOnce({ id: "sess-2" });
    renderWithProviders(<PapersView />);
    await userEvent.click(screen.getByRole("button", { name: /Exam: 参考/ }));
    expect(push).toHaveBeenCalledWith("/paper-play/sess-2?kind=exam&paper=p1");
  });

  it("renders in-progress sessions with continue links", async () => {
    renderWithProviders(<PapersView />);
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText(/42\/173 answered/)).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Continue: 模拟试卷一/ }),
    );
    expect(push).toHaveBeenCalledWith("/paper-play/s9?kind=practice&paper=p1");
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
