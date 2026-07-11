# Plan: #34 — Keyboard answer submission + WCAG AA contrast (NFR-UX-04/05/06)

**Branch:** `fix/p3-keyboard-a11y-contrast` (off `master` at `e758f99`)
**Scope:** PRD §7.4 NFR-UX-04 (keyboard select + submit), NFR-UX-05 (color not the only cue), NFR-UX-06 (WCAG 2.1 AA). Audit item #34.

## Findings from exploration

- **Selection already works via keyboard.** `OptionList` (`features/practice/option-list.tsx`) wraps shadcn `RadioGroup`/`Checkbox` (Radix). Tab enters the group, arrows move+select radios, space toggles checkboxes. The gap is **submission/advance** — there is no `onKeyDown` anywhere, so the only keyboard path is Tab→Submit→Enter.
- **Contrast fails AA.** `--success` #34C759 = 2.22:1 on white (fails even 3:1 UI); `--destructive` #FF3B30 = 3.55:1 (fails 4.5:1 normal text). Used as `text-success`/`text-destructive` on white in all three runners, `summary.tsx`, `exam/review.tsx`, `exam/report.tsx`, login/register/settings error text, and as `bg-*` with white `*-foreground` in `badge.tsx`/`button.tsx`.
- **NFR-UX-05 mostly satisfied** via `CheckCircle2`/`XCircle` icons + "Correct/Incorrect" text in result panels, and Radix's filled radio dot / checkbox check. **Gap:** per-option correctness in `OptionList` result mode is signaled by border color only (no per-option icon).
- **CAT invariant (`cat-runner.test.tsx`):** toggling language must never call `/next` refetch, `submitMutate`, or `finishMutate`. The test drives the language `<Select>` with `userEvent.click` (no `Enter`), so a document-level Enter handler will not interfere — verified.

## Implementation

### 1. Contrast tokens — `frontend/src/app/globals.css`
Darken two tokens (single-source change, propagates everywhere via `hsl(var(--*))`):
- `--success: 142 71% 53%;` → `142 72% 29%;` (#15803D, **5.02:1** on white, white-on-fill)
- `--destructive: 0 100% 60%;` → `0 72% 51%;` (#DC2626, **4.83:1** on white, white-on-fill)

Leave `--primary`/`--ring` (#007AFF, 4.02:1 — fails as text but used mainly as fill/UI-ring at 3:1) **out of scope**; `text-primary` link contrast is a separate follow-up, not audit #34. No other files change (Tailwind maps tokens at build time).

### 2. New shared hook — `frontend/src/features/shared/use-submit-shortcut.ts`
```ts
useSubmitShortcut({ onSubmit, onNext?, canSubmit, canNext?, enabled = true })
```
- Registers one `document` `keydown` listener (cleaned up on unmount).
- On `e.key === "Enter"` only, when `enabled`:
  - **Bail** (let native handle) if `e.target` is inside: `input, textarea, select, [contenteditable="true"], [role="checkbox"], [role="option"], [role="combobox"], [role="dialog"], [data-radix-popper-content-wrapper]`, or a non-radio `<button>` (Submit/Next/palette buttons handle themselves natively → no double-submit).
  - **Do NOT bail on `[role="radio"]`** — Radix radio Enter is a no-op re-select, so Enter on a focused radio cleanly submits. (For multi-choice checkboxes, Enter toggles → bailed.)
  - If `canSubmit` → `e.preventDefault(); onSubmit()`. Else if `canNext` → `e.preventDefault(); onNext()`.
- This yields the flow: single-choice → arrows/click to pick, **Enter submits**; multi-choice → space to toggle each, Tab→Submit→Enter; body-focus Enter also submits.

### 3. Wire the hook into the three runners
- **`features/practice/runner.tsx`**: `onSubmit=submit` (`canSubmit = !submitted && canSubmit(runner) && !paused && !submitAnswer.isPending`), `onNext=next` (`canNext = submitted && !finish.isPending`).
- **`features/exam/cat-runner.tsx`**: `onSubmit=submitAndAdvance` (`canSubmit = selected.length>0 && !submit.isPending`). No `onNext` (forward-only). `enabled` always true while rendered.
- **`features/exam/fixed-runner.tsx`**: `onSubmit` = forward action (`position+1<total ? () => goTo(position+1) : () => save()`, `canSubmit = !submit.isPending`). No `onNext`.

### 4. `OptionList` a11y — `features/practice/option-list.tsx`
- Add row-level visible focus: append `has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:focus-visible]:ring-offset-2` to the option `<label>` className (Tailwind 3.4 `has-*` variant). Keyboard focus now highlights the whole row, not just the 20px control.
- **NFR-UX-05 non-color cue per option in result mode:** when `result` is set, render a small `aria-hidden` `CheckCircle2` (lucide) for `correct.has(i)` options and `XCircle` for selected-but-not-correct options, at the row end. Existing `radio`/`checkbox` roles and option text nodes are unchanged → existing `option-list.test.tsx` queries still resolve.

### 5. Tests
- **New `features/shared/__tests__/use-submit-shortcut.test.tsx`** (`renderHook` + `fireEvent.keyDown`): Enter calls `onSubmit` when `canSubmit`; does nothing when `!canSubmit`; calls `onNext` when `canNext && !canSubmit`; bails when target is `textarea`/`button`/`[role="checkbox"]`/inside `[role="dialog"]`; `enabled=false` disables entirely.
- **Extend `features/practice/__tests__/option-list.test.tsx`**: in result mode, correct option shows a check icon, wrong-selected shows an X (assert via `querySelector('svg.lucide-check-circle2')` / role-free presence — keep `radio`/`checkbox`/text assertions intact).
- **Extend `features/exam/__tests__/cat-runner.test.tsx`**: add a case — select option 0, `fireEvent.keyDown(document.body, {key:"Enter"})` → `submitMutate` called; with no selection → not called. Existing language-toggle test stays unchanged and green.
- **No new i18n strings** (shortcut is invisible; icons are decorative `aria-hidden`) → no `locales` parity changes needed.

## Verification
- `npm run test` (expect 97 + ~6 new = ~103, all green; existing CAT invariant + option-list queries unchanged).
- `npm run lint` (0 errors; the `react-hooks/set-state-in-effect` warns are pre-existing).
- `npm run build` (16 routes, 0 errors).
- Manual contrast recheck: the node contrast script already confirms 5.02:1 / 4.83:1.

## Non-goals / follow-ups (not in this change)
- `--primary`/`--ring` text-contrast (#007AFF links/icons at 4.02:1) — separate item.
- Number-key (1–9) selection shortcut — Enter is sufficient for NFR-UX-04.
- Auto-focus management on question change (focus the question heading) — optional polish, risk of test churn; skipped.
- Visible "Press Enter to submit" hint — would need en/zh strings; skipped to stay scoped.
