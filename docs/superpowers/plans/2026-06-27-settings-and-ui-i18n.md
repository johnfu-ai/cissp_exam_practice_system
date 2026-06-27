# Settings Page + UI Internationalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/settings` page holding a new interface-language selector (English/中文, full UI-chrome i18n) and the relocated question-content `language_mode` selector; remove the language `<Select>` from the sidebar and add a Settings link.

**Architecture:** Backend adds `User.interface_language` (en/zh, default en) via a new Alembic migration, exposed through the existing `GET/PUT /api/users/me/preferences` and `UserOut`. Frontend uses a hand-rolled client `I18nProvider` with `t(key)` (Approach A — no new dependency, no `[locale]` routing), cookie-seeded from the root server layout so the first paint is correct with no English flash and no hydration mismatch. A single `src/locales/{en,zh}.ts` dictionary holds all UI-chrome strings; chrome components call `t()`. The Settings page writes the preference to the backend and a `ui_lang` cookie on change.

**Tech Stack:** FastAPI + SQLAlchemy 2.x + Alembic (backend); Next.js 14 App Router + TypeScript + Zustand + TanStack Query + shadcn/ui (frontend); Vitest + Testing Library (frontend tests); pytest (backend tests).

## Global Constraints

- Backend tests use a real PostgreSQL `cissp_test` DB with per-test SAVEPOINT rollback (`backend/tests/conftest.py`). The `auth_client` fixture is defined locally in `tests/test_preferences_api.py` because `create_app()` is currently broken by an admin-service import — reuse that fixture pattern, do not switch to `create_app()`.
- Alembic head revision is `a1b2c3d4e5f6` (`app/alembic/versions/a1b2c3d4e5f6_question_translations.py`). New migration `down_revision = 'a1b2c3d4e5f6'`.
- `tests/test_migrations.py` enforces **zero autogenerate drift**; after the migration, `alembic revision --autogenerate` must produce an empty diff (the only allowed manual index is `uq_users_email_lower`). Run it and confirm before committing the migration.
- `interface_language` values are `en` | `zh` only (NOT `bilingual` — that is `language_mode`). Validate with `Literal["en","zh"]` at the Pydantic layer (422) and `INTERFACE_LANGUAGES` tuple in the service guard.
- Frontend: **no new i18n dependency.** Hand-rolled context. Light mode only. No `[locale]` routing. No dark mode.
- Language toggle invariant: changing `interface_language` updates only client `locale` state + writes the `ui_lang` cookie + PUTs the backend. It must never call `/next`, advance, or submit anything (mirrors the CAT forward-only invariant).
- Tokens live in `sessionStorage` (not cookies); the `ui_lang` cookie is a SEPARATE, non-auth, `sameSite=lax`, `path=/`, `max-age=1y` cookie used only for SSR `<html lang>` + provider seed.
- Commit after every task. Branch from `master` (the single working branch). End commit messages with `Co-Authored-By: Claude <noreply@anthropic.com>`.

---

## File Structure

**Backend (create/modify):**
- Modify `backend/app/models/enums.py` — add `InterfaceLanguage` Literal + `INTERFACE_LANGUAGES` tuple.
- Modify `backend/app/models/auth.py` — add `interface_language` column.
- Create `backend/app/alembic/versions/<newid>_interface_language.py` — add column migration.
- Modify `backend/app/schemas/auth.py` — add `interface_language` to `UserOut`, `PreferencesIn`, `PreferencesOut`.
- Modify `backend/app/services/preferences.py` — read/validate/write `interface_language`.
- Modify `backend/app/api/users.py` — pass `interface_language` through `PUT`.
- Modify `backend/app/api/auth.py` — `_user_out` maps `interface_language`.
- Modify `backend/tests/test_preferences_api.py` + `test_models.py` — new tests.

