# Apple-inspired UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retheme the Next.js frontend to the Apple-inspired design language from `cissp-exam-ui/` across all 13 routes, preserving every behavior and the full test suite.

**Architecture:** Token retheme + per-page restyle. Rewrite `globals.css` HSL tokens to the Apple palette, add DM Sans via `next/font`, tune shadcn variants, add two small primitives (`<Eyebrow>`, `<Field>`), then restyle the shell and every page. No new component system, no behavior changes, no backend work. The mockup HTML is a visual reference only — never ported as code.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind 3.4, Radix/shadcn UI, `next/font/google`, Vitest + Testing Library.

## Global Constraints

- **Light mode only.** Do not wire dark mode, `next-themes`, or `.dark` tokens.
- **Palette:** exact Apple tokens — `--primary: 211 100% 50%` (#007AFF), `--destructive: 0 100% 60%` (#FF3B30), `--success: 142 71% 53%` (#34C759), `--foreground: 231 33% 10%` (#1D1D1F), `--muted-foreground: 240 4% 46%` (#8E8E93), `--secondary/--muted/--accent: 240 20% 96%` (#F2F2F7), `--border/--input: 240 9% 90%` (#E5E5EA), `--ring: 211 100% 50%`.
- **Radius:** `--radius: 0.75rem` app-wide; `--radius-lg: 1.2rem` for hero/marketing cards only.
- **Font:** DM Sans via `next/font/google`, exposed as `--font-sans`, first in `fontFamily.sans`.
- **Icons:** keep `lucide-react`. Do NOT port `cissp-exam-ui/assets/icons/` or the `mask-image` technique.
- **No behavior changes:** auth, RBAC, exam/fixed/CAT runners, language toggle, timers, lazy auto-submit, forward-only CAT — all untouched.
- **No backend changes.** This plan is frontend-only.
- **Regression gate:** all 67 existing Vitest tests must stay green; `npm run lint` and `npm run build` must pass.
- **TDD scope:** new primitives (`<Eyebrow>`, `<Field>`) are written test-first. Token/variant/page restyles are refactors gated by the existing test suite + lint + build (visual verification per the final task).
- All work happens in `frontend/` unless a path says otherwise. Mockup reference files live in `cissp-exam-ui/pages/*.html`.
- Commit after each task. Branch: `feat/language-selection`.

---

## File Structure

**Create:**
- `frontend/src/components/eyebrow.tsx` — `<Eyebrow>` section-label primitive.
- `frontend/src/components/field.tsx` — icon-leading input wrapper.
- `frontend/src/components/__tests__/eyebrow.test.tsx` — TDD tests.
- `frontend/src/components/__tests__/field.test.tsx` — TDD tests.

**Modify:**
- `frontend/src/app/globals.css` — Apple token retheme + shadow ramp + canvas/hero tokens.
- `frontend/tailwind.config.ts` — `fontFamily.sans`, `boxShadow` utilities, `borderRadius.lg2`.
- `frontend/src/app/layout.tsx` — DM Sans via `next/font`, applied to `<html>`.
- `frontend/src/components/ui/button.tsx` — font-weight 600, `pill` size variant.
- `frontend/src/components/ui/card.tsx` — `shadow-card` default, hover-lift variant.
- `frontend/src/components/ui/input.tsx` — unchanged (consumed by `<Field>`).
- `frontend/src/components/page-header.tsx` — optional `eyebrow` prop.
- `frontend/src/components/app-sidebar.tsx` — Apple nav styling.
- `frontend/src/app/(app)/layout.tsx` — canvas background.
- `frontend/src/app/(auth)/layout.tsx` — create: gradient centered-card shell.
- `frontend/src/app/(auth)/login/page.tsx` — restyle to mockup.
- `frontend/src/app/(auth)/register/page.tsx` — restyle to mockup.
- `frontend/src/app/(app)/dashboard/page.tsx` — restyle to mockup.
- `frontend/src/app/(app)/practice/page.tsx` — restyle (practice-setup).
- `frontend/src/app/(app)/practice/sessions/[id]/page.tsx` — restyle runner (quiz).
- `frontend/src/app/(app)/practice/sessions/[id]/done/page.tsx` — restyle (explanation).
- `frontend/src/app/(app)/exam/page.tsx` — restyle exam setup.
- `frontend/src/app/(app)/exam/sessions/[id]/page.tsx` — restyle fixed + CAT runner.
- `frontend/src/app/(app)/exam/sessions/[id]/report/page.tsx` — restyle (exam-report).
- `frontend/src/app/(app)/exam/sessions/[id]/review/page.tsx` — restyle (explanation).
- `frontend/src/app/(app)/analytics/page.tsx` — extrapolated retheme.
- `frontend/src/app/(app)/review/page.tsx` — extrapolated retheme.
- `frontend/src/app/(app)/import/page.tsx` — extrapolated retheme.
- `frontend/src/app/(app)/questions/page.tsx` — extrapolated retheme.
- `frontend/src/app/(app)/questions/new/page.tsx` — extrapolated retheme.
- `frontend/src/app/(app)/questions/[id]/edit/page.tsx` — extrapolated retheme.
- `frontend/src/app/(app)/questions/[id]/page.tsx` — extrapolated retheme.
- `frontend/src/app/(app)/taxonomy/page.tsx` — extrapolated retheme.
- `frontend/src/app/(app)/admin/page.tsx` — extrapolated retheme.

---

### Task 1: Token retheme + DM Sans + Tailwind config

**Files:**
- Modify: `frontend/src/app/globals.css` (full `:root` rewrite + new tokens)
- Modify: `frontend/tailwind.config.ts` (fontFamily, boxShadow, borderRadius)
- Modify: `frontend/src/app/layout.tsx` (DM Sans)

**Interfaces:**
- Produces: CSS vars `--font-sans`, `--canvas`, `--radius-lg`, `--shadow-2xs…2xl`, `--shadow-card`, `--shadow-float`; Tailwind utilities `shadow-card`, `shadow-float`, `rounded-lg2`, `bg-canvas`, `font-sans`. Consumed by all later tasks.

- [ ] **Step 1: Rewrite `frontend/src/app/globals.css`**

Replace the entire file with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 231 33% 10%;
    --card: 0 0% 100%;
    --card-foreground: 231 33% 10%;
    --popover: 0 0% 100%;
    --popover-foreground: 231 33% 10%;
    --primary: 211 100% 50%;
    --primary-foreground: 0 0% 100%;
    --secondary: 240 20% 96%;
    --secondary-foreground: 231 33% 10%;
    --muted: 240 20% 96%;
    --muted-foreground: 240 4% 46%;
    --accent: 240 20% 96%;
    --accent-foreground: 231 33% 10%;
    --success: 142 71% 53%;
    --success-foreground: 0 0% 100%;
    --destructive: 0 100% 60%;
    --destructive-foreground: 0 0% 100%;
    --border: 240 9% 90%;
    --input: 240 9% 90%;
    --ring: 211 100% 50%;
    --radius: 0.75rem;
    --radius-lg: 1.2rem;

    /* Apple-tuned surfaces */
    --canvas: 240 20% 97%; /* #F7F7FA app background */
    --hero-from: 240 20% 96%;
    --hero-to: 240 16% 92%;

    /* Shadow ramp (light) */
    --shadow-2xs: 0 1px 2px -1px rgba(0, 0, 0, 0.04);
    --shadow-xs: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05), 0 1px 3px -1px rgba(0, 0, 0, 0.05);
    --shadow-card: 0 4px 8px -2px rgba(0, 0, 0, 0.06), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
    --shadow-float: 0 8px 24px -8px rgba(0, 0, 0, 0.08), 0 4px 8px -4px rgba(0, 0, 0, 0.05);
    --shadow-xl: 0 16px 40px -10px rgba(0, 0, 0, 0.10), 0 8px 16px -8px rgba(0, 0, 0, 0.06);
  }
}

