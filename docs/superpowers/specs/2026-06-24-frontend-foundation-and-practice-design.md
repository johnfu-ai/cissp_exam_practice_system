# Sub-project I-1: Frontend Foundation + Practice — Design

**Date:** 2026-06-24
**Status:** Design approved (section-by-section) — pending spec review
**Scope owner:** Frontend phase of the CISSP Exam Practice System
**Predecessors:** Sub-projects A–H2 (full PRD functional backend) — merged to `master`. 104 API endpoints, 366 backend tests, zero migration drift.

## 1. Purpose & context

The backend is feature-complete for the PRD (auth/RBAC, ETL, question bank, taxonomy admin, practice, fixed exam, CAT exam, analytics, admin backoffice). The frontend today is minimal: login/register pages, a placeholder home page, a Zustand auth store, and a typed `apiFetch`/`apiJson` client with silent refresh. None of the actual product experience exists in the UI.

The frontend phase (**Sub-project I**) is decomposed into independently-spec'd phases:

| Phase | Covers | Audience |
|---|---|---|
| **I-1 (this spec)** | Foundation + design system + full Practice flow | Learner (base for everything) |
| I-2 | Exam (fixed + CAT) | Learner |
| I-3 | Analytics dashboard | Learner |
| I-4 | Admin backoffice | Admin |
| I-5 | Content management (question bank, taxonomy, ETL) | Content admin |

**I-1 scope:** establish the reusable design system, app shell, auth/route guards, data-fetching layer, and deliver a complete, usable Practice experience end-to-end over the existing `/api/practice/*` and read-only taxonomy APIs. No new backend work.

## 2. Decisions (approved)

| Decision | Choice | Rationale |
|---|---|---|
| Visual direction | **Modern SaaS** — white canvas, blue primary `#2563eb`, slate neutrals, green/red status | Natural home for shadcn/ui; crisp correct/incorrect + pass/fail states; legible across long sessions |
| App shell | **Left sidebar** (persistent vertical nav, user at bottom) | Constant orientation across Practice/Exam/Analytics/Admin; scales when backoffice lands |
| Practice runner | **Select → Submit → Feedback** (deliberate commit, then inline correctness + explanation + tools) | Builds exam habit of committing before feedback; handles single/multi/true-false unambiguously |
| Create-session UX | **Full filter form** on landing | Surfaces the full power of the practice API in one screen |
| Feedback depth | **Correctness + correct answer(s) + explanation + tools** | Matches the practice API contract exactly |
| Component system | **shadcn/ui** (Radix UI + Tailwind, copy-in) | Accessible, customizable, themeable; we own the source |
| Data fetching | **TanStack Query** | Caching, invalidation, mutations, loading/error states; pairs with existing client |
| UI language | **English** (navigation/buttons/labels/toasts/states) | Question content shown verbatim from the backend |

## 3. Architecture & layering

Next.js 14 App Router. Server components by default; `'use client'` only where interactivity is needed (auth, runner, forms, query hooks). Four layers:

1. **Design system** — shadcn/ui components copied into `frontend/src/components/ui/`; a `globals.css` token layer (CSS variables) defining the Modern SaaS palette, consumed by Tailwind. Theme via variables so a dark mode can be added later without rework.
2. **Data layer** — TanStack Query `QueryClientProvider` in a client boundary; typed React Query hooks in `frontend/src/lib/api/` per resource, wrapping the existing `apiFetch`/`apiJson` client (refactored to read the backend URL once, keep silent-refresh).
3. **App shell** — `(app)/layout.tsx` route group with left sidebar (Practice / Exam / Analytics / Admin — Admin link gated by `admin:*` perms), top breadcrumb/title bar, `<RequireAuth>` + permission guard. Auth store gains a `hydrated` flag so guards render a brief skeleton instead of flashing `/login`.
4. **Feature modules** — one folder per feature under `frontend/src/app/(app)/` and `frontend/src/features/`. I-1 ships `practice/` + the shared shell; later phases drop exam/analytics/admin into the same shell.

### Routing (I-1 scope)

```
/login, /register                      (existing, polished)
(app protected group:)
/                                      → redirect to /practice (or /login if unauthed)
/practice                              → landing: resume in-progress + create-session form
/practice/sessions/[id]                → runner
/practice/sessions/[id]/done           → summary + wrong-question review
```

## 4. Design system & shared primitives

`frontend/src/components/ui/` — shadcn/ui (copy-in). Only what I-1 needs, extensible per later phase:

- **Layout**: `Button` (variants: primary/secondary/ghost/destructive; sizes), `Card`/`CardHeader`/`CardContent`, `Input`, `Textarea`, `Label`, `Badge` (domain/difficulty/status chips), `Separator`.
- **Selection**: `Checkbox`, `RadioGroup`, `Select` (dropdown for domain/book/chapter/tag/type/difficulty/subset/order).
- **Feedback**: `Toast` (`sonner`) for mutation success/error, `Skeleton` for loading, `Alert` for empty/error states.
- **Overlays**: `Dialog` (note/error-type entry on a question), `Tooltip`.
- **Navigation**: `Sidebar` (shadcn-style), `Tabs` (landing Resume/New split; reused later by analytics).

