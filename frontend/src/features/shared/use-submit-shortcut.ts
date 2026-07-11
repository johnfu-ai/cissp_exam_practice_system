"use client";

import { useEffect } from "react";

/**
 * #34 / NFR-UX-04: lets a user submit (and, where supported, advance) with the
 * keyboard instead of reaching for the mouse. Registers one document-level
 * `keydown` listener that fires `onSubmit` on Enter when `canSubmit`, else
 * `onNext` when `canNext`.
 *
 * Bail-out rules (let the focused control handle Enter natively, so we never
 * double-act or clobber a text field):
 *  - the target is / is inside an editable field: `input`, `textarea`,
 *    `select`, `[contenteditable="true"]`;
 *  - the target is a non-radio button (the Submit/Next/palette buttons, or a
 *    checkbox - those activate/toggle on Enter themselves). Radios are NOT
 *    bailed: Radix's radio Enter is a no-op re-select, so Enter on a focused
 *    radio cleanly submits the current selection;
 *  - the target is inside an open overlay: a Select option/combobox, a dialog,
 *    or a Radix popper (`[data-radix-popper-content-wrapper]`).
 *
 * For multi-select (checkboxes) Enter toggles the option - to submit, the user
 * tabs to the Submit button and presses Enter (native).
 */
export function useSubmitShortcut({
  onSubmit,
  onNext,
  canSubmit,
  canNext = false,
  enabled = true,
}: {
  onSubmit: () => void;
  onNext?: () => void;
  canSubmit: boolean;
  canNext?: boolean;
  enabled?: boolean;
}) {
  useEffect(() => {
    if (!enabled) return;
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Enter") return;
      const t = e.target;
      // keydown targets are normally the focused Element; guard against the
      // rare non-Element target (e.g. document) so closest() can't throw.
      if (!(t instanceof Element)) return;
      // Editable fields + open overlays handle Enter themselves.
      if (
        t.closest(
          'input, textarea, select, [contenteditable="true"], ' +
            '[role="checkbox"], [role="option"], [role="combobox"], ' +
            '[role="dialog"], [data-radix-popper-content-wrapper]',
        )
      ) {
        return;
      }
      // A non-radio button (Submit/Next/palette/checkbox-as-button) activates
      // natively on Enter - don't also fire the shortcut (avoids double submit).
      if (t.closest("button") && !t.closest('[role="radio"]')) return;

      if (canSubmit) {
        e.preventDefault();
        onSubmit();
      } else if (canNext && onNext) {
        e.preventDefault();
        onNext();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onSubmit, onNext, canSubmit, canNext, enabled]);
}
