# Apple-inspired UI Redesign — Design Spec

**Date:** 2026-06-26
**Status:** Approved (brainstorm)
**Branch:** `feat/language-selection` (working tree: `frontend/` + new `cissp-exam-ui/`)

## 1. Goal

Apply the visual design language from the static mockups in `cissp-exam-ui/` (an
Apple-HIG-inspired design-tool export) to the existing Next.js frontend across **all
13 routes** — retheming the design tokens and restyling each page's composition while
preserving every existing behavior and the full test suite.

The mockup is a **visual reference, not code to port.** It ships as 7 static HTML
pages with inline styles and a CSS `mask-image` icon system; the existing app is a
React/shadcn app with its own component library. We adopt the mockup's *look*, not its
markup.

## 2. Scope

### In scope
- Retheme `globals.css` design tokens to the Apple palette.
- Add DM Sans via `next/font`; tune radius + add a shadow ramp.
- Restyle the shared shell (sidebar, auth layout) and **all 13 routes**:
  - 7 mocked pages (login, register, dashboard, practice-setup, quiz, explanation,
    cat-exam, exam-report) — match mockup composition closely.
  - 6 unmocked pages (analytics, import, questions list/new/edit/detail, review,
    taxonomy, admin) — extrapolate the language using the same tokens + patterns.
- Tune shadcn variants + add two small primitives (`<Eyebrow>`, an icon-leading
  field treatment) to match the mockup treatment.

