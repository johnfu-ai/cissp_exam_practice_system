import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render-with-providers";

const push = vi.fn();
const mutateState = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/preferences", () => ({
  usePreferences: () => ({ data: { language_mode: "zh" } }),
}));
vi.mock("@/lib/api/papers", () => ({
  usePapers: () => ({
    data: { items: [{ id: "p1", name: "Paper One" }] },
    isLoading: false,
  }),
}));
vi.mock("@/lib/api/sessions", () => ({
  useSetQuestionState: () => ({ mutate: mutateState, isPending: false }),
}));
vi.mock("@/lib/api/wrong-book", () => ({
  useWrongBook: (tab: string) => ({
    data:
      tab === "wrong"
        ? {
            items: [
              {
                question_id: "q1",
                question_type: "single_choice",
                stem: { en: "Stem en", zh: "题干" },
                options: [
                  {
                    order_index: 0,
                    content: { en: "a", zh: "甲" },
                    explanation: { en: null, zh: null },
                  },
                ],
                correct_indexes: [0],
                rationale: { en: "r", zh: "解析" },
                wrong_count: 3,
                last_wrong_at: null,
                is_mastered: false,
                is_bookmarked: false,
                is_flagged_review: false,
                mastery_level: "learning",
                papers: ["Paper One"],
              },
            ],
            total: 1,
          }
        : { items: [], total: 0 },
  }),
  useWrongBookPractice: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { WrongBookView } from "../wrong-book-view";

describe("<WrongBookView>", () => {
  beforeEach(() => {
    push.mockReset();
    mutateState.mockReset();
  });

  it("wrong tab lists items with wrong-count and paper attribution", () => {
    renderWithProviders(<WrongBookView />);
    expect(screen.getByText("题干")).toBeInTheDocument();
    expect(screen.getByText("Wrong 3x")).toBeInTheDocument();
    expect(screen.getAllByText(/Paper One/).length).toBeGreaterThan(0);
  });

  it("mark mastered calls the state API", async () => {
    renderWithProviders(<WrongBookView />);
    await userEvent.click(screen.getByRole("button", { name: "Mark mastered" }));
    expect(mutateState).toHaveBeenCalledWith({
      question_id: "q1",
      is_mastered: true,
    });
  });

  it("expands the explanation with the correct answer highlighted", async () => {
    renderWithProviders(<WrongBookView />);
    await userEvent.click(screen.getByRole("button", { name: "Show explanation" }));
    expect(screen.getByText("解析")).toBeInTheDocument();
    expect(screen.getByText("甲")).toBeInTheDocument();
  });

  it("switches tabs", async () => {
    renderWithProviders(<WrongBookView />);
    await userEvent.click(screen.getByRole("button", { name: "Bookmarked" }));
    expect(screen.getByText("Nothing here yet.")).toBeInTheDocument();
  });
});