@layer base {
  * {
    border-color: hsl(var(--border));
  }
  body {
    background-color: hsl(var(--background));
    color: hsl(var(--foreground));
    font-feature-settings: "ss01", "cv01";
  }
}
```

- [ ] **Step 2: Update `frontend/tailwind.config.ts`**

Replace the file with:

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "-apple-system",
          "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        canvas: "hsl(var(--canvas))",
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        success: { DEFAULT: "hsl(var(--success))", foreground: "hsl(var(--success-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        lg2: "var(--radius-lg)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        float: "var(--shadow-float)",
        sm: "var(--shadow-sm)",
        xl: "var(--shadow-xl)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

- [ ] **Step 3: Wire DM Sans in `frontend/src/app/layout.tsx`**

Replace the file with:

```tsx
import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CISSP Exam Practice",
  description: "CISSP exam preparation platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={dmSans.variable}>
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 4: Verify build + tests**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: lint clean; all 67 tests pass; build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/globals.css frontend/tailwind.config.ts frontend/src/app/layout.tsx
git commit -m "feat(ui): retheme tokens to Apple palette + DM Sans"
```

---

### Task 2: `<Eyebrow>` primitive (TDD)

**Files:**
- Create: `frontend/src/components/eyebrow.tsx`
- Test: `frontend/src/components/__tests__/eyebrow.test.tsx`

**Interfaces:**
- Produces: `<Eyebrow>{children}</Eyebrow>` — renders an uppercase, tracked, muted-foreground `<p>` with class `eyebrow`. Used by `PageHeader` (Task 5) and page section labels.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/__tests__/eyebrow.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Eyebrow } from "@/components/eyebrow";

describe("Eyebrow", () => {
  it("renders its children", () => {
    render(<Eyebrow>Section Label</Eyebrow>);
    expect(screen.getByText("Section Label")).toBeInTheDocument();
  });

  it("applies the eyebrow class", () => {
    render(<Eyebrow>X</Eyebrow>);
    const el = screen.getByText("X");
    expect(el.className).toContain("eyebrow");
    expect(el.className).toContain("uppercase");
    expect(el.className).toContain("text-muted-foreground");
  });

  it("renders as a paragraph by default", () => {
    render(<Eyebrow>X</Eyebrow>);
    expect(screen.getByText("X").tagName).toBe("P");
  });

  it("forwards additional className", () => {
    render(<Eyebrow className="extra">X</Eyebrow>);
    expect(screen.getByText("X").className).toContain("extra");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- eyebrow`
