import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ExamQuestionDelivery, ExamSession } from "@/lib/api/types";

// Refetch spy for useExamNext — toggling language must never trigger it.
const refetch = vi.fn();
const submitMutate = vi.fn();
const finishMutate = vi.fn();

const delivery: ExamQuestionDelivery = {
  session_id: "s1",
  position: 0,
  total: 100,
  question_id: "q-aaa",
  question_type: "single_choice",
  available_languages: ["en", "zh"],
  language_mode: "en",
  stem: { en: "Stem EN", zh: "题干 ZH" },
  options: [
    {
      id: "o1",
      order_index: 0,
      content: { en: "Opt EN A", zh: "选项甲" },
      content_format: { en: "markdown", zh: "markdown" },
    },
    {
      id: "o2",
      order_index: 1,
      content: { en: "Opt EN B", zh: "选项乙" },
      content_format: { en: "markdown", zh: "markdown" },
    },
  ],
  elapsed_ms: 0,
  time_remaining_ms: 3_600_000,
  previous_answer: null,
};

const session: ExamSession = {
  id: "s1",
  status: "in_progress",
  session_kind: "cat",
  total_questions: 0,
  correct_count: 0,
  started_at: "",
  ended_at: null,
  time_remaining_ms: 3_600_000,
  config: {},
};

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api/exam", () => ({
  useExamNext: () => ({
    data: delivery,
    isLoading: false,
    isError: false,
    error: null,
    refetch,
  }),
  useSubmitExamAnswer: () => ({ mutate: submitMutate, isPending: false }),
  useFinishExam: () => ({ mutate: finishMutate, isPending: false }),
}));
vi.mock("@/components/ui/sonner", () => ({
  toast: { error: vi.fn(), message: vi.fn(), success: vi.fn() },
}));
vi.mock("@/features/exam/exam-tracker", () => ({ untrackExam: vi.fn() }));

import { CatExamRunner } from "@/features/exam/cat-runner";

// Radix Select calls Element#hasPointerCapture / releasePointerCapture /
// setPointerCapture / scrollIntoView while dispatching pointer events, which
// jsdom does not implement. Patch them for the lifetime of this suite so the
// language-mode <Select> can be driven with userEvent in jsdom. (Mirrors the
// exam start-form and question editor test harnesses.)
const proto = Element.prototype as unknown as {
  hasPointerCapture?: unknown;
  releasePointerCapture?: unknown;
  setPointerCapture?: unknown;
  scrollIntoView?: unknown;
};
const saved = {
  hasPointerCapture: proto.hasPointerCapture,
  releasePointerCapture: proto.releasePointerCapture,
  setPointerCapture: proto.setPointerCapture,
  scrollIntoView: proto.scrollIntoView,
};
proto.hasPointerCapture = proto.hasPointerCapture ?? (() => false);
proto.releasePointerCapture = proto.releasePointerCapture ?? (() => undefined);
proto.setPointerCapture = proto.setPointerCapture ?? (() => undefined);
proto.scrollIntoView = proto.scrollIntoView ?? (() => undefined);
afterAll(() => {
  proto.hasPointerCapture = saved.hasPointerCapture;
  proto.releasePointerCapture = saved.releasePointerCapture;
  proto.setPointerCapture = saved.setPointerCapture;
  proto.scrollIntoView = saved.scrollIntoView;
});

beforeEach(() => {
  refetch.mockReset();
  submitMutate.mockReset();
  finishMutate.mockReset();
});

describe("CatExamRunner language-mode toggle", () => {
  it("toggles language locally without refetching /next or advancing the item", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    render(
      <QueryClientProvider client={queryClient}>
        <CatExamRunner sessionId="s1" session={session} />
      </QueryClientProvider>,
    );

    // Initial delivery: en mode, position 0 -> "Question 1". The English stem is
    // shown; the Chinese stem is not.
    expect(screen.getByText(/Question 1\b/)).toBeInTheDocument();
    expect(screen.getByText("Stem EN")).toBeInTheDocument();
    expect(screen.queryByText("题干 ZH")).not.toBeInTheDocument();

    // Open the language-mode <Select> (the only combobox in the runner) and pick 中文.
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: "中文" }));

    // The invariant: toggling language must ONLY mutate local `mode`. It must not
    // invalidate the /next query (which would refetch and could advance the CAT
    // item) nor call the delivery's refetch.
    expect(invalidateSpy).not.toHaveBeenCalled();
    expect(refetch).not.toHaveBeenCalled();

    // The same item is still on screen — position unchanged...
    expect(screen.getByText(/Question 1\b/)).toBeInTheDocument();
    // ...and the toggle took effect locally: the Chinese stem now renders and the
    // English stem is hidden (BilingualText in zh mode shows zh only).
    expect(screen.getByText("题干 ZH")).toBeInTheDocument();
    expect(screen.queryByText("Stem EN")).not.toBeInTheDocument();

    // No answer was submitted either (forward-only invariant untouched).
    expect(submitMutate).not.toHaveBeenCalled();
    expect(finishMutate).not.toHaveBeenCalled();
  });
});