**Frontend (create/modify):**
- Create `frontend/src/locales/en.ts` + `frontend/src/locales/zh.ts` — string dictionaries.
- Create `frontend/src/lib/i18n/types.ts` — `Locale`, `Dictionary`, `t` signature.
- Create `frontend/src/lib/i18n/provider.tsx` — `I18nProvider` + `useI18n`/`useT`.
- Create `frontend/src/lib/i18n/cookie.ts` — `readUiLangCookie`, `writeUiLangCookie`, `UI_LANG_COOKIE`.
- Modify `frontend/src/lib/api/types.ts` — add `interface_language` to nothing here (it's on `AuthUser`); export `Locale` re-export. Add `interface_language` to `Preferences`.
- Modify `frontend/src/lib/api/preferences.ts` — `Preferences` gains `interface_language`; add `useUpdateInterfaceLanguage`.
- Modify `frontend/src/lib/auth-store.ts` — `AuthUser` gains `interface_language`.
- Modify `frontend/src/app/layout.tsx` — read `ui_lang` cookie server-side, set `<html lang>`, pass `initialLocale` to `<Providers>`.
- Modify `frontend/src/components/providers.tsx` — accept `initialLocale`, wrap children in `<I18nProvider>`.
- Modify `frontend/src/components/app-sidebar.tsx` — remove language `<Select>` block + `onMode`/`mode`, add Settings `<Link>`.
- Create `frontend/src/app/(app)/settings/page.tsx` — thin wrapper.
- Create `frontend/src/features/settings/settings-view.tsx` — two cards.
- Modify all chrome feature modules + shared components to route strings through `t()` (per task).
- Modify affected tests to stable selectors.
- Modify `frontend/src/locales/__tests__/i18n.test.ts` — provider/dictionary tests.

---

### Task 1: Backend — add `interface_language` enum constant + User column

**Files:**
- Modify: `backend/app/models/enums.py` (after the `LANGUAGE_MODES` line ~143)
- Modify: `backend/app/models/auth.py:46-48` (after the `language_mode` column)
- Test: `backend/tests/test_models.py` (extend `test_user_has_language_mode` area)

**Interfaces:**
- Produces: `InterfaceLanguage = Literal["en","zh"]`, `INTERFACE_LANGUAGES = ("en","zh")` in `enums.py`; `User.interface_language: Mapped[str]` column (String(16), NOT NULL, server_default `'en'`).

- [ ] **Step 1: Write the failing model test**

Add to `backend/tests/test_models.py` right after `test_user_has_language_mode`:

```python
def test_user_has_interface_language(db_session):
    u = User(email="if@y.com", interface_language="zh")
    db_session.add(u)
    db_session.flush()
    assert u.interface_language == "zh"
    # default is en
    u2 = User(email="if2@y.com")
    db_session.add(u2)
    db_session.flush()
    assert u2.interface_language == "en"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models.py::test_user_has_interface_language -v`
Expected: FAIL — `interface_language` not a valid column / AttributeError.

- [ ] **Step 3: Add the enum constant**

In `backend/app/models/enums.py`, after the `LANGUAGE_MODES` line, add:

```python
InterfaceLanguage = Literal["en", "zh"]

INTERFACE_LANGUAGES: tuple[str, ...] = ("en", "zh")
```

- [ ] **Step 4: Add the User column**

In `backend/app/models/auth.py`, immediately after the `language_mode` mapped_column block, add:

```python
    interface_language: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'en'")
    )
```

- [ ] **Step 5: Run model test to verify it passes**

Run: `cd backend && pytest tests/test_models.py::test_user_has_interface_language tests/test_models.py::test_user_has_language_mode -v`
Expected: PASS (model layer uses `Base.metadata.create_all`, so no migration needed for the test DB).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/enums.py backend/app/models/auth.py backend/tests/test_models.py
git commit -m "feat(backend): add User.interface_language column + enum

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Backend — Alembic migration for `interface_language`

**Files:**
- Create: `backend/app/alembic/versions/b2c3d4e5f6a7_interface_language.py`
- Test: `backend/tests/test_migrations.py` (existing zero-drift test; do not modify, just satisfy)

**Interfaces:**
- Produces: migration `b2c3d4e5f6a7`, `down_revision='a1b2c3d4e5f6'`, adds/drops `users.interface_language`.

- [ ] **Step 1: Generate the migration via autogenerate**

Run: `cd backend && alembic revision --autogenerate -m "interface_language"`
Expected: a new file under `versions/` whose `down_revision = 'a1b2c3d4e5f6'` and upgrade adds `users.interface_language`. Rename the generated file to `b2c3d4e5f6a7_interface_language.py` only if autogenerate produced a different id — otherwise keep the generated id and use it consistently below.

- [ ] **Step 2: Inspect the generated migration**

Open the new file. Confirm `upgrade()` contains:
```python
op.add_column('users', sa.Column('interface_language', sa.String(length=16), nullable=False, server_default=sa.text("'en'")))
```
and `downgrade()` contains `op.drop_column('users', 'interface_language')`. If autogenerate emitted anything else (e.g. extra ops), delete the stray ops so only this column add/drop remains.

- [ ] **Step 3: Verify the migration applies + zero autogenerate drift**

Run: `cd backend && pytest tests/test_migrations.py -v`
Expected: PASS — includes the no-autogenerate-drift guard. If drift is reported, re-run `alembic revision --autogenerate -m "check"`; an empty diff confirms zero drift (delete the throwaway check migration file afterward).

- [ ] **Step 4: Commit**

```bash
git add backend/app/alembic/versions/*interface_language.py
git commit -m "feat(backend): migration for users.interface_language

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Backend — expose `interface_language` in schemas + preferences service + router + auth `_user_out`

**Files:**
- Modify: `backend/app/schemas/auth.py` (UserOut, PreferencesIn, PreferencesOut)
- Modify: `backend/app/services/preferences.py` (get_preferences, set_preferences)
- Modify: `backend/app/api/users.py` (put_prefs call site)
- Modify: `backend/app/api/auth.py` (`_user_out` helper)
- Test: `backend/tests/test_preferences_api.py`

**Interfaces:**
- Consumes: `INTERFACE_LANGUAGES` from `enums.py` (Task 1).
- Produces: `PreferencesOut` now `{ language_mode, interface_language }`; `PreferencesIn` accepts optional `interface_language: Literal["en","zh"]`; `UserOut` carries `interface_language: str = "en"`; `set_preferences(session, user, language_mode=None, interface_language=None)`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_preferences_api.py` (reuse the existing `auth_client`, `_register`, `_auth` helpers):

```python
def test_get_preferences_returns_interface_language(auth_client):
    token = _register(auth_client)
    prefs = auth_client.get("/api/users/me/preferences", headers=_auth(token)).json()
    assert prefs["interface_language"] == "en"


def test_put_preferences_sets_interface_language(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"interface_language": "zh"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["interface_language"] == "zh"
    me = auth_client.get("/api/auth/me", headers=_auth(token)).json()
    assert me["interface_language"] == "zh"


def test_put_preferences_rejects_invalid_interface_language(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"interface_language": "fr"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_put_preferences_updates_both_fields(auth_client):
    token = _register(auth_client)
    r = auth_client.put(
        "/api/users/me/preferences",
        json={"language_mode": "bilingual", "interface_language": "zh"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["language_mode"] == "bilingual"
    assert body["interface_language"] == "zh"
```

Also update the existing `test_get_preferences_returns_default` and `test_put_preferences_bilingual` assertions: `GET` response now also has `interface_language == "en"`; the existing `assert prefs["language_mode"] == ...` lines stay valid (extra keys don't break them), but add `assert prefs["interface_language"] == "en"` where the test reads the full prefs body.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_preferences_api.py -v`
Expected: FAIL — `KeyError: 'interface_language'` / 422 not triggered for `fr`.

- [ ] **Step 3: Update schemas**

In `backend/app/schemas/auth.py`:

```python
class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str]
    perms: list[str]
    language_mode: str = "en"
    interface_language: str = "en"


class PreferencesIn(BaseModel):
    language_mode: Literal["en", "zh", "bilingual"] | None = None
    interface_language: Literal["en", "zh"] | None = None


class PreferencesOut(BaseModel):
    language_mode: str
    interface_language: str
```

- [ ] **Step 4: Update preferences service**

Replace `backend/app/services/preferences.py` body with:

```python
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import INTERFACE_LANGUAGES, LANGUAGE_MODES, AuditAction
from app.services.audit import log_audit


def get_preferences(session: Session, user: User):
    from app.schemas.auth import PreferencesOut

    return PreferencesOut(
        language_mode=getattr(user, "language_mode", "en") or "en",
        interface_language=getattr(user, "interface_language", "en") or "en",
    )


def set_preferences(
    session: Session,
    user: User,
    language_mode: str | None = None,
    interface_language: str | None = None,
):
    from app.schemas.auth import PreferencesOut

    if language_mode is not None and language_mode not in LANGUAGE_MODES:
        raise ValueError("invalid language_mode")
    if interface_language is not None and interface_language not in INTERFACE_LANGUAGES:
        raise ValueError("invalid interface_language")
    details: dict = {}
    if language_mode is not None:
        user.language_mode = language_mode
        details["language_mode"] = language_mode
    if interface_language is not None:
        user.interface_language = interface_language
        details["interface_language"] = interface_language
    session.flush()
    log_audit(
        session,
        action=AuditAction.config_change,
        actor_id=user.id,
        organization_id=user.default_organization_id,
        entity_type="user",
        entity_id=str(user.id),
        details=details,
    )
    return PreferencesOut(
        language_mode=user.language_mode,
        interface_language=user.interface_language,
    )
```

- [ ] **Step 5: Update the router call site**

In `backend/app/api/users.py`, change the `put_prefs` body:

```python
@router.put("/me/preferences", response_model=PreferencesOut)
def put_prefs(
    body: PreferencesIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> PreferencesOut:
    if body.language_mode is None and body.interface_language is None:
        raise HTTPException(status_code=422, detail="no preferences provided")
    try:
        out = svc.set_preferences(
            session,
            current.user,
            language_mode=body.language_mode,
            interface_language=body.interface_language,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.commit()
    return out
```

- [ ] **Step 6: Update auth `_user_out`**

In `backend/app/api/auth.py`, extend `_user_out`:

```python
def _user_out(session, user, org_id) -> UserOut:
    return UserOut(
        id=str(user.id), email=user.email, display_name=user.display_name,
        roles=load_user_roles(session, user.id, org_id),
        perms=load_user_perms(session, user.id, org_id),
        language_mode=getattr(user, "language_mode", "en") or "en",
        interface_language=getattr(user, "interface_language", "en") or "en",
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_preferences_api.py -v`
Expected: PASS — all old + new tests green.

- [ ] **Step 8: Run full backend suite to confirm no regressions**

Run: `cd backend && pytest -q`
Expected: PASS — 427 prior + new tests, zero failures.

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/services/preferences.py backend/app/api/users.py backend/app/api/auth.py backend/tests/test_preferences_api.py
git commit -m "feat(backend): expose interface_language via preferences + UserOut

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Frontend — i18n types + dictionary skeleton (en + zh)

**Files:**
- Create: `frontend/src/locales/en.ts`
- Create: `frontend/src/locales/zh.ts`
- Create: `frontend/src/lib/i18n/types.ts`
- Test: `frontend/src/locales/__tests__/i18n.test.ts`

**Interfaces:**
- Produces: `Locale = "en" | "zh"`; `Dictionary` type = `typeof en`; `t(key: string, vars?: Record<string,string|number>) => string`; the two dictionaries keyed identically.

- [ ] **Step 1: Write the failing dictionary-parity + t test**

Create `frontend/src/locales/__tests__/i18n.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { en } from "../en";
import { zh } from "../zh";
import { makeT } from "../t";

describe("i18n dictionaries", () => {
  it("zh has every key en has", () => {
    const missing = keys(en).filter((k) => get(zh, k) === undefined);
    expect(missing).toEqual([]);
  });

  it("t returns the en value for a known key", () => {
    const t = makeT(en);
    expect(t("common.save")).toBe("Save");
  });

  it("t interpolates {vars}", () => {
    const t = makeT(en);
    expect(t("common.ofN", { n: 5 })).toBe("of 5");
  });

  it("t falls back to the key when missing", () => {
    const t = makeT(en);
    expect(t("nope.does.not.exist")).toBe("nope.does.not.exist");
  });
});

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}
function get(obj: any, path: string): unknown {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/locales/__tests__/i18n.test.ts`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Create the types file**

`frontend/src/lib/i18n/types.ts`:

```ts
export type Locale = "en" | "zh";

export type Vars = Record<string, string | number>;

export type TFn = (key: string, vars?: Vars) => string;
```

- [ ] **Step 4: Create the en dictionary**

`frontend/src/locales/en.ts` — start with the keys the tests reference plus the core chrome used in later tasks (this is the authoritative source; zh must mirror it):

```ts
export const en = {
  common: {
    save: "Save",
    cancel: "Cancel",
    submit: "Submit",
    retry: "Retry",
    loading: "Loading…",
    ofN: "of {n}",
    previous: "Previous",
    next: "Next",
    open: "Open",
    add: "Add",
    delete: "Delete",
  },
  nav: {
    dashboard: "Dashboard",
    practice: "Practice",
    review: "Review",
    exam: "Exam",
    analytics: "Analytics",
    manage: "Manage",
    import: "Import",
    questions: "Questions",
    taxonomy: "Taxonomy",
    admin: "Admin",
    settings: "Settings",
    logout: "Log out",
  },
  settings: {
    eyebrow: "Account",
    title: "Settings",
    description: "Manage your language and content preferences.",
    interfaceTitle: "Interface language",
    interfaceDesc: "Choose the language for menus, buttons, and labels.",
    contentTitle: "Question content language",
    contentDesc: "Choose how questions are displayed.",
    english: "English",
    chinese: "中文",
    both: "Both",
    saved: "Saved.",
  },
} as const;
```

- [ ] **Step 5: Create the zh dictionary (mirror every key)**

`frontend/src/locales/zh.ts`:

```ts
import type { en } from "./en";

export const zh: typeof en = {
  common: {
    save: "保存",
    cancel: "取消",
    submit: "提交",
    retry: "重试",
    loading: "加载中…",
    ofN: "共 {n}",
    previous: "上一题",
    next: "下一题",
    open: "打开",
    add: "添加",
    delete: "删除",
  },
  nav: {
    dashboard: "仪表盘",
    practice: "练习",
    review: "复习",
    exam: "考试",
    analytics: "分析",
    manage: "管理",
    import: "导入",
    questions: "题目",
    taxonomy: "分类",
    admin: "后台",
    settings: "设置",
    logout: "退出登录",
  },
  settings: {
    eyebrow: "账户",
    title: "设置",
    description: "管理你的语言与内容偏好。",
    interfaceTitle: "界面语言",
    interfaceDesc: "选择菜单、按钮和标签的显示语言。",
    contentTitle: "题目内容语言",
    contentDesc: "选择题目的显示方式。",
    english: "English",
    chinese: "中文",
    both: "双语",
    saved: "已保存。",
  },
};
```

- [ ] **Step 6: Create the `t` factory**

`frontend/src/locales/t.ts`:

```ts
import type { TFn, Vars } from "@/lib/i18n/types";

export function makeT(dict: Record<string, unknown>): TFn {
  return (key: string, vars?: Vars): string => {
    const raw = resolve(dict, key);
    if (typeof raw !== "string") return key;
    if (!vars) return raw;
    return raw.replace(/\{(\w+)\}/g, (_, k) =>
      vars[k] !== undefined ? String(vars[k]) : `{${k}}`,
    );
  };
}

function resolve(obj: any, path: string): unknown {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/locales/__tests__/i18n.test.ts`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/locales frontend/src/lib/i18n/types.ts
git commit -m "feat(frontend): i18n dictionary skeleton (en/zh) + t() factory

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Frontend — `I18nProvider` + cookie helpers

**Files:**
- Create: `frontend/src/lib/i18n/cookie.ts`
- Create: `frontend/src/lib/i18n/provider.tsx`
- Test: `frontend/src/lib/i18n/__tests__/provider.test.tsx`

**Interfaces:**
- Produces: `UI_LANG_COOKIE = "ui_lang"`; `readUiLangCookie(): Locale` (client, reads `document.cookie`, defaults `"en"`); `writeUiLangCookie(locale: Locale): void`; `<I18nProvider initialLocale={Locale}>`, `useI18n(): { locale, setLocale, t }`, `useT(): TFn`.

- [ ] **Step 1: Write the failing provider test**

`frontend/src/lib/i18n/__tests__/provider.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/i18n/__tests__/provider.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Create the cookie helpers**

`frontend/src/lib/i18n/cookie.ts`:

```ts
import type { Locale } from "./types";

export const UI_LANG_COOKIE = "ui_lang";
const ONE_YEAR = 60 * 60 * 24 * 365;

export function readUiLangCookie(): Locale {
  if (typeof document === "undefined") return "en";
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${UI_LANG_COOKIE}=`));
  return match?.split("=")[1] === "zh" ? "zh" : "en";
}

export function writeUiLangCookie(locale: Locale): void {
  if (typeof document === "undefined") return;
  document.cookie = `${UI_LANG_COOKIE}=${locale}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
}
```

- [ ] **Step 4: Create the provider**

`frontend/src/lib/i18n/provider.tsx`:

```tsx
"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { en } from "@/locales/en";
import { zh } from "@/locales/zh";
import { makeT } from "@/locales/t";
import type { Locale, TFn } from "./types";

const DICTS: Record<Locale, Record<string, unknown>> = { en, zh };

interface I18nCtx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: TFn;
}

const Ctx = createContext<I18nCtx | null>(null);

export function I18nProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const value = useMemo<I18nCtx>(() => {
    const t = makeT(DICTS[locale]);
    return {
      locale,
      setLocale: (l: Locale) => setLocaleState(l),
      t,
    };
  }, [locale]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18nCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

export function useT(): TFn {
  return useI18n().t;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/i18n/__tests__/provider.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/i18n/cookie.ts frontend/src/lib/i18n/provider.tsx frontend/src/lib/i18n/__tests__/provider.test.tsx
git commit -m "feat(frontend): I18nProvider + ui_lang cookie helpers

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Frontend — wire provider into root layout + Providers, server-side cookie seed

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/providers.tsx`

**Interfaces:**
- Consumes: `I18nProvider`, `readUiLangCookie`-equivalent server read via `next/headers` `cookies()`.
- Produces: root layout reads `ui_lang` cookie → sets `<html lang={locale}>` → passes `initialLocale` to `<Providers>`; `Providers` wraps children in `<I18nProvider>`.

- [ ] **Step 1: Update root layout to read the cookie server-side**

`frontend/src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import { cookies } from "next/headers";
import "./globals.css";
import { Providers } from "@/components/providers";
import type { Locale } from "@/lib/i18n/types";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CISSP Exam Practice",
  description: "CISSP exam preparation platform",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const store = cookies();
  const uiLang = store.get("ui_lang")?.value;
  const locale: Locale = uiLang === "zh" ? "zh" : "en";
  return (
    <html lang={locale} className={dmSans.variable}>
      <body className="font-sans antialiased">
        <Providers initialLocale={locale}>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Update Providers to host the I18nProvider**

`frontend/src/components/providers.tsx` — add the `initialLocale` prop and wrap children:

```tsx
"use client";

import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { I18nProvider } from "@/lib/i18n/provider";
import type { Locale } from "@/lib/i18n/types";

export function Providers({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: ReactNode;
}) {
  const [client] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={client}>
      <I18nProvider initialLocale={initialLocale}>
        {children}
        <Toaster />
      </I18nProvider>
    </QueryClientProvider>
  );
}
```

(Keep the exact import style already present; only add the I18nProvider wrapping and the prop. If `providers.tsx` currently places `<Toaster/>` outside children, keep Toaster inside the I18nProvider so toasts translate too.)

- [ ] **Step 3: Verify the build still compiles + existing tests pass**

Run: `cd frontend && npx vitest run && npm run lint`
Expected: PASS (provider has a default en seed; existing tests render components that may now require a provider — see Task 9 for test wrapping; if existing component tests error on `useI18n outside provider`, that is addressed in Task 9, but `providers.tsx`/layout are not exercised by unit tests so this step should stay green).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/components/providers.tsx
git commit -m "feat(frontend): cookie-seed I18nProvider in root layout

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Frontend — preferences client + auth store carry `interface_language`

**Files:**
- Modify: `frontend/src/lib/api/types.ts`
- Modify: `frontend/src/lib/api/preferences.ts`
- Modify: `frontend/src/lib/auth-store.ts`
- Test: `frontend/src/lib/__tests__/auth-store.test.ts` (extend) + `frontend/src/lib/api/__tests__/preferences.test.ts` (new, if feasible; otherwise cover via Task 8 settings test)

**Interfaces:**
- Produces: `Preferences` gains `interface_language: Locale`; `useUpdateInterfaceLanguage()` hook (PUT `{ interface_language }`, on success updates cache + auth store + writes `ui_lang` cookie + bumps i18n locale via a callback); `AuthUser` gains `interface_language: Locale`.

- [ ] **Step 1: Extend types + auth store**

In `frontend/src/lib/api/types.ts`, ensure `Locale` is re-exported from i18n types (or define `export type Locale = "en" | "zh";` here and have i18n import it — pick one source of truth: define in `lib/i18n/types.ts` and re-export from `api/types.ts`). Add to nothing else (Preferences is in preferences.ts).

In `frontend/src/lib/auth-store.ts`, add to `AuthUser`:

```ts
import type { Locale } from "./api/types"; // or i18n/types
// ...
export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  roles: string[];
  perms: string[];
  language_mode: LanguageMode;
  interface_language: Locale;
}
```

- [ ] **Step 2: Extend preferences client**

In `frontend/src/lib/api/preferences.ts`:

```ts
import type { LanguageMode, Locale } from "./types";

export interface Preferences {
  language_mode: LanguageMode;
  interface_language: Locale;
}
```

Add a hook that updates `interface_language` and syncs the i18n locale. Because the i18n locale lives in context (not a global store), the hook returns the new value and the **caller** (Settings page) calls `setLocale`. Keep it simple — the hook does the network + cache + auth-store + cookie; the page calls `setLocale` on success:

```ts
export function useUpdateInterfaceLanguage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (interface_language: Locale) =>
      apiJson<Preferences>("/api/users/me/preferences", {
        method: "PUT",
        body: JSON.stringify({ interface_language }),
      }),
    onSuccess: (data) => {
      qc.setQueryData(qk.preferences(), data);
      qc.invalidateQueries({ queryKey: qk.me() });
      const { user, setUser } = useAuthStore.getState();
      if (user) {
        setUser({ ...user, interface_language: data.interface_language });
      }
      writeUiLangCookie(data.interface_language);
    },
  });
}
```

Add `import { writeUiLangCookie } from "@/lib/i18n/cookie";` at top.

- [ ] **Step 3: Update the existing `useUpdatePreferences.onSuccess` to also sync interface_language into the auth store**

In the existing `useUpdatePreferences`, the `data` is now `{ language_mode, interface_language }`. The auth-store sync currently sets only `language_mode`:

```ts
onSuccess: (data) => {
  qc.setQueryData(qk.preferences(), data);
  qc.invalidateQueries({ queryKey: qk.me() });
  const { user, setUser } = useAuthStore.getState();
  if (user) {
    setUser({ ...user, language_mode: data.language_mode });
  }
},
```

`language_mode` PUT does not change `interface_language`, so leave this as-is (the backend returns the current `interface_language` too, but we only sync the field we changed).

- [ ] **Step 4: Extend auth-store test for the new field default**

In `frontend/src/lib/__tests__/auth-store.test.ts`, add (or extend) a test asserting a constructed `AuthUser` carries `interface_language`. If the test constructs an `AuthUser` literal, add `interface_language: "en"` to every literal in the file (there are likely a few). Run:

Run: `cd frontend && npx vitest run src/lib/__tests__/auth-store.test.ts`
Expected: PASS (TS will have errored at compile if any literal was missing the field — fix all literals).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/api/preferences.ts frontend/src/lib/auth-store.ts frontend/src/lib/__tests__/auth-store.test.ts
git commit -m "feat(frontend): carry interface_language in preferences client + auth store

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Frontend — Settings page (two cards) + sidebar Settings link, remove sidebar language select

**Files:**
- Create: `frontend/src/app/(app)/settings/page.tsx`
- Create: `frontend/src/features/settings/settings-view.tsx`
- Modify: `frontend/src/components/app-sidebar.tsx`
- Test: `frontend/src/features/settings/__tests__/settings-view.test.tsx`

**Interfaces:**
- Consumes: `usePreferences`, `useUpdatePreferences`, `useUpdateInterfaceLanguage`, `useI18n`, `t`.
- Produces: `/settings` route; sidebar has a Settings link and no language `<Select>`.

- [ ] **Step 1: Write the failing Settings view test**

`frontend/src/features/settings/__tests__/settings-view.test.tsx`:

```tsx
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

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider initialLocale="en">{ui}</I18nProvider>
    </QueryClientProvider>,
  );
}

describe("SettingsView", () => {
  beforeEach(() => {
    // patch Radix pointer capture for Select
    window.HTMLElement.prototype.hasPointerCapture = vi.fn();
    window.HTMLElement.prototype.releasePointerCapture = vi.fn();
  });

  it("renders both language cards", () => {
    wrap(<SettingsView />);
    expect(screen.getByText(/Interface language/i)).toBeInTheDocument();
    expect(screen.getByText(/Question content language/i)).toBeInTheDocument();
  });

  it("has a Settings page header", () => {
    wrap(<SettingsView />);
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/features/settings/__tests__/settings-view.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Create the Settings page wrapper**

`frontend/src/app/(app)/settings/page.tsx`:

```tsx
import { SettingsView } from "@/features/settings/settings-view";

export default function SettingsPage() {
  return <SettingsView />;
}
```

- [ ] **Step 4: Create the Settings view**

`frontend/src/features/settings/settings-view.tsx`:

```tsx
"use client";

import { usePreferences, useUpdatePreferences, useUpdateInterfaceLanguage } from "@/lib/api/preferences";
import { useI18n } from "@/lib/i18n/provider";
import { useT } from "@/lib/i18n/provider";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import type { LanguageMode, Locale } from "@/lib/api/types";

export function SettingsView() {
  const t = useT();
  const { setLocale } = useI18n();
  const prefs = usePreferences();
  const updateContent = useUpdatePreferences();
  const updateInterface = useUpdateInterfaceLanguage();

  const interfaceLanguage = prefs.data?.interface_language ?? "en";
  const contentMode: LanguageMode = prefs.data?.language_mode ?? "en";

  function onInterface(value: string) {
    const l = value as Locale;
    updateInterface.mutate(l, { onSuccess: () => setLocale(l) });
  }
  function onContent(value: string) {
    updateContent.mutate(value as LanguageMode);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader eyebrow={t("settings.eyebrow")} title={t("settings.title")} description={t("settings.description")} />
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.interfaceTitle")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("settings.interfaceDesc")}</p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="ui-lang">{t("settings.interfaceTitle")}</Label>
            <Select value={interfaceLanguage} onValueChange={onInterface}>
              <SelectTrigger id="ui-lang" className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">{t("settings.english")}</SelectItem>
                <SelectItem value="zh">{t("settings.chinese")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.contentTitle")}</CardTitle>
          <p className="text-sm text-muted-foreground">{t("settings.contentDesc")}</p>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="content-lang">{t("settings.contentTitle")}</Label>
            <Select value={contentMode} onValueChange={onContent}>
              <SelectTrigger id="content-lang" className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">{t("settings.english")}</SelectItem>
                <SelectItem value="zh">{t("settings.chinese")}</SelectItem>
                <SelectItem value="bilingual">{t("settings.both")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Run the Settings test to verify it passes**

Run: `cd frontend && npx vitest run src/features/settings/__tests__/settings-view.test.tsx`
Expected: PASS.

- [ ] **Step 6: Edit the sidebar — remove language select, add Settings link**

In `frontend/src/components/app-sidebar.tsx`:

1. Remove imports no longer used after the edit: `usePreferences`, `useUpdatePreferences` from `@/lib/api/preferences`; `LanguageMode` from `@/lib/api/types`; `Label` from `@/lib/ui/label` (if unused elsewhere); the `Select*` group from `@/components/ui/select` (if unused elsewhere). Add `Settings` to the `lucide-react` import list.
2. Delete the `mode`/`onMode`/`usePreferences`/`useUpdatePreferences` logic (lines ~55-69).
3. Delete the language `<Label>` + `<Select>` block in the footer (lines ~146-160).
4. In the footer, between the user info block and the Log out button, add:

```tsx
<Link
  href="/settings"
  className={cn(
    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-colors",
    pathname === "/settings" ? "bg-accent text-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
  )}
>
  <Settings className="h-4 w-4" />
  {t("nav.settings")}
</Link>
```

(Use `t("nav.settings")` for the label — the sidebar is a client component inside the provider, so `useT()` works. Add `const t = useT();` at the top of the component. Keep the existing "Log out" button using `t("nav.logout")` and the NAV/MANAGE labels via `t()` per Task 10.)

- [ ] **Step 7: Verify sidebar + settings compile and existing sidebar-adjacent tests pass**

Run: `cd frontend && npx vitest run && npm run lint`
Expected: PASS (some component tests may now fail if they render components using `useT` outside a provider — Task 9 fixes test wrapping; if failures appear only in tests that render `<AppSidebar>` or chrome without a provider, defer to Task 9 but do not leave lint failing).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/\(app\)/settings frontend/src/features/settings frontend/src/components/app-sidebar.tsx
git commit -m "feat(frontend): /settings page + sidebar Settings link, drop sidebar lang select

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Frontend — make `useT` safe in tests (provider wrapper helper) + migrate existing tests that assert English chrome

**Files:**
- Modify: `frontend/src/test/setup.tsx` (or a new `frontend/src/test/render-with-providers.tsx`)
- Modify: every component test that renders a component calling `useT()`/`useI18n()`
- Modify: tests asserting English chrome text where translation would break them — migrate to stable selectors (`data-testid`, role+id, or wrap with `I18nProvider initialLocale="en"` so English still resolves)

**Interfaces:**
- Produces: a `renderWithProviders(ui, { initialLocale? })` helper used by all component tests; component tests stay green.

- [ ] **Step 1: Create a render helper**

`frontend/src/test/render-with-providers.tsx`:

```tsx
"use client";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "@/lib/i18n/provider";
import type { Locale } from "@/lib/i18n/types";
import type { ReactElement, ReactNode } from "react";

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
```

- [ ] **Step 2: Migrate component tests to the helper (default en, so English assertions still hold)**

For each component test that renders a component which now calls `useT()` — at minimum `start-form.test.tsx`, `cat-runner.test.tsx`, `create-session-form.test.tsx`, `editor.test.tsx`, `field.test.tsx`, `eyebrow.test.tsx`, `bilingual-text.test.tsx`, `require-permission.test.tsx` — replace `render(<X/>)` with `renderWithProviders(<X/>)`. Because `initialLocale` defaults to `"en"`, all existing English text assertions (`/start fixed exam/i`, `"中文"`, `/stem$/i`, etc.) continue to resolve — **do not rewrite the assertion strings**. Only the render call changes.

For `field.test.tsx` and `eyebrow.test.tsx`: these render primitives that do not themselves call `useT()`, but if they're rendered inside a parent that does, wrap them. If they're standalone, `render` is fine — leave them. (Check: do `Field`/`Eyebrow` call `useT()`? They don't — they're presentational. Leave their tests on plain `render`.)

- [ ] **Step 3: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: PASS — all 75+ tests green. If a test fails because a component calls `useT` but wasn't wrapped, wrap it with `renderWithProviders`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/test/render-with-providers.tsx frontend/src
git commit -m "test(frontend): wrap component tests with I18nProvider (en default)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: Frontend — route chrome strings through `t()` (sidebar + shared components + pages)

**Files:**
- Modify: `frontend/src/components/app-sidebar.tsx` (NAV/MANAGE labels, header, logout)
- Modify: `frontend/src/components/error-state.tsx`, `require-auth.tsx`
- Modify: `frontend/src/app/page.tsx`, `src/app/(auth)/login/page.tsx`, `src/app/(auth)/register/page.tsx`
- Modify: each `(app)` page.tsx + its feature module per the string inventory (dashboard, practice, review, exam, analytics, import, questions, taxonomy, admin)
- Modify: `frontend/src/locales/en.ts` + `zh.ts` — add every new key introduced

**Interfaces:**
- Consumes: `useT()` everywhere chrome is rendered.
- Produces: all UI chrome strings flow through `t()`; dictionaries hold the full key set with parity.

**Approach (apply uniformly):** for each file, add `const t = useT();` (client component) and replace each literal English chrome string with `t("scope.key")`. Add the key to BOTH `en.ts` and `zh.ts`. Data-derived strings (question content, taxonomy names, user email) are NOT touched. Keep `id`/`htmlFor`/`aria-label` stable where tests assert them — only the visible *text* moves through `t()`. For `aria-label` strings asserted by tests (e.g. `aria-label="Option {n} content"`), translate them too but keep the test's regex matching the English form by rendering the test under `initialLocale="en"` (already the default) — the English dictionary value must match the prior literal exactly, so existing `getByLabelText(/option 1 content/i)` still resolves.

- [ ] **Step 1: Sidebar chrome**

Translate NAV labels (`Dashboard`→`nav.dashboard`, etc.), `MANAGE` labels, the `Manage` section header, `CISSP Practice` header (add `nav.brand`), and `Log out`. Keep `pathname`-based active class logic unchanged.

- [ ] **Step 2: Shared components**

`error-state.tsx`: default `title` → `t("common.errorTitle")`, button → `t("common.retry")`. `require-auth.tsx`: `Loading label={t("common.loading")}`. Add keys.

- [ ] **Step 3: Auth pages**

`login/page.tsx` + `register/page.tsx`: translate every chrome string (titles, labels, placeholders, button text, error text). Add `auth.*` keys. These are client components — `useT()` works.

- [ ] **Step 4: Root redirect page**

`src/app/page.tsx`: `Loading label={t("common.loading")}` (it's a client component using `useEffect`/router; if it's a server component, leave the string literal English or convert minimally — check first).

- [ ] **Step 5: Dashboard + analytics**

`features/analytics/dashboard.tsx` + `analytics-view.tsx`: translate PageHeader params, KPI labels, card titles, empty states, Eyebrows. Add `dashboard.*` and `analytics.*` keys. The `MASTERY_LABELS`/`ERROR_TYPE_LABELS` maps in `format.ts` — convert to functions that call `t()` at the call site OR keep as enum-keyed maps in the dictionary (`mastery.mastered` etc.) and look up via `t`. Pick: move them into the dictionary as `mastery.*` / `errorType.*` and have `format.ts` export `masteryLabel(t, level)` / `errorTypeLabel(t, type)` helpers. Update `format.test.ts` accordingly (assert on the en-dictionary value via `makeT(en)`).

- [ ] **Step 6: Practice + review**

`features/practice/{create-session-form,resume-panel,runner,summary}.tsx`, `features/review/subset-launcher.tsx`, and the `/practice`+`/review` page.tsx wrappers: translate all chrome. Consolidate the duplicated `LANGUAGE_LABELS` map (in 7 files) into dictionary keys `lang.en`/`lang.zh`/`lang.bilingual` and a single helper `langLabel(t, mode)` in a new `src/features/shared/lang-label.ts`. Replace all 7 copies.

- [ ] **Step 7: Exam**

`features/exam/{start-form,history-panel,runner,cat-runner,fixed-runner,report,review}.tsx`, `features/exam/format.ts` (`READINESS_LABELS` → dictionary `readiness.*`), and `/exam` page.tsx: translate chrome. Keep CAT forward-only behavior untouched.

- [ ] **Step 8: Import + questions + taxonomy + admin**

Translate chrome in `features/import/import-wizard.tsx`, `features/questions/{list,detail,editor}.tsx`, `features/questions/labels.ts` (`STATUS_LABELS` etc. → dictionary `qStatus.*`/`feedback.*`, with `availableActions(t,...)` returning translated labels), `features/taxonomy/*-tab.tsx`, `features/admin/tabs.tsx`, and each page.tsx wrapper. The `labelize(s)` helper is used for enum badges (question types, audit actions, roles, license statuses) — leave `labelize` for values that have no dictionary entry, but prefer dictionary lookups for the known enums.

- [ ] **Step 9: Verify dictionary parity + full test suite + lint + build**

Run:
```bash
cd frontend && npx vitest run src/locales/__tests__/i18n.test.ts   # parity
cd frontend && npx vitest run                                       # all tests
cd frontend && npm run lint
cd frontend && npm run build
```
Expected: all PASS. The parity test guarantees zh has every en key. The build catches any `useT()` called outside a provider or any missing key reference.

- [ ] **Step 10: Commit (one commit per page-group is fine; or one consolidated commit)**

```bash
git add frontend/src
git commit -m "feat(frontend): route all UI chrome through t() (en/zh)

Translates sidebar, auth pages, dashboard, analytics, practice, review,
exam, import, questions, taxonomy, and admin chrome. Consolidates
LANGUAGE_LABELS and label maps into the dictionary. zh dictionary
mirrors en (parity test enforced).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: Verify full stack, update CLAUDE.md, push to GitHub

**Files:**
- Modify: `CLAUDE.md`
- Verify: backend tests, frontend tests/lint/build, docker compose health

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && pytest -q`
Expected: PASS — all prior tests + new `interface_language` tests, zero failures, zero migration drift.

- [ ] **Step 2: Run the full frontend suite + lint + build**

Run:
```bash
cd frontend && npx vitest run
cd frontend && npm run lint
cd frontend && npm run build
```
Expected: all PASS.

- [ ] **Step 3: Docker compose smoke**

Run:
```bash
docker compose up -d --build
docker compose ps
curl -s http://localhost:8000/health
curl -s http://localhost:3000/ | head -c 200
```
Expected: backend `{"status":"ok",...}`; frontend responds 200. Manually (or via curl) confirm `PUT /api/users/me/preferences` with `{"interface_language":"zh"}` returns 200 and `interface_language:"zh"`.

- [ ] **Step 4: Update CLAUDE.md**

Add a concise paragraph under "Current State" documenting: PRD v1.2; new `User.interface_language` column + migration; preferences endpoints carry `interface_language`; frontend `/settings` page; `I18nProvider` + `locales/{en,zh}.ts` + `ui_lang` cookie seed; sidebar Settings link (language select removed); chrome routed through `t()`; test count; known follow-ups (taxonomy data not translated; `labelize` still used for unmapped enums). Update the "Frontend layout" rules to mention `useT()` and the provider.

- [ ] **Step 5: Commit + push**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document Settings + UI i18n (v1.2)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin master
```

Expected: push succeeds; `master` on origin contains the full feature.

---

## Self-Review

**1. Spec coverage:**
- §6.12 FR-SET-01 (settings page) → Task 8. ✓
- FR-SET-02 (relocate content selector, sidebar Settings entry) → Task 8. ✓
- FR-SET-03 (two cards) → Task 8. ✓
- FR-I18N-01 (interface_language en/zh default en) → Tasks 1, 3. ✓
- FR-I18N-02 (preferences GET/PUT, 422) → Task 3. ✓
- FR-I18N-03 (instant switch) → Tasks 5, 8 (`setLocale`). ✓
- FR-I18N-04 (no flash, cookie seed) → Task 6. ✓
- FR-I18N-05 (chrome only, no taxonomy) → Task 10 scope note. ✓
- FR-I18N-06 (UserOut/me/login/register carry it) → Task 3 (`_user_out` covers all four). ✓
- §9.4 column → Task 1/2. §9.5 API → Task 3. §8.1 page → Task 8. §12.1/§14 → verified in Task 11. §16-#3 resolved → PRD already edited (committed in brainstorm phase). ✓

**2. Placeholder scan:** No "TBD"/"TODO". Task 10 is broad by necessity (13 routes) but gives a uniform, repeatable procedure plus the dictionary-parity test as the safety net — not a placeholder, an explicit batch with a verification gate.

**3. Type consistency:** `Locale = "en"|"zh"` defined once in `lib/i18n/types.ts`, re-exported from `api/types.ts`, used in `provider.tsx`, `cookie.ts`, `preferences.ts`, `auth-store.ts`, `settings-view.tsx` — single source of truth. `INTERFACE_LANGUAGES` (backend) mirrors `Locale` (frontend). `set_preferences` signature `(session, user, language_mode=None, interface_language=None)` matches the router call in Task 3 Step 5.

**4. Risk:** Task 10 is the largest; if `npm run build` fails on a missed `useT`-outside-provider, the fix is mechanical (wrap with provider / it's only called in client components). The parity test catches missing zh keys. The migration drift test catches schema mismatch.