### Out of scope
- Dark mode (the app has none today; the mockup's dark tokens are not wired up).
- Mobile/responsive beyond what exists today.
- New product features; any backend change.
- The mockup's `mask-image` SVG icon system (lucide-react is kept).
- The mockup's `partials/` HTML and `1.2rem`-everywhere radius.
- Behavior changes of any kind: auth, RBAC, exam/fixed/CAT runners, language toggle,
  timers, lazy auto-submit, forward-only CAT — all unchanged.

## 3. Decisions (from brainstorm)

| Decision | Choice |
|---|---|
| Dark mode | **Light only.** Mockup dark tokens noted but not wired. |
| Palette faithfulness | **Exact Apple palette** (#007AFF primary, DM Sans, full scales). |
| Unmocked pages | **Extrapolate** the language (tokens + established patterns). |
| Execution | **A. Token retheme + restyle** with existing shadcn primitives. No parallel component layer. |
| Radius | **Tuned**: `--radius: 0.75rem` app-wide; `--radius-lg: 1.2rem` for hero/marketing cards only. |
| Verification | Tests + lint + build + docker compose visual click-through. |

## 4. Token mapping

Rewrite the `:root` block in `src/app/globals.css`. Tokens stay HSL triplets so the
existing `hsl(var(--*))` Tailwind pipeline and `tailwind.config.ts` work unchanged.

| Role | Current | New | Hex |
|---|---|---|---|
| `--primary` | `221 83% 53%` | `211 100% 50%` | #007AFF |
| `--primary-foreground` | `0 0% 100%` | `0 0% 100%` | #FFFFFF |
| `--background` | `0 0% 100%` | `0 0% 100%` | #FFFFFF |
| `--foreground` | `222 47% 11%` | `231 33% 10%` | #1D1D1F |
| `--card` / `--popover` | `0 0% 100%` | `0 0% 100%` | #FFFFFF |
| `--secondary` / `--muted` / `--accent` | `210 40% 96%` | `240 20% 96%` | #F2F2F7 |
| `--muted-foreground` | `215 16% 47%` | `240 4% 46%` | #8E8E93 |
| `--border` / `--input` | `214 32% 91%` | `240 9% 90%` | #E5E5EA |
| `--destructive` | `0 72% 51%` | `0 100% 60%` | #FF3B30 |
| `--success` | `142 71% 45%` | `142 71% 53%` | #34C759 |
| `--ring` | `217 91% 60%` | `211 100% 50%` | #007AFF |
| `--radius` | `0.5rem` | `0.75rem` | — |
| `--radius-lg` (new) | — | `1.2rem` | hero/marketing cards |

**Canvas:** main content area uses a tinted canvas `#F7F7FA` (`240 20% 97%` via a new
`--canvas` token) so white cards lift, matching the mockup's dashboard. Auth pages use
the mockup's vertical gradient (`--background-100` → `--background-200`).

**Shadow ramp (new CSS vars, exposed as utilities):** `--shadow-2xs … --shadow-2xl`
ported from the mockup; expose `shadow-card` (≈`--shadow-md`) and `shadow-float`
(≈`--shadow-lg`) in `tailwind.config.ts`.

## 5. Typography

Add **DM Sans** via `next/font/google` in `src/app/layout.tsx`, assign to a
`--font-sans` CSS var and wire into `tailwind.config.ts` `theme.extend.fontFamily.sans`
as `["var(--font-sans)", ...systemFallback]`. No other font changes.

## 6. Component strategy

No parallel component layer. Tune existing shadcn variants + add two small primitives:

- **Button**: weight 600; primary CTAs on auth/hero pages use `rounded-full` (pill);
  standard radius elsewhere; heights 40 (default) / 44 (lg CTAs).
- **Card**: 1px border-first surface; default `shadow-card`; interactive media cards
  lift on hover (`hover:-translate-y-0.5 hover:shadow-float`).
- **Input**: add an optional icon-leading field treatment. Implemented as a small
  `Field` wrapper around `Input` (or a `leadingIcon` prop), **not** a parallel
  `.field/.control` class system. Keeps a11y on the existing Input.
- **`<Eyebrow>`** (new primitive): uppercase, tracked, muted-foreground label used
  for section headers throughout the mockup. ~10 lines.
- **Icons:** keep `lucide-react`. Do **not** port the mockup's `assets/icons/` SVGs
  or its `mask-image` technique. The mockup's icons all have lucide equivalents.

Existing `components/__tests__/*` target helpers/state-machines, not styles — they must
stay green unchanged.

## 7. Shell & navigation

- **`AppSidebar`**: Apple-style nav — 44px row height; active item as a tinted pill
  (`bg-accent` with `text-foreground`), inactive `text-muted-foreground`; a divider
  between primary nav and the permission-gated "Manage" group; sidebar surface white
  with a right border.
- **`(app)` layout**: main content on the `--canvas` tint; cards white with
  `shadow-card`.
- **`(auth)` layout**: centered card on the vertical gradient; logo mark in a
  `rounded-2xl` brand tile.

## 8. Per-route treatment

### Mocked pages (match mockup composition)
- **login / register**: centered card on gradient, logo tile, tab toggle (Sign
  In/Register), icon-leading email/password fields, pill submit, forgot-password link.
- **dashboard**: hero stat row + media-card grid + "Continue practicing" CTA.
- **practice-setup**: two-column card — filters left, summary + start CTA right.
- **quiz** (practice runner): question card with progress bar, option list with clear
  selection state, sticky footer (prev/next, flag, bookmark). Runner state machine
  untouched.
- **cat-exam**: same question-card shell, forward-only, persistent study-tool
  disclaimer; language toggle is pure client state (never advances `/next`).
- **explanation**: correctness banner + per-option review + explanation prose + next
  CTA.
- **exam-report**: score hero (scaled score + pass/fail), per-domain bars, time,
  wrong-question list; CAT report surfaces ability/CI/SEM/readiness + `DISCLAIMER`.

### Extrapolated pages (retheme + apply established patterns)
- **analytics**, **review**, **import**, **questions** (list/new/edit/detail),
  **taxonomy**, **admin**: page header with `<Eyebrow>` + title; card surfaces with
  `shadow-card`; consistent spacing scale; pill primary actions; hand-rolled charts
  recolored to the brand scale. Layouts stay structurally similar to today, re-skinned.

## 9. Testing & verification

1. `npm test` — all 67 existing frontend tests green.
2. `npm run lint` — clean.
3. `npm run build` — clean.
4. **Visual** (docker compose): `docker compose up -d --build`; click through
   login → dashboard → practice → fixed exam → CAT → report → analytics → questions
   → taxonomy → admin, in all three language modes (en / zh / bilingual), confirming
   the new look and **unchanged behavior** (auth, timers, auto-submit, forward-only
   CAT, language toggle, RBAC gating).

## 10. Risks

- **Inline-style translation:** the mockup leans on `style="..."`; in React these
  become className/utility or component props. Bulk of porting effort, low risk.
- **Radius at app density:** the mockup's `1.2rem` everywhere looks bubbly on inputs
  and dense tables — mitigated by the tuned `0.75rem` app / `1.2rem` hero split.
- **Extrapolation consistency:** 6 unmocked pages share no single source — mitigate
  by codifying patterns (eyebrow header, card surface, pill CTA) in §6/§7 first, then
  applying uniformly.
- **Test churn:** low — tests don't assert styles; confirm anyway.

## 11. Non-goals / explicitly preserved

Every behavior listed in `CLAUDE.md` and the FR-LANG work on this branch is preserved.
This is a CSS/className/layout-only change. No backend, no API, no data-model, no
state-machine changes.
