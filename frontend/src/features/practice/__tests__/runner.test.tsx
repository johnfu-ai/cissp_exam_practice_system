import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render-with-providers";
import type {
  AnswerResult,
  QuestionDelivery,
  RelatedQuestion,
  SessionOut,
} from "@/lib/api/types";

// Per-hook vi.fn()s are auto-hoisted, so the vi.mock factory below can close over
// them. Each test configures the return values it needs via `install(...)`.
const useSessionImpl = vi.fn();
const useQuestionImpl = vi.fn();
const useRelatedImpl = vi.fn(() => ({ data: [] as RelatedQuestion[], isLoading: false }));
const submitMutate = vi.fn();
const updateStateMutate = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api/practice", () => ({
  useSession: () => useSessionImpl(),
  useQuestion: () => useQuestionImpl(),
  useSubmitAnswer: () => ({ mutate: submitMutate, isPending: false }),
  usePauseSession: () => ({ mutate: vi.fn() }),
  useResumeSession: () => ({ mutate: vi.fn() }),
  useFinishSession: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateQuestionState: () => ({ mutate: updateStateMutate }),
  useRelatedQuestions: () => useRelatedImpl(),
}));
vi.mock("@/components/ui/sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn(), message: vi.fn() },
}));
vi.mock("@/features/practice/session-tracker", () => ({ untrackSession: vi.fn() }));

import { Runner } from "@/features/practice/runner";

// Radix Dialog/Select call Element#hasPointerCapture / releasePointerCapture /
// setPointerCapture / scrollIntoView while opening (focus trap + viewport
// scrolling), which jsdom does not implement. Patch them for the suite so the
// NoteDialog can be driven with userEvent. (Mirrors the cat-runner test harness.)
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

function makeDelivery(overrides: Partial<QuestionDelivery> = {}): QuestionDelivery {
  return {
    session_id: "s1",
    position: 0,
    total: 3,
    // q-aaa seed permutes [0,1,2] -> [1,2,0] (Bravo, Charlie, Alpha) under
    // shuffleBySeed, so shuffle tests can assert a non-identity permutation.
    question_id: "q-aaa",
    question_type: "single_choice",
    available_languages: ["en", "zh"],
    language_mode: "en",
    stem: { en: "Stem EN", zh: "题干 ZH" },
    options: [
      { id: "o0", order_index: 0, content: { en: "Alpha", zh: "阿尔法" }, content_format: { en: "plain", zh: "plain" } },
      { id: "o1", order_index: 1, content: { en: "Bravo", zh: "布拉沃" }, content_format: { en: "plain", zh: "plain" } },
      { id: "o2", order_index: 2, content: { en: "Charlie", zh: "查理" }, content_format: { en: "plain", zh: "plain" } },
    ],
    elapsed_ms: 0,
    previous_answer: null,
    note: null,
    ...overrides,
  };
}

function makeSession(overrides: Partial<SessionOut> = {}): SessionOut {
  return {
    id: "s1",
    status: "in_progress",
    total_questions: 3,
    correct_count: 0,
    started_at: new Date(Date.now() - 60_000).toISOString(),
    ended_at: null,
    paused_at: null,
    config: {},
    ...overrides,
  };
}

const ANSWER_RESULT: AnswerResult = {
  is_correct: true,
  correct_indexes: [1],
  selected_indexes: [1],
  correct_rationale: { en: null, zh: null },
  key_point_summary: { en: null, zh: null },
  per_option: [],
  mapping: {},
  history: [],
};

function install(session: SessionOut, delivery: QuestionDelivery) {
  useSessionImpl.mockReturnValue({
    data: session, isLoading: false, isError: false, error: null,
  });
  useQuestionImpl.mockReturnValue({
    data: delivery, isLoading: false, isError: false, error: null, refetch: vi.fn(),
  });
}

beforeEach(() => {
  submitMutate.mockReset();
  updateStateMutate.mockReset();
  useRelatedImpl.mockReturnValue({ data: [], isLoading: false });
  // Default: a submit succeeds so the runner can transition to "submitted",
  // which is required to surface the NoteDialog (it only renders post-submit).
  submitMutate.mockImplementation((_payload, handlers) => {
    handlers?.onSuccess?.(ANSWER_RESULT);
  });
});

