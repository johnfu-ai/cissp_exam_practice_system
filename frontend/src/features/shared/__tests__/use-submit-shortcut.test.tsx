import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { useSubmitShortcut } from "@/features/shared/use-submit-shortcut";

function setup(opts: {
  canSubmit?: boolean;
  canNext?: boolean;
  enabled?: boolean;
}) {
  const onSubmit = vi.fn();
  const onNext = vi.fn();
  function Harness() {
    useSubmitShortcut({
      onSubmit,
      onNext,
      canSubmit: opts.canSubmit ?? true,
      canNext: opts.canNext ?? false,
      enabled: opts.enabled ?? true,
    });
    return (
      <div>
        <div data-testid="plain" tabIndex={0}>plain</div>
        <textarea data-testid="ta" />
        <button type="button" data-testid="btn">btn</button>
        <div role="dialog">
          <button type="button" data-testid="dlg-btn">dlg</button>
        </div>
        <span role="checkbox" aria-checked={false} tabIndex={0} data-testid="cb">cb</span>
        <span role="radio" aria-checked={false} tabIndex={0} data-testid="rd">rd</span>
        <span role="combobox" aria-expanded={false} aria-controls="combo-list" tabIndex={0} data-testid="combo">combo</span>
      </div>
    );
  }
  const utils = render(<Harness />);
  return { onSubmit, onNext, ...utils };
}

describe("useSubmitShortcut (#34 NFR-UX-04)", () => {
  it("fires onSubmit on Enter when canSubmit", () => {
    const { onSubmit, onNext, getByTestId } = setup({ canSubmit: true });
    fireEvent.keyDown(getByTestId("plain"), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onNext).not.toHaveBeenCalled();
  });

  it("fires onNext when not canSubmit but canNext", () => {
    const { onSubmit, onNext, getByTestId } = setup({ canSubmit: false, canNext: true });
    fireEvent.keyDown(getByTestId("plain"), { key: "Enter" });
    expect(onNext).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does nothing when neither canSubmit nor canNext", () => {
    const { onSubmit, onNext, getByTestId } = setup({ canSubmit: false, canNext: false });
    fireEvent.keyDown(getByTestId("plain"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
    expect(onNext).not.toHaveBeenCalled();
  });

  it("ignores non-Enter keys", () => {
    const { onSubmit, getByTestId } = setup({ canSubmit: true });
    fireEvent.keyDown(getByTestId("plain"), { key: " " });
    fireEvent.keyDown(getByTestId("plain"), { key: "ArrowDown" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("bails on textarea (lets the field handle Enter)", () => {
    const { onSubmit, getByTestId } = setup({ canSubmit: true });
    fireEvent.keyDown(getByTestId("ta"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("bails on a plain button (native activation, no double-submit)", () => {
    const { onSubmit, getByTestId } = setup({ canSubmit: true });
    fireEvent.keyDown(getByTestId("btn"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("bails inside an open dialog", () => {
    const { onSubmit, getByTestId } = setup({ canSubmit: true });
    fireEvent.keyDown(getByTestId("dlg-btn"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("bails on a checkbox (Enter toggles, not submits)", () => {
    const { onSubmit, getByTestId } = setup({ canSubmit: true });
    fireEvent.keyDown(getByTestId("cb"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("bails on a combobox (Select trigger)", () => {
    const { onSubmit, getByTestId } = setup({ canSubmit: true });
    fireEvent.keyDown(getByTestId("combo"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does NOT bail on a radio - Enter submits (Radix radio Enter is a no-op re-select)", () => {
    const { onSubmit, getByTestId } = setup({ canSubmit: true });
    fireEvent.keyDown(getByTestId("rd"), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("does nothing when disabled", () => {
    const { onSubmit, getByTestId } = setup({ canSubmit: true, enabled: false });
    fireEvent.keyDown(getByTestId("plain"), { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
