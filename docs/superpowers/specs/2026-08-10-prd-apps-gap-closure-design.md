# PRD Dual-Client Gap Closure Design (v1.3)

Date: 2026-08-10
Status: Approved
Related: PRD v1.3 §12 / §14; `docs/superpowers/specs/2026-08-10-flutter-learner-design.md`

## 1. Goals

Close remaining MVP acceptance gaps on the Flutter learner (primary) and Next.js admin (secondary) without inventing backend routes. Shared contract remains `openapi/openapi.json`.

## 2. Gap → target contracts

### 2.1 Practice book/chapter filters (§14 #7)

| Current | Target |
|---|---|
| `PracticeHomeScreen` calls `api.books()` and discards; create body omits book/chapter | Cascading Book → Chapter dropdowns; `POST /api/practice/sessions` includes optional `book_id` / `chapter_id` |

Payload fields (existing API): `count`, `subset`, `order_mode`, `shuffle_options`, `language_mode`, `domain_id?`, `book_id?`, `chapter_id?`.

### 2.2 Answer explanations (§14 #8)

| Current | Target |
|---|---|
| Practice shows `correctRationale` only | Also render `per_option[]` explanations + key-point summary |
| Exam review shows stem + option indexes | Full bilingual stem/options/rationale |
| `flutter_markdown` unused | Markdown for stems/rationales via shared bilingual markdown helper |

### 2.3 CAT language toggle (§14 #21)

| Current | Target |
|---|---|
| `_CatExamBody` uses ad-hoc `setState`; `CatRunnerState` unused | Runner holds `CatRunnerState`; language toggle = `copyWithLanguage` only; never calls `/next` |
| Unit test on pure state only | Widget/integration test with Dio mock asserting zero `/next` on toggle |

### 2.4 Auth refresh tests

Concurrent 401s share one refresh; failure clears session and routes to login. Cover with unit tests on `AuthSession` + interceptor seam.

### 2.5 Analytics (§14 #15)

| Current | Target |
|---|---|
| Domains list + DomainCompass only | Domains + trend (30/90) + weak-areas + error-types + recommendation |

Use existing `cissp_api` methods: `domainMastery`, `trend`, `weakAreas`, `errorTypes`, `recommendation`.

### 2.6 Windows keyboard (FR-CLIENT-05)

Desktop (≥800) Shortcuts/Actions on practice/fixed/CAT:
- `1–4` / `A–D` select option
- `Enter` submit / advance
- Arrow keys navigate fixed palette

Touch path unchanged.

### 2.7 Admin gaps

| Gap | Target |
|---|---|
| FR-IMP-03 template | Downloadable CSV template from import wizard |
| FR-IMP-04 field mapping | Interactive column→canonical-field map before preview/upload commit path |
| FR-LANG-10 coverage | Admin UI for `/api/admin/questions/language-coverage` |
| FR-ADMIN-03 members | Add/remove class members |
| Admin reset password | Users tab → `POST /api/admin/users/{id}/reset-password` |

## 3. Out of scope

Flutter Web/macOS/Linux, offline sync, dark mode, complex item types, 3PL IRT, Markdown-paste import, question export, store signing.

## 4. Acceptance

See plan §14 checklist. Learner green on #7, #8, #15, #21 (client), #25–31. Admin green on #1–6, #14, #23–24, #30.