describe("Runner timer (#36-rem / FR-PRAC-09)", () => {
  it("renders a live session timer and a per-question timer", () => {
    install(makeSession(), makeDelivery());
    renderWithProviders(<Runner sessionId="s1" />);

    const sessionTime = screen.getByTitle("Session time");
    const questionTime = screen.getByTitle("This question");
    // Both render a m:ss duration (session started 60s ago -> ~1:00; this
    // question just started -> ~0:00). The Clock icon has no text content.
    expect(sessionTime.textContent ?? "").toMatch(/\d+:\d{2}/);
    expect(questionTime.textContent ?? "").toMatch(/\d+:\d{2}/);
  });
});

describe("Runner option shuffle (#36-rem / §8.1)", () => {
  it("shuffles display order deterministically: same seed -> same order, differs from canonical", () => {
    install(makeSession({ config: { shuffle_options: true } }), makeDelivery());
    const { unmount } = renderWithProviders(<Runner sessionId="s1" />);
    const order1 = screen
      .getAllByText(/^(Alpha|Bravo|Charlie)$/)
      .map((el) => el.textContent);
    unmount();

    install(makeSession({ config: { shuffle_options: true } }), makeDelivery());
    renderWithProviders(<Runner sessionId="s1" />);
    const order2 = screen
      .getAllByText(/^(Alpha|Bravo|Charlie)$/)
      .map((el) => el.textContent);

    // Deterministic: the same question_id seed yields the same display order
    // across separate renders (stable across re-renders / re-fetches).
    expect(order2).toEqual(order1);
    // Actually shuffled: not the canonical [Alpha, Bravo, Charlie] order.
    expect(order2).not.toEqual(["Alpha", "Bravo", "Charlie"]);
    // Still a permutation - no option dropped or duplicated.
    expect([...order2].sort()).toEqual(["Alpha", "Bravo", "Charlie"]);
  });

  it("keeps selection canonical: a displayed option submits its own order_index, not its display position", async () => {
    const user = userEvent.setup();
    install(makeSession({ config: { shuffle_options: true } }), makeDelivery());
    renderWithProviders(<Runner sessionId="s1" />);

    // q-aaa permutes [0,1,2] -> [1,2,0]: display order is Bravo, Charlie, Alpha.
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);

    // Click the FIRST displayed radio. It is "Bravo" (canonical order_index 1),
    // which under canonical ordering would sit at position 1, not 0.
    await user.click(radios[0]);
    await user.click(screen.getByRole("button", { name: /^Submit$/ }));

    expect(submitMutate).toHaveBeenCalledTimes(1);
    // The invariant: `selected` carries the option's canonical order_index (1),
    // NOT its shuffled display position (0). Judging reads `is_correct` from the
    // snapshot by order_index, so a display-position selection would be misjudged.
    expect(submitMutate.mock.calls[0][0]).toMatchObject({ position: 0, selected: [1] });
  });
});

describe("Runner NoteDialog (#36-rem / FR-ANS-07)", () => {
  it("pre-loads the existing note when opened", async () => {
    const user = userEvent.setup();
    install(makeSession(), makeDelivery({ note: "existing note" }));
    renderWithProviders(<Runner sessionId="s1" />);

    await user.click(screen.getAllByRole("radio")[0]);
    await user.click(screen.getByRole("button", { name: /^Submit$/ }));
    // Submitted -> the per-question "Add note" action appears.
    await user.click(screen.getByRole("button", { name: /add note/i }));

    const textbox = await screen.findByRole("textbox");
    expect(textbox).toHaveValue("existing note");
  });

  it("starts empty when no note exists", async () => {
    const user = userEvent.setup();
    install(makeSession(), makeDelivery({ note: null }));
    renderWithProviders(<Runner sessionId="s1" />);

    await user.click(screen.getAllByRole("radio")[0]);
    await user.click(screen.getByRole("button", { name: /^Submit$/ }));
    await user.click(screen.getByRole("button", { name: /add note/i }));

    const textbox = await screen.findByRole("textbox");
    expect(textbox).toHaveValue("");
  });
});
