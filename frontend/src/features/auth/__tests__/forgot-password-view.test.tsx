import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "@/lib/i18n/provider";
import { ForgotPasswordView } from "../forgot-password-view";

function wrap(ui: React.ReactNode, initialLocale: "en" | "zh" = "en") {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider initialLocale={initialLocale}>{ui}</I18nProvider>
    </QueryClientProvider>,
  );
}

describe("ForgotPasswordView", () => {
  beforeEach(() => {
    window.HTMLElement.prototype.hasPointerCapture = vi.fn();
    window.HTMLElement.prototype.releasePointerCapture = vi.fn();
    window.HTMLElement.prototype.setPointerCapture = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("renders the request step in English", () => {
    wrap(<ForgotPasswordView />);
    expect(screen.getByRole("heading", { name: "Reset password" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send reset token" })).toBeEnabled();
    // confirm-step controls are not shown until a token is requested
    expect(screen.queryByLabelText("Reset token")).not.toBeInTheDocument();
  });

  it("renders in Chinese when locale is zh", () => {
    wrap(<ForgotPasswordView />, "zh");
    expect(screen.getByRole("heading", { name: "重置密码" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送重置令牌" })).toBeEnabled();
    expect(screen.getByText("返回登录")).toBeInTheDocument();
  });
});
