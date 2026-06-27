import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { I18nProvider, useI18n } from "../provider";

function Probe() {
  const { t, locale, setLocale } = useI18n();
  return (
    <div>
      <p>{t("common.save")}</p>
      <p data-testid="loc">{locale}</p>
      <button onClick={() => setLocale("zh")}>switch</button>
    </div>
  );
}

describe("I18nProvider", () => {
  it("renders with initialLocale en", () => {
    render(
      <I18nProvider initialLocale="en">
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByTestId("loc")).toHaveTextContent("en");
  });

  it("switches locale and translates", () => {
    render(
      <I18nProvider initialLocale="en">
        <Probe />
      </I18nProvider>,
    );
    act(() => screen.getByText("switch").click());
    expect(screen.getByTestId("loc")).toHaveTextContent("zh");
    expect(screen.getByText("保存")).toBeInTheDocument();
  });
});
