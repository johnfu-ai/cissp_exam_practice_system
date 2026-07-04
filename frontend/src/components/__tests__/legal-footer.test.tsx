import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render-with-providers";
import { LegalFooter } from "@/components/legal-footer";

describe("LegalFooter", () => {
  it("renders the trademark + not-official disclaimers in English", () => {
    renderWithProviders(<LegalFooter />);
    expect(
      screen.getByText(/CISSP® and ISC2® are registered trademarks of ISC2, Inc\./i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/not an official ISC2 exam platform/i),
    ).toBeInTheDocument();
  });

  it("renders in Chinese when locale is zh", () => {
    renderWithProviders(<LegalFooter />, { initialLocale: "zh" });
    expect(screen.getByText(/CISSP® 与 ISC2® 是 ISC2, Inc\. 的注册商标。/)).toBeInTheDocument();
    expect(screen.getByText(/并非 ISC2 官方考试平台/)).toBeInTheDocument();
  });

  it("is marked as a contentinfo landmark", () => {
    renderWithProviders(<LegalFooter />);
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  });
});
