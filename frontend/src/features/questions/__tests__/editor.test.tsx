import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mutate = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/taxonomy", () => ({
  useDomains: () => ({ data: [], isLoading: false }),
}));
vi.mock("@/lib/api/questions", () => ({
  useCreateQuestion: () => ({ mutate, isPending: false }),
  useUpdateQuestion: () => ({ mutate, isPending: false }),
}));
vi.mock("@/components/ui/sonner", () => ({
  // Defined inside the factory so the hoisted mock is self-contained; the
  // import below resolves to this same singleton.
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { toast as toastImpl } from "@/components/ui/sonner";
import { QuestionEditor } from "@/features/questions/editor";

// The `vi.mock` below swaps `@/components/ui/sonner` for a `{ toast }` object
// whose members are vi.fn() mocks; cast to a mock-shaped interface so we can
// reset/assert on them (the real sonner `toast` is typed as a non-mock fn).
const toast = toastImpl as unknown as {
  success: ReturnType<typeof vi.fn>;
  error: ReturnType<typeof vi.fn>;
};

// Radix Tabs / Checkbox call Element#hasPointerCapture / releasePointerCapture /
// setPointerCapture / scrollIntoView while dispatching pointer events, which
// jsdom does not implement. Patch them for the lifetime of this suite so the
// language tabs and correctness checkboxes can be driven with userEvent in
// jsdom. Scoped to this file only (mirrors the exam start-form test).
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
  mutate.mockReset();
  push.mockReset();
  toast.success.mockReset();
  toast.error.mockReset();
});

async function fillEnglishBasics(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^stem$/i), "What is the CIA triad?");
  await user.type(screen.getByLabelText(/option 1 content/i), "Confidentiality, Integrity, Availability");
  await user.type(screen.getByLabelText(/option 2 content/i), "Certification, Identity, Audit");
  await user.type(screen.getByLabelText(/correct-answer rationale/i), "CIA = Confidentiality, Integrity, Availability.");
}

describe("QuestionEditor", () => {
  it("enables save after filling the English tab + canonical options and posts translations+options", async () => {
    const user = userEvent.setup();
    render(<QuestionEditor />);

    await fillEnglishBasics(user);
    await user.click(screen.getByRole("button", { name: /create question/i }));

    expect(mutate).toHaveBeenCalledTimes(1);
    const payload = mutate.mock.calls[0][0];
    // Canonical options: shared correctness + order, no per-language content here.
    expect(payload.options).toEqual([
      { order_index: 0, is_correct: true },
      { order_index: 1, is_correct: false },
    ]);
    // English translation carries the per-language stem / option content / rationale.
    expect(payload.translations).toEqual([
      {
        language: "en",
        stem: "What is the CIA triad?",
        correct_answer_rationale: "CIA = Confidentiality, Integrity, Availability.",
        options: [
          { order_index: 0, content: "Confidentiality, Integrity, Availability" },
          { order_index: 1, content: "Certification, Identity, Audit" },
        ],
      },
    ]);
    expect(payload.mappings).toEqual({});
    expect(payload.question_type).toBe("single_choice");
  });

  it("blocks save with a toast when the Chinese tab is enabled but its stem is blank", async () => {
    const user = userEvent.setup();
    render(<QuestionEditor />);

    await fillEnglishBasics(user);

    // Enable the Chinese version (zh starts null) and switch to its tab.
    await user.click(screen.getByRole("button", { name: /add chinese version/i }));

    // Leave the Chinese stem blank and attempt to save.
    await user.click(screen.getByRole("button", { name: /create question/i }));

    expect(mutate).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });
});
