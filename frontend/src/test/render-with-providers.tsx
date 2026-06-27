"use client";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "@/lib/i18n/provider";
import type { Locale } from "@/lib/i18n/types";
import type { ReactElement } from "react";

/**
 * Render a component wrapped in QueryClientProvider + I18nProvider.
 * Use this for any component that calls `useT()` / `useI18n()`.
 * `initialLocale` defaults to "en" so existing English-text assertions
 * continue to resolve.
 */
export function renderWithProviders(
  ui: ReactElement,
  { initialLocale = "en", ...opts }: { initialLocale?: Locale } & RenderOptions = {},
) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider initialLocale={initialLocale}>{ui}</I18nProvider>
    </QueryClientProvider>,
    opts,
  );
}
