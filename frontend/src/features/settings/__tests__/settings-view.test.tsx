import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "@/lib/i18n/provider";
import { SettingsView } from "../settings-view";

vi.mock("@/lib/api/preferences", () => ({
  usePreferences: () => ({
    data: { language_mode: "en", interface_language: "en" },
  }),
  useUpdatePreferences: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateInterfaceLanguage: () => ({ mutate: vi.fn(), isPending: false }),
}));

function wrap(ui: React.ReactNode, initialLocale: "en" | "zh" = "en") {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider initialLocale={initialLocale}>{ui}</I18nProvider>
    </QueryClientProvider>,
  );
}

describe("SettingsView", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.hasPointerCapture = vi.fn();
    window.HTMLElement.prototype.releasePointerCapture = vi.fn();
    window.HTMLElement.prototype.setPointerCapture = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("renders both language cards in English", () => {
    wrap(<SettingsView />);
    expect(screen.getAllByText(/Interface language/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Question content language/i).length).toBeGreaterThan(0);
  });

  it("has a Settings page header", () => {
    wrap(<SettingsView />);
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
  });

  it("renders in Chinese when locale is zh", () => {
    wrap(<SettingsView />, "zh");
    expect(screen.getByRole("heading", { name: "设置" })).toBeInTheDocument();
    expect(screen.getAllByText("界面语言").length).toBeGreaterThan(0);
  });
});
