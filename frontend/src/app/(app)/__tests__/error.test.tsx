import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render-with-providers";
import AppError from "../error";

describe("AppError boundary", () => {
  it("renders the title + retry button and calls reset on click", async () => {
    const reset = vi.fn();
    renderWithProviders(<AppError error={new Error("boom")} reset={reset} />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("renders in Chinese when locale is zh", () => {
    renderWithProviders(<AppError error={new Error("boom")} reset={vi.fn()} />, {
      initialLocale: "zh",
    });
    expect(screen.getByText("出错了")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
  });
});
