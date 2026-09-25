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
}));

import { PapersView } from "../papers-view";

describe("<PapersView>", () => {
  beforeEach(() => {
    push.mockReset();
    apiJson.mockReset();
  });

  it("renders paper cards with counts, duration, score, domain", () => {
    renderWithProviders(<PapersView />);
    expect(
      screen.getByText("模拟试卷一.安全与风险管理"),
    ).toBeInTheDocument();
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
});