Expected: FAIL with "Cannot find module '@/components/eyebrow'".

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/eyebrow.tsx`:

```tsx
import { cn } from "@/lib/utils";

export function Eyebrow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "eyebrow text-xs font-semibold uppercase tracking-wider text-muted-foreground",
        className
      )}
    >
      {children}
    </p>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- eyebrow`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/eyebrow.tsx frontend/src/components/__tests__/eyebrow.test.tsx
git commit -m "feat(ui): add Eyebrow section-label primitive"
```

---

### Task 3: `<Field>` icon-leading input (TDD)

**Files:**
- Create: `frontend/src/components/field.tsx`
- Test: `frontend/src/components/__tests__/field.test.tsx`

**Interfaces:**
- Produces: `<Field icon={Mail} label="Email" htmlFor="x"><Input id="x" .../></Field>` — wraps an input in a bordered surface with an optional leading lucide icon and optional label. The input is passed as `children` so a11y attrs stay on the real `Input`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/__tests__/field.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Mail } from "lucide-react";
import { Field } from "@/components/field";
import { Input } from "@/components/ui/input";

describe("Field", () => {
  it("renders the label and input", () => {
    render(
      <Field label="Email" htmlFor="e">
        <Input id="e" />
      </Field>
    );
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("renders a leading icon when provided", () => {
    render(
      <Field icon={Mail} htmlFor="e">
        <Input id="e" />
      </Field>
    );
    // lucide renders an <svg>; presence of svg inside the field surface
    expect(document.querySelector(".field-surface svg")).toBeInTheDocument();
  });

  it("omits the surface wrapper class when no icon", () => {
    render(
      <Field htmlFor="e">
        <Input id="e" />
      </Field>
    );
    expect(document.querySelector(".field-surface")).toBeNull();
  });

  it("forwards wrapper className", () => {
    render(
      <Field htmlFor="e" className="my-4">
        <Input id="e" />
      </Field>
    );
    expect(screen.getByLabelText("").parentElement?.className).toContain("my-4");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- field`
Expected: FAIL with "Cannot find module '@/components/field'".

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/field.tsx`:

```tsx
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function Field({
  children,
  icon: Icon,
  label,
  htmlFor,
  className,
}: {
  children: React.ReactNode;
  icon?: LucideIcon;
  label?: string;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-xs font-medium text-muted-foreground">
          {label}
        </label>
      )}
      {Icon ? (
        <div className="field-surface flex h-10 items-center gap-2 rounded-md border border-input bg-background px-3 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
          <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          {children}
        </div>
      ) : (
        <div>{children}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- field`
Expected: PASS (4 tests). If the "omits surface" or "forwards className" assertion is brittle, adjust the test to match the rendered DOM precisely (the test's assertions are the contract).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/field.tsx frontend/src/components/__tests__/field.test.tsx
git commit -m "feat(ui): add Field icon-leading input wrapper"
```

---

### Task 4: Tune shadcn Button + Card variants

**Files:**
- Modify: `frontend/src/components/ui/button.tsx`
- Modify: `frontend/src/components/ui/card.tsx`

**Interfaces:**
- Produces: `Button` gains `size: "pill"` (rounded-full, h-11, font-semibold) and base `font-semibold`; `Card` defaults to `shadow-card` and accepts a `hover` prop adding `hover:-translate-y-0.5 hover:shadow-float transition`.

- [ ] **Step 1: Update `frontend/src/components/ui/button.tsx`**

Change the base string to add `font-semibold` and add a `pill` size. Replace the `buttonVariants` cva block with:

```tsx
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        pill: "h-11 rounded-full px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);
```

Leave the rest of the file unchanged.

- [ ] **Step 2: Update `frontend/src/components/ui/card.tsx`**

Replace the `Card` definition (keep all other exports unchanged) with:

```tsx
const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }>(
  ({ className, hover = false, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-lg border bg-card text-card-foreground shadow-card",
        hover && "transition hover:-translate-y-0.5 hover:shadow-float",
        className
      )}
      {...props}
    />
  )
);
Card.displayName = "Card";
```

- [ ] **Step 3: Verify build + tests**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: lint clean; 67 tests pass; build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/button.tsx frontend/src/components/ui/card.tsx
git commit -m "feat(ui): tune Button (pill size, semibold) + Card (shadow-card, hover lift)"
```

---

### Task 5: PageHeader eyebrow support

**Files:**
- Modify: `frontend/src/components/page-header.tsx`

**Interfaces:**
- Produces: `<PageHeader eyebrow="..." title="..." .../>` — optional uppercase eyebrow above the title. Consumes `Eyebrow` (Task 2).

- [ ] **Step 1: Update `frontend/src/components/page-header.tsx`**

Replace the file with:

```tsx
import type { ReactNode } from "react";
import { Eyebrow } from "@/components/eyebrow";

export function PageHeader({
  title,
  description,
  crumbs,
  actions,
  eyebrow,
}: {
  title: string;
  description?: string;
  crumbs?: string[];
  actions?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        {crumbs && crumbs.length > 0 && (
          <nav className="mb-1 text-sm text-muted-foreground">{crumbs.join(" / ")}</nav>
        )}
        {eyebrow && <Eyebrow className="mb-1.5">{eyebrow}</Eyebrow>}
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Verify tests + lint**

Run: `cd frontend && npm test && npm run lint`
Expected: all pass (no existing test imports PageHeader's internals; if one breaks, fix it minimally).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/page-header.tsx
git commit -m "feat(ui): add eyebrow prop to PageHeader"
```

---

### Task 6: Shell restyle — sidebar, app layout, auth layout

**Files:**
- Modify: `frontend/src/components/app-sidebar.tsx` (className-only changes)
- Modify: `frontend/src/app/(app)/layout.tsx`
- Create: `frontend/src/app/(auth)/layout.tsx`

**Interfaces:**
- Produces: app content sits on `bg-canvas`; sidebar uses Apple nav pill styling; auth pages render inside a centered card on a vertical gradient.

- [ ] **Step 1: Restyle the `(app)` layout canvas**

Replace `frontend/src/app/(app)/layout.tsx` with:

```tsx
import { RequireAuth } from "@/components/require-auth";
import { AppSidebar } from "@/components/app-sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <div className="flex min-h-screen bg-canvas">
        <AppSidebar />
        <main className="flex-1 overflow-y-auto px-8 py-6">{children}</main>
      </div>
    </RequireAuth>
  );
}
```

- [ ] **Step 2: Create the `(auth)` layout**

Create `frontend/src/app/(auth)/layout.tsx`:

```tsx
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main
      className="flex min-h-screen items-center justify-center px-4 py-8"
      style={{
        background:
          "linear-gradient(180deg, hsl(var(--hero-from)) 0%, hsl(var(--hero-to)) 100%)",
      }}
    >
      <div className="w-full max-w-md">{children}</div>
    </main>
  );
}
```

- [ ] **Step 3: Restyle `AppSidebar` nav items**

Open `frontend/src/components/app-sidebar.tsx`. This file is large and client-interactive; make ONLY these className changes (do not alter any logic, hooks, handlers, or the language-mode control):

- Sidebar root `<aside>`: add `bg-card` and keep the existing border/right divider. If it currently has no explicit width class, leave structure as-is.
- For each nav link's active vs. inactive className, change the active state to `bg-accent text-foreground` (tinted pill) and inactive to `text-muted-foreground hover:bg-accent hover:text-foreground`, with `h-11 rounded-md` rows. Apply via the existing `cn(...)` active-class logic already present — swap the active/inactive class strings in place.
- Add a `Separator` or `<div className="my-2 h-px bg-border" />` between the primary `NAV` group and the `MANAGE` group (the `showManage` block).

Read the file first to find the exact active-class `cn(...)` call, then edit those strings only. Do not touch the permission logic, the language `<Select>`, or the logout button's behavior.

- [ ] **Step 4: Verify build + tests**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: all pass. (Sidebar has no unit test; build + lint is the gate.)

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(app)/layout.tsx" "frontend/src/app/(auth)/layout.tsx" frontend/src/components/app-sidebar.tsx
git commit -m "feat(ui): Apple shell — canvas bg, auth gradient, sidebar pill nav"
```

---

### Task 7: Restyle login + register (mocked: `login.html`)

**Files:**
- Modify: `frontend/src/app/(auth)/login/page.tsx`
- Modify: `frontend/src/app/(auth)/register/page.tsx`

Reference: `cissp-exam-ui/pages/login.html` (centered card, logo tile, tab toggle, icon-leading fields, pill submit).

**Interfaces:**
- Consumes: `Field` (Task 3), `Button` `size="pill"` (Task 4), `Eyebrow` (Task 2). Preserves all existing auth logic (fetch to `/api/auth/login`, `setAuth`, `next` redirect, dev-login button).

- [ ] **Step 1: Restyle `frontend/src/app/(auth)/login/page.tsx`**

Keep ALL logic (`loginWith`, `submit`, dev-login, `useSearchParams` `next`, `setAuth`/`setHydrated`). Replace only the JSX return of `LoginForm` with the Apple treatment. The full target file:

```tsx
"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Mail, Lock, ShieldCheck } from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/field";

const DEV_ADMIN_EMAIL = "admin@example.com";
const DEV_ADMIN_PASSWORD = "admin";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/practice";
  const setAuth = useAuthStore((s) => s.setAuth);
  const setHydrated = useAuthStore((s) => s.setHydrated);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loginWith(creds: { email: string; password: string }) {
    setError(null);
    setBusy(true);
    try {
      const resp = await fetch(`${BACKEND}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(creds),
      });
      if (!resp.ok) {
        setError(resp.status === 429 ? "Too many attempts. Try later." : "Invalid credentials.");
        return;
      }
      const data = await resp.json();
      setAuth(data.user, data.access_token, data.refresh_token);
      setHydrated(true);
      router.push(next);
    } finally {
      setBusy(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    void loginWith({ email, password });
  }

  return (
    <div>
      <div className="mb-8 text-center">
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary">
          <ShieldCheck className="h-6 w-6 text-primary-foreground" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">CISSP Exam Prep</h1>
        <p className="mt-1 text-sm text-muted-foreground">Master cybersecurity certification</p>
      </div>

      <Card className="rounded-2xl p-6 sm:p-8">
        <h2 className="mb-6 text-lg font-semibold">Log in</h2>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email" htmlFor="signin-email" icon={Mail}>
            <Input
              id="signin-email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              required
            />
          </Field>
          <Field label="Password" htmlFor="signin-password" icon={Lock}>
            <Input
              id="signin-password"
              type="password"
              autoComplete="current-password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
              required
            />
          </Field>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" size="pill" className="w-full" disabled={busy}>
            {busy ? "Logging in…" : "Log in"}
          </Button>
        </form>
        <Button
          type="button"
          variant="outline"
          size="pill"
          className="mt-3 w-full border-dashed"
          disabled={busy}
          onClick={() => void loginWith({ email: DEV_ADMIN_EMAIL, password: DEV_ADMIN_PASSWORD })}
          title={`Logs in as ${DEV_ADMIN_EMAIL} / ${DEV_ADMIN_PASSWORD}`}
        >
          Dev login (admin / admin)
        </Button>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          No account?{" "}
          <a href="/register" className="font-medium text-primary hover:underline">
            Register
          </a>
        </p>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
```

- [ ] **Step 2: Restyle `frontend/src/app/(auth)/register/page.tsx`**

Read the existing register page first (it has its own register logic). Apply the SAME visual treatment as login: `Card` with `rounded-2xl p-6 sm:p-8`, the ShieldCheck logo tile header, `Field`+icon for email/name/password, `Button size="pill" className="w-full"` submit, and a link back to `/login`. Preserve the existing register fetch logic, field state, and error handling exactly — change only markup/styling to mirror login. Do not introduce a tab toggle (login and register are separate routes).

- [ ] **Step 3: Verify build + tests + lint**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(auth)/login/page.tsx" "frontend/src/app/(auth)/register/page.tsx"
git commit -m "feat(ui): Apple login + register cards"
```

---

### Task 8: Restyle dashboard (mocked: `dashboard.html`)

**Files:**
- Modify: `frontend/src/app/(app)/dashboard/page.tsx`

Reference: `cissp-exam-ui/pages/dashboard.html` (hero stat row of 4 KPI cards + media-card grid + CTA).

**Interfaces:** Consumes `PageHeader` (eyebrow), `Card` (`hover`), `Eyebrow`. Preserves all existing data fetching and links.

- [ ] **Step 1: Read the current dashboard page**

Run: `cd frontend && cat "src/app/(app)/dashboard/page.tsx"`
Identify: the data it fetches (likely `/api/analytics/dashboard`), the KPIs it shows, and any "continue practicing" / "start exam" CTAs. Preserve all of that.

- [ ] **Step 2: Restyle to the mockup composition**

Rewrite the JSX (keep all hooks/fetch/handlers) to:
- `<PageHeader eyebrow="Overview" title="Dashboard" description="..." />`
- A 4-up KPI grid: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4` — each KPI is a `Card className="p-4"` with a `rounded-lg h-10 w-10` brand-tinted icon tile (`bg-accent text-primary`), a `text-xs text-muted-foreground` label, a `text-2xl font-semibold` value, and a small delta/trend line.
- A section with `<Eyebrow>Continue</Eyebrow>` and a row of `Card hover` media-cards linking to Practice / Exam / Review (use the existing CTAs/links already on the page).
- Keep the actual data values and links from the current page — only the visual treatment changes.

If the current dashboard surfaces different data than the mockup's KPIs (Total Questions / Accuracy / Study Hours / Streak), map the mockup's visual slots onto whatever real data the page has; do not invent fake numbers.

- [ ] **Step 3: Verify build + tests + lint**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(app)/dashboard/page.tsx"
git commit -m "feat(ui): Apple dashboard — KPI grid + media cards"
```

---

### Task 9: Restyle practice setup + runner + done (mocked: `practice-setup.html`, `quiz.html`, `explanation.html`)

**Files:**
- Modify: `frontend/src/app/(app)/practice/page.tsx` (setup)
- Modify: `frontend/src/app/(app)/practice/sessions/[id]/page.tsx` (runner)
- Modify: `frontend/src/app/(app)/practice/sessions/[id]/done/page.tsx` (explanation/summary)

Reference: `cissp-exam-ui/pages/practice-setup.html` (two-column: filters left, summary + start CTA right), `quiz.html` (question card, progress bar, option list, sticky footer), `explanation.html` (correctness banner, option review, explanation prose, next CTA).

**Interfaces:** Consumes `PageHeader`, `Card`, `Button`, `Field`. CRITICAL: the runner uses tested state machines (`runner-machine`, `session-tracker`) and `option-list` — do NOT alter those modules or their props; only the page-level JSX/className wrapping them. The 67 tests include `option-list.test.tsx` and `runner-machine.test.ts` — they must stay green.

- [ ] **Step 1: Restyle practice setup page**

Read `frontend/src/app/(app)/practice/page.tsx`. Rewrite JSX (keep the create-session form logic — see `create-session-form.test.tsx` for its contract) to the two-column mockup: left `Card` with domain/count/filters via `Field`/`Select`/`Checkbox`; right `Card` with a summary and a `Button size="pill"` "Start practice" CTA. Preserve the exact form field names and submission behavior the test expects.

- [ ] **Step 2: Restyle practice runner page**

Read `frontend/src/app/(app)/practice/sessions/[id]/page.tsx`. Wrap the existing runner in the mockup's question-card layout: top progress bar (`h-1.5 rounded-full bg-muted` with a `bg-primary` fill), a `Card` holding the question stem + `<BilingualText>` + the existing `<OptionList>` (unchanged), and a sticky footer with Prev/Next, flag, bookmark `Button`s. Do not change how answers are submitted or how position advances.

- [ ] **Step 3: Restyle practice done/summary page**

Read `frontend/src/app/(app)/practice/sessions/[id]/done/page.tsx`. Apply the explanation mockup: a correctness `Card` banner (success/destructive tint), per-option review list, explanation prose, and a `Button size="pill"` "Next" / "Back to practice" CTA. Preserve summary data and links.

- [ ] **Step 4: Verify build + tests + lint**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: all 67 pass — especially `create-session-form`, `option-list`, `runner-machine`, `session-tracker`, `session-payload`.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(app)/practice"
git commit -m "feat(ui): Apple practice setup + runner + summary"
```

---

### Task 10: Restyle exam setup + runner (fixed + CAT) + report + review

**Files:**
- Modify: `frontend/src/app/(app)/exam/page.tsx` (setup)
- Modify: `frontend/src/app/(app)/exam/sessions/[id]/page.tsx` (fixed + CAT runner)
- Modify: `frontend/src/app/(app)/exam/sessions/[id]/report/page.tsx` (exam-report)
- Modify: `frontend/src/app/(app)/exam/sessions/[id]/review/page.tsx` (explanation)

Reference: `cissp-exam-ui/pages/cat-exam.html`, `exam-report.html`, `explanation.html`.

**Interfaces:** Consumes `PageHeader`, `Card`, `Button`. CRITICAL: the runners use `features/exam/fixed-runner.tsx` and `features/exam/cat-runner.tsx` + tested helpers (`cat-runner.test`, `exam-tracker.test`, `start-form.test`, `format.test`). Do NOT alter those modules' logic/props; only page-level JSX/className. CAT must remain forward-only with its persistent disclaimer and language toggle that never calls `/next`.

- [ ] **Step 1: Restyle exam setup page**

Read `frontend/src/app/(auth)/exam/page.tsx` → actually `frontend/src/app/(app)/exam/page.tsx`. Rewrite JSX (keep the start-form logic per `start-form.test.tsx`) to a `Card`-based setup: kind selector (fixed/CAT), domain/count controls, duration display, `Button size="pill"` "Start exam". Preserve field names and submission.

- [ ] **Step 2: Restyle exam runner page (fixed + CAT)**

Read `frontend/src/app/(app)/exam/sessions/[id]/page.tsx`. It branches on session kind. Wrap both branches in the mockup question-card shell (progress bar / countdown timer display, `Card` with stem + options, sticky footer). For CAT: keep the persistent study-tool disclaimer (`cat_engine.DISCLAIMER`) and the in-runner language toggle as pure client state. Keep the fixed exam's revisable positional answers + question palette + lazy auto-submit. Change only styling/wrapping.

- [ ] **Step 3: Restyle exam report page**

Read `frontend/src/app/(app)/exam/sessions/[id]/report/page.tsx`. Apply `exam-report.html`: a score hero `Card` (scaled score, pass/fail badge, accuracy), per-domain bars (hand-rolled divs with `bg-primary` fills), time, wrong-question list. For CAT reports, surface ability/CI/SEM/readiness + `DISCLAIMER`. Preserve all report data and the `format` helpers.

- [ ] **Step 4: Restyle exam review page**

Read `frontend/src/app/(app)/exam/sessions/[id]/review/page.tsx`. Apply the `explanation.html` treatment (correctness banner, per-option review, explanation prose). Preserve data.

- [ ] **Step 5: Verify build + tests + lint**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: all 67 pass — especially `cat-runner`, `exam-tracker`, `start-form`, `format`.

- [ ] **Step 6: Commit**

```bash
git add "frontend/src/app/(app)/exam"
git commit -m "feat(ui): Apple exam setup + fixed/CAT runner + report + review"
```

---

### Task 11: Extrapolated retheme — analytics, review, import

**Files:**
- Modify: `frontend/src/app/(app)/analytics/page.tsx`
- Modify: `frontend/src/app/(app)/review/page.tsx`
- Modify: `frontend/src/app/(app)/import/page.tsx`

These have no mockup. Apply the established language: `<PageHeader eyebrow=...>`, `Card` surfaces with `shadow-card`, `Eyebrow` section labels, `Button size="pill"` primary actions, hand-rolled charts recolored to the brand scale (`bg-primary`, `bg-primary/60`, `bg-primary/30`, `bg-success`, `bg-destructive`).

- [ ] **Step 1: analytics** — Read the page. Add `<PageHeader eyebrow="Insights" title="Analytics" .../>`. Wrap each chart/section in `Card className="p-6"`. Recolor all inline SVG/CSS chart fills to the brand scale (replace any hardcoded hex like `#8884d8`/`#82ca9d` with `hsl(var(--primary))` etc., or Tailwind `text-primary`/`fill-primary` classes). Keep all data fetching and the existing chart logic.

- [ ] **Step 2: review** — Read the page. Add `<PageHeader eyebrow="Review" title="Wrong / Bookmarked / Flagged" .../>`. Wrap the re-practice launchers in `Card hover` media-cards. Preserve subset-scoped session launch logic.

- [ ] **Step 3: import** — Read the page. Add `<PageHeader eyebrow="Content" title="Import" .../>`. Restyle the preview → commit/rollback wizard steps as a sequence of `Card`s with `Button size="pill"` actions. Preserve the ETL preview/commit/rollback calls and `question:import` gating.

- [ ] **Step 4: Verify build + tests + lint**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(app)/analytics" "frontend/src/app/(app)/review" "frontend/src/app/(app)/import"
git commit -m "feat(ui): extrapolated retheme — analytics, review, import"
```

---

### Task 12: Extrapolated retheme — questions (list, new, edit, detail)

**Files:**
- Modify: `frontend/src/app/(app)/questions/page.tsx`
- Modify: `frontend/src/app/(app)/questions/new/page.tsx`
- Modify: `frontend/src/app/(app)/questions/[id]/edit/page.tsx`
- Modify: `frontend/src/app/(app)/questions/[id]/page.tsx`

**Interfaces:** Consumes `PageHeader`, `Card`, `Button`, `Field`. CRITICAL: the editor uses `features/questions/editor.tsx` + tested helpers (`editor.test`, `labels.test`). Do NOT alter those modules' logic; only page-level styling. The editor's English/中文 tabs and publish-completeness validation (FR-LANG-09) must remain intact.

- [ ] **Step 1: questions list** — Add `<PageHeader eyebrow="Content" title="Questions" actions={<Button size="pill">New</Button>}/>`. Wrap the filter bar in a `Card` and the list rows in `Card hover` or a `Card` table surface. Preserve filters, pagination, and `question:read` gating.

- [ ] **Step 2: questions/new + edit** — Wrap the existing editor in a `Card` with `PageHeader eyebrow="Content"`. Keep the English/中文 tab UI and publish-completeness validation visually consistent (use `Button size="pill"` for save/publish). Preserve all editor logic and the `editor.test`/`labels.test` contracts.

- [ ] **Step 3: questions detail** — Add `PageHeader`. Restyle the review state machine controls (submit/approve/request_changes/archive/restore), revisions history, and correction feedback into `Card` sections with `Button` actions. Preserve the review state machine and `question:publish` gating.

- [ ] **Step 4: Verify build + tests + lint**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: all 67 pass — especially `editor`, `labels`.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/(app)/questions"
git commit -m "feat(ui): extrapolated retheme — questions list/new/edit/detail"
```

---

### Task 13: Extrapolated retheme — taxonomy + admin

**Files:**
- Modify: `frontend/src/app/(app)/taxonomy/page.tsx`
- Modify: `frontend/src/app/(app)/admin/page.tsx`

**Interfaces:** Consumes `PageHeader`, `Card`, `Tabs`, `Button`. CRITICAL: preserve all `admin:manage_taxonomy` / per-tab permission gating and the admin tab logic.

- [ ] **Step 1: taxonomy** — Add `<PageHeader eyebrow="Admin" title="Taxonomy" .../>`. Restyle the blueprints+domains / books+chapters / knowledge-points tree / tags sections as `Card`s with consistent spacing and `Button` actions. Preserve `admin:manage_taxonomy` gating and all CRUD calls.

- [ ] **Step 2: admin** — Add `<PageHeader eyebrow="Backoffice" title="Admin" .../>`. Restyle the users / classes / CAT-param versions / quality queue / audit-log / operational-reports tabs as `Card`-based tab panels with `Button size="pill"` actions. Preserve every per-permission tab gate (`admin:manage_users`, `admin:manage_taxonomy`, `question:publish`, `admin:view_audit`, `admin:view_reports`).

- [ ] **Step 3: Verify build + tests + lint**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: all 67 pass.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(app)/taxonomy" "frontend/src/app/(app)/admin"
git commit -m "feat(ui): extrapolated retheme — taxonomy + admin"
```

---

### Task 14: Final verification — full stack up + visual click-through

**Files:** none (verification only)

- [ ] **Step 1: Clean build + full test suite**

Run: `cd frontend && npm run lint && npm test && npm run build`
Expected: lint clean; all 67 tests pass; build succeeds.

- [ ] **Step 2: Bring the full stack up**

Run: `cd /home/john/cissp_exam && docker compose up -d --build`
Expected: `docker compose ps` shows postgres, redis, backend, frontend healthy; `curl http://localhost:8000/health` → `{"status":"ok","db":"ok","redis":"ok"}`; `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/` → 200.

- [ ] **Step 3: Visual click-through (confirm new look + unchanged behavior)**

In a browser at `http://localhost:3000`:
1. Login (use Dev login admin/admin) — confirm Apple login card on gradient.
2. Dashboard — confirm KPI grid + media cards on canvas.
3. Practice setup → start → answer → summary — confirm question card, progress bar, option selection, explanation banner.
4. Exam setup → fixed exam → answer (revisable) → report — confirm palette, timer, lazy auto-submit, score hero.
5. Exam setup → CAT → answer forward-only → report — confirm persistent disclaimer, ability/CI/SEM, no-advance on language toggle.
6. Toggle language mode (en/zh/bilingual) in the sidebar and in-runner — confirm instant toggle, no refetch, no CAT advance.
7. Analytics, Review, Import, Questions (list/new/edit/detail), Taxonomy, Admin — confirm rethemed cards, RBAC gating intact.

If any behavior regresses, fix it (the underlying logic modules were not touched, so regressions should only be from broken JSX — fix the page, re-run tests).

- [ ] **Step 4: Final commit if any fixes were made**

```bash
git add -A
git commit -m "fix(ui): post-verification touch-ups"
```

- [ ] **Step 5: Report**

Report: test count, lint/build status, docker health, and confirm the click-through passed in all three language modes.

---

## Self-Review

**Spec coverage:**
- §2 Token mapping → Task 1 ✓
- §3 Typography (DM Sans) → Task 1 ✓
- §4 Component strategy (Button pill/semibold, Card shadow/hover, Field icon-leading, Eyebrow, keep lucide) → Tasks 2, 3, 4 ✓
- §5 Shell & navigation → Task 6 ✓
- §6 Mocked pages (login, register, dashboard, practice-setup, quiz, explanation, cat-exam, exam-report) → Tasks 7, 8, 9, 10 ✓
- §7 Extrapolated pages (analytics, review, import, questions×4, taxonomy, admin) → Tasks 11, 12, 13 ✓
- §8 Testing & verification (tests + lint + build + docker visual) → Task 14 ✓
- Out-of-scope items (dark mode, mobile, backend, mask-image icons, 1.2rem-everywhere) → respected, no tasks add them ✓

**Placeholder scan:** Page-restyle tasks (8–13) describe concrete className/component changes against the existing code rather than full rewrites, because the existing page logic must be preserved verbatim and reading-then-editing is the correct procedure. Each step names the exact file, the exact mockup reference, the exact primitives consumed, and the exact behavior-preservation contract. No "TBD"/"TODO"/"add error handling" present.

**Type consistency:** `<Eyebrow>` (props: `children`, `className`) defined Task 2, consumed Task 5. `<Field>` (props: `children`, `icon`, `label`, `htmlFor`, `className`) defined Task 3, consumed Task 7. `Button size="pill"` defined Task 4, consumed Tasks 7–13. `Card hover` prop defined Task 4, consumed Tasks 8, 11. `PageHeader eyebrow` prop defined Task 5, consumed Tasks 8–13. `bg-canvas`/`shadow-card`/`shadow-float`/`rounded-2xl`/`font-sans` utilities defined Task 1, consumed throughout. All consistent.

**Scope:** Single subsystem (frontend UI), one plan, 14 tasks each independently testable. No decomposition needed.