**Tokens** (`globals.css`, CSS variables → Tailwind): primary `#2563eb`, primary-foreground `#ffffff`, background `#ffffff`, foreground slate-900, muted slate-100/500, border slate-200, **success** emerald-600/50, **destructive** red-600/50, ring blue-500. Radius 0.5rem. These map to correct/incorrect and pass/fail states.

**Shared patterns** (`frontend/src/components/`): `<PageHeader title crumbs>`, `<EmptyState>`, `<ErrorState>`, `<Loading>` (compositions keeping feature code declarative), and `<OptionList>` — renders single/multi/true-false options uniformly; the runner's core.

**Data discipline:** every server read → a TanStack Query hook returning `{data, isLoading, isError, error}`; every mutation → `useMutation` with `onSuccess` invalidation of the relevant query key. No raw `useState`+`useEffect` fetching in feature code.

## 5. Practice feature — data flow

Response shapes will be verified against `app/api/practice.py` Pydantic schemas during planning; this is the contract.

**5.1 Landing `/practice`** — two panels:
- **Resume**: `GET /api/practice/sessions` (in-progress) → cards with progress bar + "Resume" → `/sessions/[id]`.
- **Create** (full filter form) → `POST /api/practice/sessions`:
  - scope filters → `domain_ids[]` / `book_id` / `chapter_id` / `tag_ids[]` / `type` / `difficulty`
  - subset → `subset` (all/unpracticed/wrong/bookmarked/needs_review)
  - order → `order` (random/sequential/easy_to_hard)
  - count → `count`
  - dropdowns populated from `GET /api/domains`, `/api/books`, `/api/books/{id}/chapters`, `/api/knowledge-points`, `/api/tags`
  - Start creates the session and routes to the runner.
- On success → redirect `/practice/sessions/[id]`.

**5.2 Runner `/practice/sessions/[id]`** — `GET /api/practice/sessions/{id}` (meta + position), `GET /api/practice/sessions/{id}/questions/{position}` (delivery from snapshot). State machine:
- `selecting` → learner picks option(s); Submit enabled when valid.
- `submitted` → `POST /api/practice/sessions/{id}/answers` with chosen option IDs; backend returns `AnswerResultOut` (correct/incorrect + correct answers). UI shows correctness + explanation + tools row (bookmark/flag/note/error-type via `PUT /api/practice/questions/{id}/state`).
- `Next` → advance position; past last → `POST /api/practice/sessions/{id}/finish` → redirect to `/done`.
- Pause/Resume buttons call `/pause` and `/resume`.
- **Practice answers are one-shot (no upsert)** — once submitted, locked. (Distinct from the fixed exam's revisable answers; relevant when I-2 lands.)

**5.3 Summary `/practice/sessions/[id]/done`** — `GET /api/practice/sessions/{id}/summary` (per-domain breakdown + wrong-question list). Wrong-question list links into a review view of each wrong question's snapshot. "Start another" → `/practice`.

**5.4 Error handling**: `ApiError` (422/404/409) → toast + inline `ErrorState`; 401 handled by client silent-refresh. Stale/finished session access (409) → friendly message + link to landing.

## 6. Auth & route guards

- Polish existing login/register: redirect-to-intended-path after login (store `?next=`); `useHydratedAuth()` so guards render a brief skeleton instead of flashing `/login`; home `/` becomes a redirect to `/practice` (or `/login` if unauthed). Dev "admin/admin" button stays.
- `<RequireAuth>` wraps the `(app)` group; `<RequirePermission perm="...">` built now for feature-level gating (admin link suppressed in I-1, guard ready for later phases). Perms from auth store `user.perms`.

## 7. Testing (Vitest, already configured)

- Unit: pure runner state machine (`selecting → submitted → next`); `<OptionList>` rendering for single/multi/true-false.
- Client: `apiFetch` 401 → silent-refresh path (mocked fetch).
- Component: create-session form (validation, payload shape).
- No Playwright/E2E in I-1 (scope tight); manual smoke against `docker compose` covers integration.

## 8. Scope boundaries (explicitly out of I-1)

- Exam (fixed + CAT), analytics dashboard, admin backoffice, content management, ETL UI — later phases.
- Dark mode — tokens ready, toggle deferred.
- PWA / offline — not in scope.
- i18n — English UI only; no bilingual toggle infrastructure now.

## 9. Acceptance criteria

1. `npm run build` and `npm run lint` pass; `npm run test` (Vitest) passes with the new unit/component tests.
2. Full stack (`docker compose up -d --build`) starts healthy; a learner can log in (incl. dev admin), land on `/practice`, create a scoped practice session via the full filter form, answer questions with Select→Submit→Feedback (correctness + explanation + bookmark/flag/note/error-type tools), pause/resume, finish, and see the per-domain summary + wrong-question review.
3. Route guards work: unauthed → `/login`; intended-path redirect after login.
4. Sidebar renders Practice (active) + Exam/Analytics (disabled/coming-soon placeholders) + Admin (hidden unless `admin:*` perms).
5. Design tokens applied consistently; correct/incorrect and pass/fail use the success/destructive palette.
6. No raw-fetch-in-component pattern remains in feature code — all server state via TanStack Query hooks.
7. No backend changes required; existing 366 backend tests still pass.
