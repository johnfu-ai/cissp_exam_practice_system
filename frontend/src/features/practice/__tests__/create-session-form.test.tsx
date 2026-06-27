import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render-with-providers";
import userEvent from "@testing-library/user-event";

const mutate = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/taxonomy", () => ({
  useDomains: () => ({ data: [], isLoading: false }),
  useBooks: () => ({ data: [], isLoading: false }),
  useChapters: () => ({ data: [], isLoading: false }),
  useTags: () => ({ data: [], isLoading: false }),
}));
vi.mock("@/lib/api/practice", () => ({
  useCreateSession: () => ({ mutate, isPending: false }),
}));

import { CreateSessionForm } from "@/features/practice/create-session-form";

beforeEach(() => {
  mutate.mockReset();
  push.mockReset();
});

describe("CreateSessionForm", () => {
  it("submits count + defaults using backend field names", async () => {
    renderWithProviders(<CreateSessionForm />);
    const count = screen.getByLabelText(/number of questions/i);
    await userEvent.clear(count);
    await userEvent.type(count, "15");
    await userEvent.click(screen.getByRole("button", { name: /start practice/i }));

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({ count: 15, subset: "all", order_mode: "random" });
  });

  it("disables Start when count is below 1", async () => {
    renderWithProviders(<CreateSessionForm />);
    const count = screen.getByLabelText(/number of questions/i);
    await userEvent.clear(count);
    await userEvent.type(count, "0");
    expect(screen.getByRole("button", { name: /start practice/i })).toBeDisabled();
  });
});
