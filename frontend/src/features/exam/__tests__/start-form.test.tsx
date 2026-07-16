import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render-with-providers";
import userEvent from "@testing-library/user-event";
import { useAuthStore } from "@/lib/auth-store";
import type { AuthUser } from "@/lib/auth-store";
import type { LanguageMode } from "@/lib/api/types";

const mutate = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/exam", () => ({
  useCreateExam: () => ({ mutate, isPending: false }),
}));

import { ExamStartForm } from "@/features/exam/start-form";

// Radix Select calls Element#hasPointerCapture / releasePointerCapture while
// dispatching pointer events, which jsdom does not implement. Patch them for
// the lifetime of this suite so the language-mode <Select> can be driven with
// userEvent in jsdom. Scoped to this file only.
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

function userWith(language_mode: LanguageMode): AuthUser {
  return {
    id: "u1",
    email: "a@b.c",
    display_name: null,
    roles: [],
    perms: [],
    language_mode,
    interface_language: "en",
  };
}

beforeEach(() => {
  mutate.mockReset();
  push.mockReset();
  useAuthStore.setState({
    user: null,
    accessToken: null,
    hydrated: false,
  });
});

describe("ExamStartForm", () => {
  it("posts language_mode when starting a fixed exam", async () => {
    useAuthStore.setState({
      user: userWith("en"),
      accessToken: "t",
      hydrated: true,
    });
    renderWithProviders(<ExamStartForm />);

    // Open the language-mode select and pick 中文 (zh).
    await userEvent.click(screen.getByRole("combobox", { name: /language mode/i }));
    await userEvent.click(screen.getByRole("option", { name: "中文" }));

    await userEvent.click(screen.getByRole("button", { name: /start fixed exam/i }));

    expect(mutate).toHaveBeenCalledTimes(1);
    // count left blank → omitted from the body (brief: { kind, language_mode }).
    expect(mutate.mock.calls[0][0]).toEqual({ kind: "fixed", language_mode: "zh" });
  });

  it("defaults language_mode to the user preference and sends it for CAT", async () => {
    useAuthStore.setState({
      user: userWith("zh"),
      accessToken: "t",
      hydrated: true,
    });
    renderWithProviders(<ExamStartForm />);

    // Switch to the CAT card (form defaults to "fixed").
    await userEvent.click(screen.getByRole("button", { name: /cat mock exam/i }));
    await userEvent.click(screen.getByRole("button", { name: /start cat exam/i }));

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({ kind: "cat", language_mode: "zh" });
  });
});
