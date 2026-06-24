# Frontend Foundation + Practice (Sub-project I-1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reusable frontend design system, app shell, auth/route guards, data-fetching layer, and a complete end-to-end Practice experience over the existing `/api/practice/*` and read-only taxonomy APIs — with zero backend changes.

**Architecture:** Next.js 14 App Router. Server components by default; `'use client'` only for interactivity (auth, runner, forms, query hooks). Four layers: (1) a shadcn/ui design system copied into `src/components/ui/` with an HSL CSS-variable token layer; (2) a TanStack Query data layer wrapping the existing `apiFetch`/`apiJson` client; (3) an `(app)` route group with a left-sidebar shell guarded by `<RequireAuth>`; (4) feature modules — I-1 ships `practice/`.

**Tech Stack:** Next.js 14.2.18, React 18.3.1, TypeScript 5.6 (strict), Tailwind CSS 3.4.15, shadcn/ui (Radix UI + CVA, copy-in), TanStack Query v5, Zustand v5 (existing), Vitest 2.1.6 + Testing Library + jsdom.

## Global Constraints

- **No backend changes.** All 366 backend tests must still pass; the backend API surface is frozen. (Acceptance criterion #7.)
- **No raw `fetch` / `useState`+`useEffect` server reads in feature code.** Every server read → a TanStack Query hook; every mutation → `useMutation` with `onSuccess` query-key invalidation. (Acceptance criterion #6.)
- **Backend field names are authoritative** — use them verbatim, NOT the spec's draft names:
  - Session create: `domain_id` (singular UUID|null), `tag_id` (singular UUID|null), `chapter_ids` (UUID[] array), `book_id`, `question_type` (string), `difficulty` (int|null), `subset`, `order_mode`, `count` (only required field).
  - Options are selected and reported by **`order_index` (int)**, never option UUID.
  - The explanation field on an answer result is **`correct_rationale`** (plus `key_point_summary`); per-option explanation is `per_option[].explanation`.
  - Question delivery `position` is **0-indexed**.
  - Answer submit body: `{ position, selected: number[], started_at: ISO-string }`.
  - Question-state PUT fields: `is_bookmarked`, `is_flagged_review`, `is_mastered`, `is_questioned`, `note`, `error_type`.
- **No `GET /api/practice/sessions` list endpoint exists.** Resume is implemented via **client-side localStorage tracking** of session IDs created on this device, re-fetched individually with `GET /api/practice/sessions/{id}`.
- **No knowledge-point filter** on session creation — the create form does NOT render a KP dropdown.
- **`GET /api/domains` returns all blueprints' domains** (not filtered to current); render them ordered by `number`.
- **`GET /api/tags` returns raw `{id, name, description}` dicts** (no Pydantic model) — type accordingly.
- **Auth tokens live in `sessionStorage`** (existing behavior, keep). User object is NOT persisted — it is restored on hydrate via `GET /api/auth/me`.
- **Permissions** are on `user.perms` (string[]); Admin nav link gated by any `admin:*` perm.
- **UI language: English.** Question content is rendered verbatim from the backend.
- **Path alias:** `@/*` → `./src/*` (already configured in tsconfig; must be mirrored in vitest config).
- **Visual tokens (Modern SaaS):** primary `#2563eb`, success emerald-600, destructive red-600, ring blue-500, radius `0.5rem`, white canvas, slate neutrals. Expressed as HSL CSS variables (Tailwind 3 + shadcn convention).

---

## File Structure

**Config & foundation**
- Modify `frontend/package.json` — add runtime + dev dependencies.
- Create `frontend/vitest.config.ts` — jsdom env, `@` alias, setup file.
- Create `frontend/src/test/setup.ts` — Testing Library matchers + cleanup.
- Modify `frontend/tailwind.config.ts` — `darkMode: "class"`, token color mapping, `tailwindcss-animate` plugin.
- Modify `frontend/src/app/globals.css` — HSL CSS-variable token layer.
- Create `frontend/src/lib/utils.ts` — `cn()` class-merge helper.
- Create `frontend/src/lib/config.ts` — single `BACKEND` resolution.

**Design system** (`frontend/src/components/ui/`, shadcn copy-in)
- `button.tsx`, `card.tsx`, `input.tsx`, `textarea.tsx`, `label.tsx`, `badge.tsx`, `separator.tsx`, `skeleton.tsx`, `alert.tsx` (core, batch 1).
- `checkbox.tsx`, `radio-group.tsx`, `select.tsx`, `dialog.tsx`, `tooltip.tsx`, `tabs.tsx`, `sonner.tsx` (interactive, batch 2).

**Shared patterns** (`frontend/src/components/`)
- `providers.tsx` — `QueryClientProvider` + `<Toaster>` (client boundary).
- `page-header.tsx`, `empty-state.tsx`, `error-state.tsx`, `loading.tsx`.
- `require-auth.tsx`, `require-permission.tsx`.
- `app-sidebar.tsx` — left nav (Practice active; Exam/Analytics disabled; Admin perm-gated).

**Data & auth layer** (`frontend/src/lib/`)
- Modify `frontend/src/lib/api.ts` — import `BACKEND` from `config.ts`; keep silent-refresh.
- Modify `frontend/src/lib/auth-store.ts` — add `hydrated` flag, `setHydrated`, `setUser`; `hydrate()` restores tokens only.
- Create `frontend/src/lib/use-hydrated-auth.ts` — restores user via `/api/auth/me`, flips `hydrated`.
- Create `frontend/src/lib/api/types.ts` — TS types mirroring backend schemas.
- Create `frontend/src/lib/api/keys.ts` — query-key factory.
- Create `frontend/src/lib/api/taxonomy.ts` — `useDomains`, `useBooks`, `useChapters`, `useTags`.
- Create `frontend/src/lib/api/practice.ts` — session/question/answer/state hooks.

**Practice feature** (`frontend/src/features/practice/`)
- `runner-machine.ts` — pure selection/submit state machine.
- `session-tracker.ts` — localStorage active-session tracking.
- `session-payload.ts` — pure `buildSessionPayload()`.
- `option-list.tsx` — renders single/multi/true-false options uniformly.
- `create-session-form.tsx`, `resume-panel.tsx`, `runner.tsx`, `summary.tsx`.

**Routes** (`frontend/src/app/`)
- Modify `frontend/src/app/layout.tsx` — wrap children in `<Providers>`.
- Modify `frontend/src/app/page.tsx` — redirect `/` → `/practice` or `/login`.
- Modify `frontend/src/app/(auth)/login/page.tsx` — `?next=` redirect.
- Create `frontend/src/app/(app)/layout.tsx` — `<RequireAuth>` + sidebar shell.
- Create `frontend/src/app/(app)/practice/page.tsx` — landing (Resume / New tabs).
- Create `frontend/src/app/(app)/practice/sessions/[id]/page.tsx` — runner.
- Create `frontend/src/app/(app)/practice/sessions/[id]/done/page.tsx` — summary.

---

### Task 1: Dependencies + Vitest harness

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`
- Test: `frontend/src/lib/__tests__/smoke.test.ts`

**Interfaces:**
- Produces: a runnable `npm test` (Vitest + jsdom + Testing Library, `@` alias resolved). Later tasks rely on this harness.

- [ ] **Step 1: Add dependencies to `package.json`**

Merge these into the existing `dependencies` and `devDependencies` (keep `next`, `react`, `react-dom`, `zustand`):

```jsonc
// dependencies — add:
"@tanstack/react-query": "5.59.20",
"@radix-ui/react-checkbox": "1.1.2",
"@radix-ui/react-dialog": "1.1.2",
"@radix-ui/react-label": "2.1.0",
"@radix-ui/react-radio-group": "1.2.1",
"@radix-ui/react-select": "2.1.2",
"@radix-ui/react-separator": "1.1.0",
"@radix-ui/react-slot": "1.1.0",
"@radix-ui/react-tabs": "1.1.1",
"@radix-ui/react-tooltip": "1.1.3",
"class-variance-authority": "0.7.0",
"clsx": "2.1.1",
"lucide-react": "0.454.0",
"sonner": "1.7.0",
"tailwind-merge": "2.5.4",
"tailwindcss-animate": "1.0.7"

// devDependencies — add:
"@testing-library/jest-dom": "6.6.3",
"@testing-library/react": "16.0.1",
"@testing-library/user-event": "14.5.2",
"@vitejs/plugin-react": "4.3.3",
"jsdom": "25.0.1"
```

- [ ] **Step 2: Install**

Run: `cd frontend && npm install`
Expected: completes; `node_modules/@tanstack/react-query` and `node_modules/jsdom` exist.

- [ ] **Step 3: Create `frontend/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
```

- [ ] **Step 4: Create `frontend/src/test/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 5: Write the harness smoke test `frontend/src/lib/__tests__/smoke.test.ts`**

```ts
import { describe, it, expect } from "vitest";

describe("vitest harness", () => {
  it("runs and resolves the @ alias path style", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 6: Run the test to verify the harness works**

Run: `cd frontend && npm test`
Expected: PASS — 1 test passed.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/src/test/setup.ts frontend/src/lib/__tests__/smoke.test.ts
git commit -m "chore(frontend): add design-system + query + test dependencies and Vitest harness"
```

---

### Task 2: Design tokens (globals.css + Tailwind config)

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/tailwind.config.ts`

**Interfaces:**
- Produces: Tailwind utility classes `bg-primary`, `text-primary-foreground`, `bg-success`, `bg-destructive`, `border-border`, `ring-ring`, `rounded-lg` etc., backed by HSL CSS variables. Every shadcn component in later tasks depends on these tokens.

- [ ] **Step 1: Replace `frontend/src/app/globals.css` with the token layer**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222 47% 11%;
    --card: 0 0% 100%;
    --card-foreground: 222 47% 11%;
    --popover: 0 0% 100%;
    --popover-foreground: 222 47% 11%;
    --primary: 221 83% 53%;
    --primary-foreground: 0 0% 100%;
    --secondary: 210 40% 96%;
    --secondary-foreground: 222 47% 11%;
    --muted: 210 40% 96%;
    --muted-foreground: 215 16% 47%;
    --accent: 210 40% 96%;
    --accent-foreground: 222 47% 11%;
    --success: 142 71% 45%;
    --success-foreground: 0 0% 100%;
    --destructive: 0 72% 51%;
    --destructive-foreground: 0 0% 100%;
    --border: 214 32% 91%;
    --input: 214 32% 91%;
    --ring: 217 91% 60%;
    --radius: 0.5rem;
  }
}

@layer base {
  * {
    border-color: hsl(var(--border));
  }
  body {
    background-color: hsl(var(--background));
    color: hsl(var(--foreground));
  }
}
```

- [ ] **Step 2: Replace `frontend/tailwind.config.ts` with the token-mapped config**

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
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
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
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

- [ ] **Step 3: Verify the build still compiles CSS**

Run: `cd frontend && npm run build`
Expected: build succeeds (no Tailwind/PostCSS errors). The home page may not reflect tokens yet — that is fine.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/globals.css frontend/tailwind.config.ts
git commit -m "feat(frontend): add Modern SaaS design tokens (HSL CSS variables + Tailwind mapping)"
```

---

### Task 3: `cn()` helper + `BACKEND` config constant

**Files:**
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/lib/config.ts`
- Test: `frontend/src/lib/__tests__/utils.test.ts`

**Interfaces:**
- Produces: `cn(...inputs: ClassValue[]): string` (used by every UI component) and `BACKEND: string` (single source of the backend base URL).

- [ ] **Step 1: Write the failing test `frontend/src/lib/__tests__/utils.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn", () => {
  it("joins truthy class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });
  it("drops falsy values", () => {
    expect(cn("a", false && "b", undefined, "c")).toBe("a c");
  });
  it("merges conflicting tailwind classes (last wins)", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- utils`
Expected: FAIL — cannot resolve `@/lib/utils`.

- [ ] **Step 3: Create `frontend/src/lib/utils.ts`**

```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 4: Create `frontend/src/lib/config.ts`**

```ts
export const BACKEND: string =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- utils`
Expected: PASS — 3 tests passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/utils.ts frontend/src/lib/config.ts frontend/src/lib/__tests__/utils.test.ts
git commit -m "feat(frontend): add cn() class helper and single BACKEND config constant"
```

---

### Task 4: Core UI primitives (batch)

**Files:**
- Create: `frontend/src/components/ui/button.tsx`, `card.tsx`, `input.tsx`, `textarea.tsx`, `label.tsx`, `badge.tsx`, `separator.tsx`, `skeleton.tsx`, `alert.tsx`

**Interfaces:**
- Produces: `Button` (+`buttonVariants`), `Card`/`CardHeader`/`CardTitle`/`CardDescription`/`CardContent`/`CardFooter`, `Input`, `Textarea`, `Label`, `Badge` (+`badgeVariants`), `Separator`, `Skeleton`, `Alert`/`AlertTitle`/`AlertDescription`. These are vendored shadcn components; their test cycle is a successful typecheck/build, exercised in later feature tasks.

- [ ] **Step 1: Create `frontend/src/components/ui/button.tsx`**

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
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
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

- [ ] **Step 2: Create `frontend/src/components/ui/card.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("rounded-lg border bg-card text-card-foreground shadow-sm", className)} {...props} />
  )
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
  )
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-lg font-semibold leading-none tracking-tight", className)} {...props} />
  )
);
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  )
);
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
);
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center p-6 pt-0", className)} {...props} />
  )
);
CardFooter.displayName = "CardFooter";

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter };
```

- [ ] **Step 3: Create `frontend/src/components/ui/input.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export { Input };
```

- [ ] **Step 4: Create `frontend/src/components/ui/textarea.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";

export { Textarea };
```

- [ ] **Step 5: Create `frontend/src/components/ui/label.tsx`**

```tsx
"use client";
import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { cn } from "@/lib/utils";

const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn("text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70", className)}
    {...props}
  />
));
Label.displayName = LabelPrimitive.Root.displayName;

export { Label };
```

- [ ] **Step 6: Create `frontend/src/components/ui/badge.tsx`**

```tsx
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        success: "border-transparent bg-success text-success-foreground",
        destructive: "border-transparent bg-destructive text-destructive-foreground",
        outline: "text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
```

- [ ] **Step 7: Create `frontend/src/components/ui/separator.tsx`**

```tsx
"use client";
import * as React from "react";
import * as SeparatorPrimitive from "@radix-ui/react-separator";
import { cn } from "@/lib/utils";

const Separator = React.forwardRef<
  React.ElementRef<typeof SeparatorPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>
>(({ className, orientation = "horizontal", decorative = true, ...props }, ref) => (
  <SeparatorPrimitive.Root
    ref={ref}
    decorative={decorative}
    orientation={orientation}
    className={cn("shrink-0 bg-border", orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]", className)}
    {...props}
  />
));
Separator.displayName = SeparatorPrimitive.Root.displayName;

export { Separator };
```

- [ ] **Step 8: Create `frontend/src/components/ui/skeleton.tsx`**

```tsx
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}

export { Skeleton };
```

- [ ] **Step 9: Create `frontend/src/components/ui/alert.tsx`**

```tsx
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative w-full rounded-lg border p-4 [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg~*]:pl-7",
  {
    variants: {
      variant: {
        default: "bg-background text-foreground",
        destructive: "border-destructive/50 text-destructive [&>svg]:text-destructive",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

const Alert = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>>(
  ({ className, variant, ...props }, ref) => (
    <div ref={ref} role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
  )
);
Alert.displayName = "Alert";

const AlertTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h5 ref={ref} className={cn("mb-1 font-medium leading-none tracking-tight", className)} {...props} />
  )
);
AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("text-sm [&_p]:leading-relaxed", className)} {...props} />
  )
);
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };
```

- [ ] **Step 10: Verify typecheck/build**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/components/ui/button.tsx frontend/src/components/ui/card.tsx frontend/src/components/ui/input.tsx frontend/src/components/ui/textarea.tsx frontend/src/components/ui/label.tsx frontend/src/components/ui/badge.tsx frontend/src/components/ui/separator.tsx frontend/src/components/ui/skeleton.tsx frontend/src/components/ui/alert.tsx
git commit -m "feat(frontend): add core shadcn/ui primitives (button, card, input, textarea, label, badge, separator, skeleton, alert)"
```

---

### Task 5: Interactive UI primitives (batch)

**Files:**
- Create: `frontend/src/components/ui/checkbox.tsx`, `radio-group.tsx`, `select.tsx`, `dialog.tsx`, `tooltip.tsx`, `tabs.tsx`, `sonner.tsx`

**Interfaces:**
- Produces: `Checkbox`; `RadioGroup`/`RadioGroupItem`; `Select`/`SelectTrigger`/`SelectValue`/`SelectContent`/`SelectItem`; `Dialog`/`DialogTrigger`/`DialogContent`/`DialogHeader`/`DialogTitle`/`DialogDescription`/`DialogFooter`/`DialogClose`; `Tooltip`/`TooltipTrigger`/`TooltipContent`/`TooltipProvider`; `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent`; `Toaster` + re-exported `toast`. Consumed by the create-session form, option list, note dialog, landing tabs, and providers.

- [ ] **Step 1: Create `frontend/src/components/ui/checkbox.tsx`**

```tsx
"use client";
import * as React from "react";
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      "peer h-5 w-5 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
      className
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className={cn("flex items-center justify-center text-current")}>
      <Check className="h-4 w-4" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

export { Checkbox };
```

- [ ] **Step 2: Create `frontend/src/components/ui/radio-group.tsx`**

```tsx
"use client";
import * as React from "react";
import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";
import { Circle } from "lucide-react";
import { cn } from "@/lib/utils";

const RadioGroup = React.forwardRef<
  React.ElementRef<typeof RadioGroupPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root>
>(({ className, ...props }, ref) => (
  <RadioGroupPrimitive.Root className={cn("grid gap-2", className)} {...props} ref={ref} />
));
RadioGroup.displayName = RadioGroupPrimitive.Root.displayName;

const RadioGroupItem = React.forwardRef<
  React.ElementRef<typeof RadioGroupPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Item>
>(({ className, ...props }, ref) => (
  <RadioGroupPrimitive.Item
    ref={ref}
    className={cn(
      "aspect-square h-5 w-5 rounded-full border border-primary text-primary ring-offset-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
      className
    )}
    {...props}
  >
    <RadioGroupPrimitive.Indicator className="flex items-center justify-center">
      <Circle className="h-2.5 w-2.5 fill-current text-current" />
    </RadioGroupPrimitive.Indicator>
  </RadioGroupPrimitive.Item>
));
RadioGroupItem.displayName = RadioGroupPrimitive.Item.displayName;

export { RadioGroup, RadioGroupItem };
```

- [ ] **Step 3: Create `frontend/src/components/ui/select.tsx`**

```tsx
"use client";
import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const Select = SelectPrimitive.Root;
const SelectValue = SelectPrimitive.Value;

const SelectTrigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1",
      className
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown className="h-4 w-4 opacity-50" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
));
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName;

const SelectContent = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = "popper", ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      className={cn(
        "relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
        position === "popper" && "data-[side=bottom]:translate-y-1",
        className
      )}
      position={position}
      {...props}
    >
      <SelectPrimitive.Viewport className={cn("p-1", position === "popper" && "w-full min-w-[var(--radix-select-trigger-width)]")}>
        {children}
      </SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
));
SelectContent.displayName = SelectPrimitive.Content.displayName;

const SelectItem = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className
    )}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <SelectPrimitive.ItemIndicator>
        <Check className="h-4 w-4" />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
));
SelectItem.displayName = SelectPrimitive.Item.displayName;

export { Select, SelectValue, SelectTrigger, SelectContent, SelectItem };
```

- [ ] **Step 4: Create `frontend/src/components/ui/dialog.tsx`**

```tsx
"use client";
import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogClose = DialogPrimitive.Close;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn("fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0", className)}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 sm:rounded-lg",
        className
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props} />
);
DialogHeader.displayName = "DialogHeader";

const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)} {...props} />
);
DialogFooter.displayName = "DialogFooter";

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn("text-lg font-semibold leading-none tracking-tight", className)} {...props} />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export { Dialog, DialogTrigger, DialogClose, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription };
```

- [ ] **Step 5: Create `frontend/src/components/ui/tooltip.tsx`**

```tsx
"use client";
import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95",
        className
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
```

- [ ] **Step 6: Create `frontend/src/components/ui/tabs.tsx`**

```tsx
"use client";
import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground", className)}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm",
      className
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn("mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", className)}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
```

- [ ] **Step 7: Create `frontend/src/components/ui/sonner.tsx`**

```tsx
"use client";
import { Toaster as SonnerToaster, toast } from "sonner";

function Toaster(props: React.ComponentProps<typeof SonnerToaster>) {
  return (
    <SonnerToaster
      position="top-right"
      toastOptions={{
        classNames: {
          toast: "group rounded-md border bg-background text-foreground shadow-lg",
          error: "border-destructive/50",
          success: "border-success/50",
        },
      }}
      {...props}
    />
  );
}

export { Toaster, toast };
```

- [ ] **Step 8: Verify typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ui/checkbox.tsx frontend/src/components/ui/radio-group.tsx frontend/src/components/ui/select.tsx frontend/src/components/ui/dialog.tsx frontend/src/components/ui/tooltip.tsx frontend/src/components/ui/tabs.tsx frontend/src/components/ui/sonner.tsx
git commit -m "feat(frontend): add interactive shadcn/ui primitives (checkbox, radio-group, select, dialog, tooltip, tabs, sonner)"
```

---

### Task 6: API client refactor + silent-refresh test

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/__tests__/api.test.ts`

**Interfaces:**
- Consumes: `BACKEND` from `@/lib/config`; `useAuthStore` from `@/lib/auth-store`.
- Produces: unchanged public surface — `apiFetch(path, init?): Promise<Response>`, `apiJson<T>(path, init?): Promise<T>`, `ApiError` (with `.status`). Behavior change: `BACKEND` is now imported, not re-declared.

- [ ] **Step 1: Write the failing test `frontend/src/lib/__tests__/api.test.ts`**

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiJson, ApiError } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";

const user = { id: "u1", email: "a@b.c", display_name: null, roles: [], perms: [] };

beforeEach(() => {
  useAuthStore.setState({ user, accessToken: "stale", refreshToken: "r1" });
});
afterEach(() => {
  vi.restoreAllMocks();
  useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
});

describe("apiJson silent refresh", () => {
  it("on 401 refreshes once then retries with the new token", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("nope", { status: 401 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user, access_token: "fresh", refresh_token: "r2" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

    const data = await apiJson<{ ok: boolean }>("/api/practice/sessions/x");

    expect(data).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    // second call is the refresh
    expect(String(fetchMock.mock.calls[1][0])).toContain("/api/auth/refresh");
    // third (retry) carries the fresh token
    const retryHeaders = new Headers((fetchMock.mock.calls[2][1] as RequestInit).headers);
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh");
    expect(useAuthStore.getState().accessToken).toBe("fresh");
  });

  it("throws ApiError with status when a non-401 error response is returned", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("bad scope", { status: 422 })
    );
    await expect(apiJson("/api/practice/sessions")).rejects.toMatchObject({
      status: 422,
    });
    await expect(apiJson("/api/practice/sessions")).rejects.toBeInstanceOf(ApiError);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- api`
Expected: FAIL — at minimum the second assertion path differs, or (if `api.ts` not yet refactored) it still passes against the old duplicated `BACKEND`. The goal of this task is to lock behavior under test before refactoring; if it already passes, proceed to Step 3 and confirm it still passes after.

- [ ] **Step 3: Refactor `frontend/src/lib/api.ts` to import `BACKEND`**

Replace the file with:

```ts
import { useAuthStore } from "./auth-store";
import { BACKEND } from "./config";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { accessToken, refreshToken, setAuth, clear } = useAuthStore.getState();
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${BACKEND}${path}`, { ...init, headers, credentials: "include" });
  if (resp.status !== 401) return resp;

  if (!refreshToken) return resp;
  const r = await fetch(`${BACKEND}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    credentials: "include",
  });
  if (!r.ok) {
    clear();
    return resp;
  }
  const data = await r.json();
  setAuth(data.user, data.access_token, data.refresh_token);
  const retryHeaders = new Headers(init.headers);
  retryHeaders.set("Authorization", `Bearer ${data.access_token}`);
  if (init.body && !retryHeaders.has("Content-Type")) retryHeaders.set("Content-Type", "application/json");
  return fetch(`${BACKEND}${path}`, { ...init, headers: retryHeaders, credentials: "include" });
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await apiFetch(path, init);
  if (!resp.ok) throw new ApiError(resp.status, await resp.text());
  return resp.json() as Promise<T>;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- api`
Expected: PASS — both tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/__tests__/api.test.ts
git commit -m "refactor(frontend): import BACKEND from config in api client; lock silent-refresh under test"
```

---

### Task 7: Auth store `hydrated` flag + `useHydratedAuth`

**Files:**
- Modify: `frontend/src/lib/auth-store.ts`
- Create: `frontend/src/lib/use-hydrated-auth.ts`
- Test: `frontend/src/lib/__tests__/auth-store.test.ts`

**Interfaces:**
- Consumes: `apiJson` from `@/lib/api`.
- Produces:
  - `useAuthStore` state gains `hydrated: boolean`, `setHydrated(v: boolean): void`, `setUser(u: AuthUser): void`. `hydrate()` now restores ONLY tokens (not `hydrated`).
  - `useHydratedAuth()` hook: on mount, restores tokens, fetches `GET /api/auth/me` into `user` when a token exists but `user` is null, then sets `hydrated = true`. Returns the full auth store state. Later guards depend on `hydrated`.

- [ ] **Step 1: Write the failing test `frontend/src/lib/__tests__/auth-store.test.ts`**

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/lib/auth-store";

beforeEach(() => {
  sessionStorage.clear();
  useAuthStore.setState({ user: null, accessToken: null, refreshToken: null, hydrated: false });
});

describe("auth store", () => {
  it("starts not hydrated", () => {
    expect(useAuthStore.getState().hydrated).toBe(false);
  });

  it("setHydrated flips the flag", () => {
    useAuthStore.getState().setHydrated(true);
    expect(useAuthStore.getState().hydrated).toBe(true);
  });

  it("hydrate() restores tokens from sessionStorage but not the hydrated flag", () => {
    sessionStorage.setItem("access", "a1");
    sessionStorage.setItem("refresh", "r1");
    useAuthStore.getState().hydrate();
    expect(useAuthStore.getState().accessToken).toBe("a1");
    expect(useAuthStore.getState().refreshToken).toBe("r1");
    expect(useAuthStore.getState().hydrated).toBe(false);
  });

  it("setUser stores the user object", () => {
    const u = { id: "1", email: "x@y.z", display_name: null, roles: ["r"], perms: ["practice:read"] };
    useAuthStore.getState().setUser(u);
    expect(useAuthStore.getState().user).toEqual(u);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- auth-store`
Expected: FAIL — `hydrated`, `setHydrated`, `setUser` do not exist yet.

- [ ] **Step 3: Update `frontend/src/lib/auth-store.ts`**

```tsx
"use client";

import { create } from "zustand";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  roles: string[];
  perms: string[];
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  hydrated: boolean;
  setAuth: (user: AuthUser, access: string, refresh: string) => void;
  setUser: (user: AuthUser) => void;
  setHydrated: (v: boolean) => void;
  clear: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  hydrated: false,
  setAuth: (user, access, refresh) => {
    sessionStorage.setItem("access", access);
    sessionStorage.setItem("refresh", refresh);
    set({ user, accessToken: access, refreshToken: refresh });
  },
  setUser: (user) => set({ user }),
  setHydrated: (v) => set({ hydrated: v }),
  clear: () => {
    sessionStorage.removeItem("access");
    sessionStorage.removeItem("refresh");
    set({ user: null, accessToken: null, refreshToken: null });
  },
  hydrate: () => {
    const access = sessionStorage.getItem("access");
    const refresh = sessionStorage.getItem("refresh");
    if (access && refresh) set({ accessToken: access, refreshToken: refresh });
  },
}));
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- auth-store`
Expected: PASS — 4 tests pass.

- [ ] **Step 5: Create `frontend/src/lib/use-hydrated-auth.ts`**

```tsx
"use client";

import { useEffect } from "react";
import { useAuthStore, type AuthUser } from "./auth-store";
import { apiJson } from "./api";

/**
 * Restores auth state on first mount: rehydrates tokens from sessionStorage,
 * and when a token exists but the user object was lost (e.g. page reload),
 * refetches GET /api/auth/me. Flips `hydrated` true once resolved so route
 * guards can render instead of flashing /login.
 */
export function useHydratedAuth() {
  const hydrated = useAuthStore((s) => s.hydrated);

  useEffect(() => {
    if (hydrated) return;
    let cancelled = false;
    const init = async () => {
      const store = useAuthStore.getState();
      store.hydrate();
      const { accessToken, user } = useAuthStore.getState();
      if (accessToken && !user) {
        try {
          const me = await apiJson<AuthUser>("/api/auth/me");
          if (!cancelled) useAuthStore.getState().setUser(me);
        } catch {
          if (!cancelled) useAuthStore.getState().clear();
        }
      }
      if (!cancelled) useAuthStore.getState().setHydrated(true);
    };
    void init();
    return () => {
      cancelled = true;
    };
  }, [hydrated]);

  return useAuthStore();
}
```

- [ ] **Step 6: Verify typecheck and tests**

Run: `cd frontend && npx tsc --noEmit && npm test -- auth-store`
Expected: no type errors; tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/auth-store.ts frontend/src/lib/use-hydrated-auth.ts frontend/src/lib/__tests__/auth-store.test.ts
git commit -m "feat(frontend): add hydrated flag + useHydratedAuth (restore user via /api/auth/me)"
```

---

### Task 8: API types + query-key factory

**Files:**
- Create: `frontend/src/lib/api/types.ts`
- Create: `frontend/src/lib/api/keys.ts`

**Interfaces:**
- Produces: all TypeScript types mirroring backend schemas (listed below) and a `qk` query-key factory. Every query/mutation hook in Tasks 9–10 imports from here.

- [ ] **Step 1: Create `frontend/src/lib/api/types.ts`**

```ts
// Mirrors backend Pydantic schemas. Field names are authoritative.
export type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "scenario"
  | "ordering"
  | "drag_drop"
  | "hotspot";

export type Subset = "all" | "unpracticed" | "wrong" | "bookmarked" | "needs_review";
export type OrderMode = "random" | "sequential" | "easy_to_hard";
export type ErrorType =
  | "concept_unclear"
  | "misread_stem"
  | "memory_lapse"
  | "option_confusion"
  | "time_pressure";
export type SessionStatus = "in_progress" | "completed" | "abandoned";

export interface SessionCreateInput {
  count: number;
  subset?: Subset;
  order_mode?: OrderMode;
  domain_id?: string | null;
  book_id?: string | null;
  chapter_ids?: string[];
  question_type?: string | null;
  difficulty?: number | null;
  tag_id?: string | null;
}

export interface SessionOut {
  id: string;
  status: SessionStatus;
  total_questions: number;
  correct_count: number;
  started_at: string;
  ended_at: string | null;
  paused_at: string | null;
  config: Record<string, unknown>;
}

export interface OptionDelivery {
  id: string;
  order_index: number;
  content: string;
  content_format: "plain" | "markdown";
}

export interface PreviousAnswer {
  selected: number[];
  is_correct: boolean;
}

export interface QuestionDelivery {
  session_id: string;
  position: number;
  total: number;
  question_id: string;
  stem: string;
  question_type: QuestionType;
  options: OptionDelivery[];
  elapsed_ms: number;
  previous_answer: PreviousAnswer | null;
}

export interface AnswerInput {
  position: number;
  selected: number[];
  started_at: string;
}

export interface PerOptionExplanation {
  order_index: number;
  is_correct: boolean;
  explanation: string | null;
}

export interface AnswerResult {
  is_correct: boolean;
  correct_indexes: number[];
  selected_indexes: number[];
  correct_rationale: string | null;
  key_point_summary: string | null;
  per_option: PerOptionExplanation[];
  mapping: Record<string, unknown>;
  history: Array<Record<string, unknown>>;
}

export interface DomainBreakdown {
  domain_id: string | null;
  domain_name: string | null;
  answered: number;
  correct: number;
}

export interface WrongQuestion {
  question_id: string;
  stem: string;
  selected_indexes: number[];
  correct_indexes: number[];
}

export interface SessionSummary {
  session_id: string;
  total_questions: number;
  answered_count: number;
  correct_count: number;
  accuracy: number;
  total_time_spent_ms: number;
  domains: DomainBreakdown[];
  wrong_questions: WrongQuestion[];
}

export interface QuestionStateInput {
  is_bookmarked?: boolean;
  is_flagged_review?: boolean;
  is_mastered?: boolean;
  is_questioned?: boolean;
  note?: string | null;
  error_type?: ErrorType | null;
}

export interface QuestionState {
  is_bookmarked: boolean;
  is_flagged_review: boolean;
  is_mastered: boolean;
  is_questioned: boolean;
  note: string | null;
  error_type: ErrorType | null;
}

// Taxonomy
export interface Domain {
  id: string;
  blueprint_id: string;
  number: number;
  name: string;
  weight_pct: number;
}

export interface Book {
  id: string;
  title: string;
  edition: string | null;
  author: string | null;
  publisher: string | null;
}

export interface Chapter {
  id: string;
  book_id: string;
  order_index: number;
  title: string;
}

export interface Tag {
  id: string;
  name: string;
  description: string | null;
}
```

- [ ] **Step 2: Create `frontend/src/lib/api/keys.ts`**

```ts
export const qk = {
  domains: ["domains"] as const,
  books: ["books"] as const,
  chapters: (bookId: string) => ["books", bookId, "chapters"] as const,
  tags: ["tags"] as const,
  session: (id: string) => ["practice", "session", id] as const,
  question: (sessionId: string, position: number) =>
    ["practice", "session", sessionId, "question", position] as const,
  summary: (id: string) => ["practice", "session", id, "summary"] as const,
};
```

- [ ] **Step 3: Verify typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/lib/api/keys.ts
git commit -m "feat(frontend): add API types mirroring backend schemas + query-key factory"
```

---

### Task 9: Taxonomy query hooks

**Files:**
- Create: `frontend/src/lib/api/taxonomy.ts`

**Interfaces:**
- Consumes: `apiJson` from `@/lib/api`; `qk` from `./keys`; types from `./types`.
- Produces:
  - `useDomains(): UseQueryResult<Domain[]>`
  - `useBooks(): UseQueryResult<Book[]>`
  - `useChapters(bookId: string | null): UseQueryResult<Chapter[]>` (disabled when `bookId` is null)
  - `useTags(): UseQueryResult<Tag[]>`

- [ ] **Step 1: Create `frontend/src/lib/api/taxonomy.ts`**

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type { Domain, Book, Chapter, Tag } from "./types";

export function useDomains() {
  return useQuery({
    queryKey: qk.domains,
    queryFn: () => apiJson<Domain[]>("/api/domains"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useBooks() {
  return useQuery({
    queryKey: qk.books,
    queryFn: () => apiJson<Book[]>("/api/books"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useChapters(bookId: string | null) {
  return useQuery({
    queryKey: bookId ? qk.chapters(bookId) : ["books", "none", "chapters"],
    queryFn: () => apiJson<Chapter[]>(`/api/books/${bookId}/chapters`),
    enabled: !!bookId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useTags() {
  return useQuery({
    queryKey: qk.tags,
    queryFn: () => apiJson<Tag[]>("/api/tags"),
    staleTime: 5 * 60 * 1000,
  });
}
```

- [ ] **Step 2: Verify typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api/taxonomy.ts
git commit -m "feat(frontend): add taxonomy query hooks (domains, books, chapters, tags)"
```

---

### Task 10: Practice query + mutation hooks

**Files:**
- Create: `frontend/src/lib/api/practice.ts`

**Interfaces:**
- Consumes: `apiJson` from `@/lib/api`; `qk` from `./keys`; `useQueryClient`/`useQuery`/`useMutation` from `@tanstack/react-query`; types from `./types`.
- Produces:
  - `useSession(id: string): UseQueryResult<SessionOut>`
  - `useQuestion(sessionId: string, position: number): UseQueryResult<QuestionDelivery>`
  - `useSessionSummary(id: string, enabled?: boolean): UseQueryResult<SessionSummary>`
  - `useCreateSession(): UseMutationResult<SessionOut, unknown, SessionCreateInput>`
  - `useSubmitAnswer(sessionId: string): UseMutationResult<AnswerResult, unknown, AnswerInput>`
  - `usePauseSession(sessionId: string)` / `useResumeSession(sessionId: string)`: `UseMutationResult<SessionOut, unknown, void>`
  - `useFinishSession(sessionId: string): UseMutationResult<SessionSummary, unknown, void>`
  - `useUpdateQuestionState(): UseMutationResult<QuestionState, unknown, { questionId: string; body: QuestionStateInput }>`

- [ ] **Step 1: Create `frontend/src/lib/api/practice.ts`**

```ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiJson } from "@/lib/api";
import { qk } from "./keys";
import type {
  SessionOut,
  SessionCreateInput,
  QuestionDelivery,
  AnswerInput,
  AnswerResult,
  SessionSummary,
  QuestionStateInput,
  QuestionState,
} from "./types";

export function useSession(id: string) {
  return useQuery({
    queryKey: qk.session(id),
    queryFn: () => apiJson<SessionOut>(`/api/practice/sessions/${id}`),
  });
}

export function useQuestion(sessionId: string, position: number) {
  return useQuery({
    queryKey: qk.question(sessionId, position),
    queryFn: () =>
      apiJson<QuestionDelivery>(`/api/practice/sessions/${sessionId}/questions/${position}`),
  });
}

export function useSessionSummary(id: string, enabled = true) {
  return useQuery({
    queryKey: qk.summary(id),
    queryFn: () => apiJson<SessionSummary>(`/api/practice/sessions/${id}/summary`),
    enabled,
  });
}

export function useCreateSession() {
  return useMutation({
    mutationFn: (body: SessionCreateInput) =>
      apiJson<SessionOut>("/api/practice/sessions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

export function useSubmitAnswer(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AnswerInput) =>
      apiJson<AnswerResult>(`/api/practice/sessions/${sessionId}/answers`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.session(sessionId) });
    },
  });
}

export function usePauseSession(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<SessionOut>(`/api/practice/sessions/${sessionId}/pause`, { method: "POST" }),
    onSuccess: (data) => qc.setQueryData(qk.session(sessionId), data),
  });
}

export function useResumeSession(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<SessionOut>(`/api/practice/sessions/${sessionId}/resume`, { method: "POST" }),
    onSuccess: (data) => qc.setQueryData(qk.session(sessionId), data),
  });
}

export function useFinishSession(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiJson<SessionSummary>(`/api/practice/sessions/${sessionId}/finish`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.session(sessionId) });
      qc.invalidateQueries({ queryKey: qk.summary(sessionId) });
    },
  });
}

export function useUpdateQuestionState() {
  return useMutation({
    mutationFn: ({ questionId, body }: { questionId: string; body: QuestionStateInput }) =>
      apiJson<QuestionState>(`/api/practice/questions/${questionId}/state`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
  });
}
```

- [ ] **Step 2: Verify typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api/practice.ts
git commit -m "feat(frontend): add practice query + mutation hooks with query-key invalidation"
```

---

### Task 11: Providers (QueryClient + Toaster) wired into root layout

**Files:**
- Create: `frontend/src/components/providers.tsx`
- Modify: `frontend/src/app/layout.tsx`

**Interfaces:**
- Consumes: `QueryClient`/`QueryClientProvider` from `@tanstack/react-query`; `Toaster` from `@/components/ui/sonner`.
- Produces: `<Providers>` client boundary wrapping the app with a singleton `QueryClient` and a global toast outlet.

- [ ] **Step 1: Create `frontend/src/components/providers.tsx`**

```tsx
"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false },
        },
      })
  );
  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster />
    </QueryClientProvider>
  );
}
```

- [ ] **Step 2: Update `frontend/src/app/layout.tsx` to wrap children**

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

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
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/providers.tsx frontend/src/app/layout.tsx
git commit -m "feat(frontend): add TanStack Query + Toaster providers in root layout"
```

---

### Task 12: Shared layout patterns

**Files:**
- Create: `frontend/src/components/page-header.tsx`, `loading.tsx`, `empty-state.tsx`, `error-state.tsx`

**Interfaces:**
- Produces:
  - `<PageHeader title: string; description?: string; crumbs?: string[]; actions?: ReactNode />`
  - `<Loading label?: string />` (skeleton block)
  - `<EmptyState title: string; description?: string; action?: ReactNode />`
  - `<ErrorState title?: string; message: string; onRetry?: () => void />`

- [ ] **Step 1: Create `frontend/src/components/page-header.tsx`**

```tsx
import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  crumbs,
  actions,
}: {
  title: string;
  description?: string;
  crumbs?: string[];
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        {crumbs && crumbs.length > 0 && (
          <nav className="mb-1 text-sm text-muted-foreground">{crumbs.join(" / ")}</nav>
        )}
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/loading.tsx`**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export function Loading({ label }: { label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-busy="true">
      {label && <p className="text-sm text-muted-foreground">{label}</p>}
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/empty-state.tsx`**

```tsx
import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-10 text-center">
      <h3 className="text-base font-medium">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/error-state.tsx`**

```tsx
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
      {onRetry && (
        <div className="mt-3">
          <Button variant="outline" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </Alert>
  );
}
```

- [ ] **Step 5: Verify typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/page-header.tsx frontend/src/components/loading.tsx frontend/src/components/empty-state.tsx frontend/src/components/error-state.tsx
git commit -m "feat(frontend): add shared layout patterns (PageHeader, Loading, EmptyState, ErrorState)"
```

---

### Task 13: Route guards (`RequireAuth`, `RequirePermission`)

**Files:**
- Create: `frontend/src/components/require-auth.tsx`
- Create: `frontend/src/components/require-permission.tsx`
- Test: `frontend/src/components/__tests__/require-permission.test.tsx`

**Interfaces:**
- Consumes: `useHydratedAuth` from `@/lib/use-hydrated-auth`; `useAuthStore` from `@/lib/auth-store`; `useRouter`/`usePathname` from `next/navigation`; `<Loading>`.
- Produces:
  - `<RequireAuth>{children}</RequireAuth>` — renders `<Loading>` until `hydrated`; if unauthed after hydration, redirects to `/login?next=<path>`; otherwise renders children.
  - `<RequirePermission perm="..." fallback?={ReactNode}>{children}</RequirePermission>` — renders children only when `user.perms` includes `perm`; else renders `fallback` (default `null`).

- [ ] **Step 1: Write the failing test `frontend/src/components/__tests__/require-permission.test.tsx`**

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { RequirePermission } from "@/components/require-permission";
import { useAuthStore } from "@/lib/auth-store";

beforeEach(() => {
  useAuthStore.setState({
    user: { id: "1", email: "a@b.c", display_name: null, roles: [], perms: ["practice:read"] },
    accessToken: "t",
    refreshToken: "r",
    hydrated: true,
  });
});

describe("RequirePermission", () => {
  it("renders children when the perm is present", () => {
    render(
      <RequirePermission perm="practice:read">
        <span>visible</span>
      </RequirePermission>
    );
    expect(screen.getByText("visible")).toBeInTheDocument();
  });

  it("renders fallback when the perm is absent", () => {
    render(
      <RequirePermission perm="admin:manage_users" fallback={<span>denied</span>}>
        <span>secret</span>
      </RequirePermission>
    );
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(screen.getByText("denied")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- require-permission`
Expected: FAIL — `@/components/require-permission` does not exist.

- [ ] **Step 3: Create `frontend/src/components/require-permission.tsx`**

```tsx
"use client";

import type { ReactNode } from "react";
import { useAuthStore } from "@/lib/auth-store";

export function RequirePermission({
  perm,
  fallback = null,
  children,
}: {
  perm: string;
  fallback?: ReactNode;
  children: ReactNode;
}) {
  const perms = useAuthStore((s) => s.user?.perms ?? []);
  if (!perms.includes(perm)) return <>{fallback}</>;
  return <>{children}</>;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- require-permission`
Expected: PASS — 2 tests pass.

- [ ] **Step 5: Create `frontend/src/components/require-auth.tsx`**

```tsx
"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useHydratedAuth } from "@/lib/use-hydrated-auth";
import { Loading } from "@/components/loading";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { hydrated, accessToken } = useHydratedAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (hydrated && !accessToken) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [hydrated, accessToken, router, pathname]);

  if (!hydrated || !accessToken) {
    return (
      <div className="p-8">
        <Loading label="Loading…" />
      </div>
    );
  }
  return <>{children}</>;
}
```

- [ ] **Step 6: Verify typecheck and tests**

Run: `cd frontend && npx tsc --noEmit && npm test -- require-permission`
Expected: no type errors; tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/require-auth.tsx frontend/src/components/require-permission.tsx frontend/src/components/__tests__/require-permission.test.tsx
git commit -m "feat(frontend): add RequireAuth and RequirePermission route guards"
```

---

### Task 14: App sidebar + `(app)` layout shell

**Files:**
- Create: `frontend/src/components/app-sidebar.tsx`
- Create: `frontend/src/app/(app)/layout.tsx`

**Interfaces:**
- Consumes: `RequireAuth`; `RequirePermission`; `useAuthStore`; `usePathname` from `next/navigation`; `next/link`; `lucide-react` icons; `Button`.
- Produces: a persistent left sidebar (Practice active link; Exam/Analytics disabled "coming soon"; Admin link rendered only when the user holds an `admin:*` perm; user identity + logout at the bottom) and the protected `(app)` route-group layout that wraps every app page in `<RequireAuth>` + the sidebar chrome.

- [ ] **Step 1: Create `frontend/src/components/app-sidebar.tsx`**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, GraduationCap, BarChart3, Shield, LogOut } from "lucide-react";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const NAV = [
  { href: "/practice", label: "Practice", icon: BookOpen, enabled: true },
  { href: "/exam", label: "Exam", icon: GraduationCap, enabled: false },
  { href: "/analytics", label: "Analytics", icon: BarChart3, enabled: false },
];

export function AppSidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const perms = user?.perms ?? [];
  const isAdmin = perms.some((p) => p.startsWith("admin:"));

  async function logout() {
    const { refreshToken, clear } = useAuthStore.getState();
    if (refreshToken) {
      await fetch(`${BACKEND}/api/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {});
    }
    clear();
    window.location.href = "/login";
  }

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r bg-card">
      <div className="px-5 py-4 text-lg font-semibold tracking-tight">CISSP Practice</div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ href, label, icon: Icon, enabled }) => {
          const active = pathname.startsWith(href);
          if (!enabled) {
            return (
              <span
                key={href}
                className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground/60"
                title="Coming soon"
              >
                <Icon className="h-4 w-4" />
                {label}
                <span className="ml-auto text-xs">Soon</span>
              </span>
            );
          }
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-primary text-primary-foreground" : "hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
        {isAdmin && (
          <Link
            href="/admin"
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              pathname.startsWith("/admin")
                ? "bg-primary text-primary-foreground"
                : "hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Shield className="h-4 w-4" />
            Admin
          </Link>
        )}
      </nav>
      <div className="border-t p-3">
        <div className="mb-2 px-2 text-sm">
          <div className="truncate font-medium">{user?.display_name || user?.email}</div>
          <div className="truncate text-xs text-muted-foreground">{user?.email}</div>
        </div>
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={logout}>
          <LogOut className="h-4 w-4" />
          Log out
        </Button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Create `frontend/src/app/(app)/layout.tsx`**

```tsx
import { RequireAuth } from "@/components/require-auth";
import { AppSidebar } from "@/components/app-sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <div className="flex min-h-screen">
        <AppSidebar />
        <main className="flex-1 overflow-y-auto px-8 py-6">{children}</main>
      </div>
    </RequireAuth>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds. (No page in `(app)` yet besides nothing — Next allows an empty group layout; if the build complains about no page, proceed to Task 16 which adds `/practice`, then re-run. For now `npx tsc --noEmit` is the gate.)

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/components/app-sidebar.tsx" "frontend/src/app/(app)/layout.tsx"
git commit -m "feat(frontend): add left-sidebar app shell + protected (app) layout"
```

---

### Task 15: Login `?next=` redirect + home redirect

**Files:**
- Modify: `frontend/src/app/(auth)/login/page.tsx`
- Modify: `frontend/src/app/page.tsx`

**Interfaces:**
- Consumes: `useSearchParams`/`useRouter` from `next/navigation`; `useHydratedAuth`; `BACKEND` from `@/lib/config`; `useAuthStore`.
- Produces: login routes to the `?next=` path (default `/practice`) after success; `/` redirects authed users to `/practice` and unauthed users to `/login`.

- [ ] **Step 1: Replace `frontend/src/app/(auth)/login/page.tsx`**

```tsx
"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/lib/auth-store";
import { BACKEND } from "@/lib/config";

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
    <main className="mx-auto max-w-sm p-8">
      <h1 className="mb-4 text-2xl font-bold">Log in</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input
          type="email"
          placeholder="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded border p-2"
          required
        />
        <input
          type="password"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded border p-2"
          required
        />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-primary p-2 text-primary-foreground disabled:opacity-50"
        >
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <button
        type="button"
        disabled={busy}
        onClick={() => void loginWith({ email: DEV_ADMIN_EMAIL, password: DEV_ADMIN_PASSWORD })}
        className="mt-3 w-full rounded border border-dashed border-gray-400 p-2 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        title={`Logs in as ${DEV_ADMIN_EMAIL} / ${DEV_ADMIN_PASSWORD}`}
      >
        Dev login (admin / admin)
      </button>
      <p className="mt-4 text-sm">
        No account?{" "}
        <a href="/register" className="text-primary underline">
          Register
        </a>
      </p>
    </main>
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

- [ ] **Step 2: Replace `frontend/src/app/page.tsx` with a redirect**

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useHydratedAuth } from "@/lib/use-hydrated-auth";
import { Loading } from "@/components/loading";

export default function Home() {
  const { hydrated, accessToken } = useHydratedAuth();
  const router = useRouter();

  useEffect(() => {
    if (!hydrated) return;
    router.replace(accessToken ? "/practice" : "/login");
  }, [hydrated, accessToken, router]);

  return (
    <div className="p-8">
      <Loading label="Loading…" />
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds (login uses `useSearchParams` inside `<Suspense>`, satisfying Next's CSR-bailout rule).

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/(auth)/login/page.tsx" frontend/src/app/page.tsx
git commit -m "feat(frontend): login ?next= redirect + home route redirect to /practice"
```

---

### Task 16: Runner state machine (pure)

**Files:**
- Create: `frontend/src/features/practice/runner-machine.ts`
- Test: `frontend/src/features/practice/__tests__/runner-machine.test.ts`

**Interfaces:**
- Consumes: `QuestionType`, `PreviousAnswer`, `AnswerResult` from `@/lib/api/types`.
- Produces:
  - `type RunnerPhase = "selecting" | "submitted"`
  - `interface RunnerState { phase: RunnerPhase; selected: number[]; result: AnswerResult | null }`
  - `initialRunnerState(previous?: PreviousAnswer | null): RunnerState`
  - `toggleSelection(state: RunnerState, orderIndex: number, questionType: QuestionType): RunnerState`
  - `canSubmit(state: RunnerState): boolean`
  - `markSubmitted(state: RunnerState, result: AnswerResult): RunnerState`

- [ ] **Step 1: Write the failing test `frontend/src/features/practice/__tests__/runner-machine.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import {
  initialRunnerState,
  toggleSelection,
  canSubmit,
  markSubmitted,
} from "@/features/practice/runner-machine";
import type { AnswerResult } from "@/lib/api/types";

const result: AnswerResult = {
  is_correct: true,
  correct_indexes: [0],
  selected_indexes: [0],
  correct_rationale: "because",
  key_point_summary: null,
  per_option: [],
  mapping: {},
  history: [],
};

describe("runner machine", () => {
  it("fresh question starts selecting with no selection", () => {
    const s = initialRunnerState(null);
    expect(s.phase).toBe("selecting");
    expect(s.selected).toEqual([]);
    expect(canSubmit(s)).toBe(false);
  });

  it("rehydrates an already-answered question as submitted with its prior selection", () => {
    const s = initialRunnerState({ selected: [2], is_correct: false });
    expect(s.phase).toBe("submitted");
    expect(s.selected).toEqual([2]);
    expect(canSubmit(s)).toBe(false);
  });

  it("single_choice selection replaces the prior choice", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 1, "single_choice");
    s = toggleSelection(s, 3, "single_choice");
    expect(s.selected).toEqual([3]);
    expect(canSubmit(s)).toBe(true);
  });

  it("true_false selection replaces the prior choice", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 0, "true_false");
    s = toggleSelection(s, 1, "true_false");
    expect(s.selected).toEqual([1]);
  });

  it("multiple_choice toggles selections in and out, kept sorted", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 2, "multiple_choice");
    s = toggleSelection(s, 0, "multiple_choice");
    expect(s.selected).toEqual([0, 2]);
    s = toggleSelection(s, 2, "multiple_choice");
    expect(s.selected).toEqual([0]);
  });

  it("cannot toggle after submitting", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 1, "single_choice");
    s = markSubmitted(s, result);
    const after = toggleSelection(s, 2, "single_choice");
    expect(after.selected).toEqual([1]);
    expect(after.phase).toBe("submitted");
  });

  it("markSubmitted captures the result and locks the phase", () => {
    let s = initialRunnerState(null);
    s = toggleSelection(s, 0, "single_choice");
    s = markSubmitted(s, result);
    expect(s.phase).toBe("submitted");
    expect(s.result).toBe(result);
    expect(canSubmit(s)).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- runner-machine`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/src/features/practice/runner-machine.ts`**

```ts
import type { QuestionType, PreviousAnswer, AnswerResult } from "@/lib/api/types";

export type RunnerPhase = "selecting" | "submitted";

export interface RunnerState {
  phase: RunnerPhase;
  selected: number[];
  result: AnswerResult | null;
}

export function initialRunnerState(previous?: PreviousAnswer | null): RunnerState {
  if (previous) {
    return { phase: "submitted", selected: [...previous.selected], result: null };
  }
  return { phase: "selecting", selected: [], result: null };
}

export function toggleSelection(
  state: RunnerState,
  orderIndex: number,
  questionType: QuestionType
): RunnerState {
  if (state.phase !== "selecting") return state;
  if (questionType === "multiple_choice") {
    const has = state.selected.includes(orderIndex);
    const selected = has
      ? state.selected.filter((i) => i !== orderIndex)
      : [...state.selected, orderIndex].sort((a, b) => a - b);
    return { ...state, selected };
  }
  // single_choice, true_false, and any single-answer type: replace
  return { ...state, selected: [orderIndex] };
}

export function canSubmit(state: RunnerState): boolean {
  return state.phase === "selecting" && state.selected.length > 0;
}

export function markSubmitted(state: RunnerState, result: AnswerResult): RunnerState {
  return { phase: "submitted", selected: state.selected, result };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- runner-machine`
Expected: PASS — 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/practice/runner-machine.ts frontend/src/features/practice/__tests__/runner-machine.test.ts
git commit -m "feat(practice): add pure runner selection/submit state machine"
```

---

### Task 17: Session tracker (localStorage)

**Files:**
- Create: `frontend/src/features/practice/session-tracker.ts`
- Test: `frontend/src/features/practice/__tests__/session-tracker.test.ts`

**Interfaces:**
- Produces:
  - `trackSession(id: string): void` — records a newly created session id (most-recent-first, deduped).
  - `untrackSession(id: string): void` — removes an id (e.g. on finish).
  - `getTrackedSessionIds(): string[]` — returns tracked ids, most-recent-first; `[]` when none or on parse failure.
- Storage key: `"practice:active-sessions"`. SSR-safe (no-ops when `window` is undefined).

- [ ] **Step 1: Write the failing test `frontend/src/features/practice/__tests__/session-tracker.test.ts`**

```ts
import { describe, it, expect, beforeEach } from "vitest";
import {
  trackSession,
  untrackSession,
  getTrackedSessionIds,
} from "@/features/practice/session-tracker";

beforeEach(() => {
  localStorage.clear();
});

describe("session tracker", () => {
  it("returns empty when nothing tracked", () => {
    expect(getTrackedSessionIds()).toEqual([]);
  });

  it("tracks ids most-recent-first and dedupes", () => {
    trackSession("a");
    trackSession("b");
    trackSession("a");
    expect(getTrackedSessionIds()).toEqual(["a", "b"]);
  });

  it("untracks an id", () => {
    trackSession("a");
    trackSession("b");
    untrackSession("a");
    expect(getTrackedSessionIds()).toEqual(["b"]);
  });

  it("recovers from corrupt storage", () => {
    localStorage.setItem("practice:active-sessions", "not-json");
    expect(getTrackedSessionIds()).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- session-tracker`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/src/features/practice/session-tracker.ts`**

```ts
const KEY = "practice:active-sessions";

function read(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function write(ids: string[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(ids));
}

export function trackSession(id: string): void {
  const ids = read().filter((x) => x !== id);
  write([id, ...ids]);
}

export function untrackSession(id: string): void {
  write(read().filter((x) => x !== id));
}

export function getTrackedSessionIds(): string[] {
  return read();
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- session-tracker`
Expected: PASS — 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/practice/session-tracker.ts frontend/src/features/practice/__tests__/session-tracker.test.ts
git commit -m "feat(practice): add localStorage active-session tracker for Resume"
```

---

### Task 18: Session payload builder (pure)

**Files:**
- Create: `frontend/src/features/practice/session-payload.ts`
- Test: `frontend/src/features/practice/__tests__/session-payload.test.ts`

**Interfaces:**
- Consumes: `Subset`, `OrderMode`, `SessionCreateInput` from `@/lib/api/types`.
- Produces:
  - `interface SessionFormState { count: number; subset: Subset; orderMode: OrderMode; domainId: string | null; bookId: string | null; chapterIds: string[]; questionType: string | null; difficulty: number | null; tagId: string | null }`
  - `defaultSessionFormState: SessionFormState`
  - `buildSessionPayload(f: SessionFormState): SessionCreateInput` — always includes `count`, `subset`, `order_mode`; includes optional scope fields only when set (non-null / non-empty).

- [ ] **Step 1: Write the failing test `frontend/src/features/practice/__tests__/session-payload.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import {
  buildSessionPayload,
  defaultSessionFormState,
  type SessionFormState,
} from "@/features/practice/session-payload";

describe("buildSessionPayload", () => {
  it("emits only count/subset/order_mode when nothing else is set", () => {
    const payload = buildSessionPayload({ ...defaultSessionFormState, count: 10 });
    expect(payload).toEqual({ count: 10, subset: "all", order_mode: "random" });
  });

  it("includes scope fields only when present, using backend field names", () => {
    const form: SessionFormState = {
      count: 25,
      subset: "wrong",
      orderMode: "easy_to_hard",
      domainId: "d1",
      bookId: "b1",
      chapterIds: ["c1", "c2"],
      questionType: "single_choice",
      difficulty: 3,
      tagId: "t1",
    };
    expect(buildSessionPayload(form)).toEqual({
      count: 25,
      subset: "wrong",
      order_mode: "easy_to_hard",
      domain_id: "d1",
      book_id: "b1",
      chapter_ids: ["c1", "c2"],
      question_type: "single_choice",
      difficulty: 3,
      tag_id: "t1",
    });
  });

  it("omits empty chapter_ids and null difficulty", () => {
    const payload = buildSessionPayload({
      ...defaultSessionFormState,
      count: 5,
      domainId: "d1",
      chapterIds: [],
      difficulty: null,
    });
    expect(payload).toEqual({ count: 5, subset: "all", order_mode: "random", domain_id: "d1" });
    expect(payload).not.toHaveProperty("chapter_ids");
    expect(payload).not.toHaveProperty("difficulty");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- session-payload`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/src/features/practice/session-payload.ts`**

```ts
import type { Subset, OrderMode, SessionCreateInput } from "@/lib/api/types";

export interface SessionFormState {
  count: number;
  subset: Subset;
  orderMode: OrderMode;
  domainId: string | null;
  bookId: string | null;
  chapterIds: string[];
  questionType: string | null;
  difficulty: number | null;
  tagId: string | null;
}

export const defaultSessionFormState: SessionFormState = {
  count: 10,
  subset: "all",
  orderMode: "random",
  domainId: null,
  bookId: null,
  chapterIds: [],
  questionType: null,
  difficulty: null,
  tagId: null,
};

export function buildSessionPayload(f: SessionFormState): SessionCreateInput {
  const payload: SessionCreateInput = {
    count: f.count,
    subset: f.subset,
    order_mode: f.orderMode,
  };
  if (f.domainId) payload.domain_id = f.domainId;
  if (f.bookId) payload.book_id = f.bookId;
  if (f.chapterIds.length > 0) payload.chapter_ids = f.chapterIds;
  if (f.questionType) payload.question_type = f.questionType;
  if (f.difficulty != null) payload.difficulty = f.difficulty;
  if (f.tagId) payload.tag_id = f.tagId;
  return payload;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- session-payload`
Expected: PASS — 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/practice/session-payload.ts frontend/src/features/practice/__tests__/session-payload.test.ts
git commit -m "feat(practice): add pure session payload builder with backend field names"
```

---

### Task 19: OptionList component

**Files:**
- Create: `frontend/src/features/practice/option-list.tsx`
- Test: `frontend/src/features/practice/__tests__/option-list.test.tsx`

**Interfaces:**
- Consumes: `RadioGroup`/`RadioGroupItem`, `Checkbox`, `cn`; `OptionDelivery`, `QuestionType`, `AnswerResult` from `@/lib/api/types`.
- Produces: `<OptionList questionType options selected onToggle disabled? result? />` — renders radios for single-answer types (`single_choice`, `true_false`, and any non-`multiple_choice` type) and checkboxes for `multiple_choice`; after a `result` is supplied, colors correct options success and wrongly-selected options destructive.

- [ ] **Step 1: Write the failing test `frontend/src/features/practice/__tests__/option-list.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OptionList } from "@/features/practice/option-list";
import type { OptionDelivery } from "@/lib/api/types";

const options: OptionDelivery[] = [
  { id: "o0", order_index: 0, content: "Alpha", content_format: "plain" },
  { id: "o1", order_index: 1, content: "Bravo", content_format: "plain" },
  { id: "o2", order_index: 2, content: "Charlie", content_format: "plain" },
];

describe("OptionList", () => {
  it("renders single_choice options as radios with their content", () => {
    render(
      <OptionList questionType="single_choice" options={options} selected={[]} onToggle={() => {}} />
    );
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
  });

  it("renders multiple_choice options as checkboxes", () => {
    render(
      <OptionList questionType="multiple_choice" options={options} selected={[]} onToggle={() => {}} />
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("renders true_false options as radios", () => {
    const tf: OptionDelivery[] = [
      { id: "t", order_index: 0, content: "True", content_format: "plain" },
      { id: "f", order_index: 1, content: "False", content_format: "plain" },
    ];
    render(<OptionList questionType="true_false" options={tf} selected={[]} onToggle={() => {}} />);
    expect(screen.getAllByRole("radio")).toHaveLength(2);
  });

  it("calls onToggle with the option order_index when a radio is clicked", async () => {
    const onToggle = vi.fn();
    render(
      <OptionList questionType="single_choice" options={options} selected={[]} onToggle={onToggle} />
    );
    await userEvent.click(screen.getAllByRole("radio")[1]);
    expect(onToggle).toHaveBeenCalledWith(1);
  });

  it("calls onToggle when a checkbox is clicked", async () => {
    const onToggle = vi.fn();
    render(
      <OptionList questionType="multiple_choice" options={options} selected={[0]} onToggle={onToggle} />
    );
    await userEvent.click(screen.getAllByRole("checkbox")[2]);
    expect(onToggle).toHaveBeenCalledWith(2);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- option-list`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/src/features/practice/option-list.tsx`**

```tsx
"use client";

import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { OptionDelivery, QuestionType, AnswerResult } from "@/lib/api/types";

export function OptionList({
  questionType,
  options,
  selected,
  onToggle,
  disabled = false,
  result = null,
}: {
  questionType: QuestionType;
  options: OptionDelivery[];
  selected: number[];
  onToggle: (orderIndex: number) => void;
  disabled?: boolean;
  result?: AnswerResult | null;
}) {
  const isMulti = questionType === "multiple_choice";
  const correct = new Set(result?.correct_indexes ?? []);

  function rowClass(orderIndex: number): string {
    if (!result) {
      return selected.includes(orderIndex) ? "border-primary" : "border-border";
    }
    if (correct.has(orderIndex)) return "border-success bg-success/10";
    if (selected.includes(orderIndex)) return "border-destructive bg-destructive/10";
    return "border-border";
  }

  if (isMulti) {
    return (
      <div className="space-y-2">
        {options.map((o) => (
          <label
            key={o.order_index}
            className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3", rowClass(o.order_index))}
          >
            <Checkbox
              checked={selected.includes(o.order_index)}
              disabled={disabled}
              onCheckedChange={() => onToggle(o.order_index)}
            />
            <span className="text-sm">{o.content}</span>
          </label>
        ))}
      </div>
    );
  }

  return (
    <RadioGroup
      value={selected[0] != null ? String(selected[0]) : undefined}
      disabled={disabled}
      onValueChange={(v) => onToggle(Number(v))}
      className="space-y-2"
    >
      {options.map((o) => (
        <label
          key={o.order_index}
          className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3", rowClass(o.order_index))}
        >
          <RadioGroupItem value={String(o.order_index)} />
          <span className="text-sm">{o.content}</span>
        </label>
      ))}
    </RadioGroup>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- option-list`
Expected: PASS — 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/practice/option-list.tsx frontend/src/features/practice/__tests__/option-list.test.tsx
git commit -m "feat(practice): add OptionList rendering single/multi/true-false uniformly"
```

---

### Task 20: Create-session form

**Files:**
- Create: `frontend/src/features/practice/create-session-form.tsx`
- Test: `frontend/src/features/practice/__tests__/create-session-form.test.tsx`

**Interfaces:**
- Consumes: `useDomains`/`useBooks`/`useChapters`/`useTags`; `useCreateSession`; `buildSessionPayload`/`defaultSessionFormState`/`SessionFormState`; `trackSession`; `toast`; `ApiError`; `useRouter`; UI primitives (`Card`, `Input`, `Label`, `Select`, `Button`).
- Produces: `<CreateSessionForm />` — full filter form. On Start, builds the payload, creates the session, tracks the id in localStorage, routes to the runner. No knowledge-point dropdown (backend has no KP filter).

- [ ] **Step 1: Write the failing test `frontend/src/features/practice/__tests__/create-session-form.test.tsx`**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mutate = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/taxonomy", () => ({
  useDomains: () => ({ data: [], isLoading: false }),
  useBooks: () => ({ data: [], isLoading: false }),
  useChapters: () => ({ data: [], isLoading: false }),
  useTags: () => ({ data: [], isLoading: false }),
}));
vi.mock("@/lib/api/practice", () => ({
  useCreateSession: () => ({ mutate, isPending: false }),
}));

import { CreateSessionForm } from "@/features/practice/create-session-form";

beforeEach(() => {
  mutate.mockReset();
  push.mockReset();
});

describe("CreateSessionForm", () => {
  it("submits count + defaults using backend field names", async () => {
    render(<CreateSessionForm />);
    const count = screen.getByLabelText(/number of questions/i);
    await userEvent.clear(count);
    await userEvent.type(count, "15");
    await userEvent.click(screen.getByRole("button", { name: /start practice/i }));

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toEqual({ count: 15, subset: "all", order_mode: "random" });
  });

  it("disables Start when count is below 1", async () => {
    render(<CreateSessionForm />);
    const count = screen.getByLabelText(/number of questions/i);
    await userEvent.clear(count);
    await userEvent.type(count, "0");
    expect(screen.getByRole("button", { name: /start practice/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- create-session-form`
Expected: FAIL — module not found.

- [ ] **Step 3: Create `frontend/src/features/practice/create-session-form.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDomains, useBooks, useChapters, useTags } from "@/lib/api/taxonomy";
import { useCreateSession } from "@/lib/api/practice";
import { ApiError } from "@/lib/api";
import {
  buildSessionPayload,
  defaultSessionFormState,
  type SessionFormState,
} from "./session-payload";
import { trackSession } from "./session-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import type { Subset, OrderMode, QuestionType } from "@/lib/api/types";

const ANY = "__any__";
const SUBSETS: Subset[] = ["all", "unpracticed", "wrong", "bookmarked", "needs_review"];
const ORDERS: OrderMode[] = ["random", "sequential", "easy_to_hard"];
const TYPES: QuestionType[] = [
  "single_choice",
  "multiple_choice",
  "true_false",
  "scenario",
  "ordering",
  "drag_drop",
  "hotspot",
];

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CreateSessionForm() {
  const router = useRouter();
  const [form, setForm] = useState<SessionFormState>(defaultSessionFormState);
  const domains = useDomains();
  const books = useBooks();
  const chapters = useChapters(form.bookId);
  const tags = useTags();
  const create = useCreateSession();

  function set<K extends keyof SessionFormState>(key: K, value: SessionFormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function start() {
    const payload = buildSessionPayload(form);
    create.mutate(payload, {
      onSuccess: (session) => {
        trackSession(session.id);
        router.push(`/practice/sessions/${session.id}`);
      },
      onError: (e) => {
        const msg =
          e instanceof ApiError && e.status === 422
            ? "No questions match the selected filters."
            : "Could not start the session. Please try again.";
        toast.error(msg);
      },
    });
  }

  const countValid = Number.isFinite(form.count) && form.count >= 1 && form.count <= 200;

  return (
    <Card>
      <CardHeader>
        <CardTitle>New practice session</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="count">Number of questions</Label>
          <Input
            id="count"
            type="number"
            min={1}
            max={200}
            value={Number.isNaN(form.count) ? "" : form.count}
            onChange={(e) => set("count", e.target.value === "" ? NaN : Number(e.target.value))}
          />
        </div>

        <div className="space-y-2">
          <Label>Subset</Label>
          <Select value={form.subset} onValueChange={(v) => set("subset", v as Subset)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SUBSETS.map((s) => (
                <SelectItem key={s} value={s}>
                  {labelize(s)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Order</Label>
          <Select value={form.orderMode} onValueChange={(v) => set("orderMode", v as OrderMode)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ORDERS.map((o) => (
                <SelectItem key={o} value={o}>
                  {labelize(o)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Domain</Label>
          <Select
            value={form.domainId ?? ANY}
            onValueChange={(v) => set("domainId", v === ANY ? null : v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Any domain" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any domain</SelectItem>
              {(domains.data ?? []).map((d) => (
                <SelectItem key={d.id} value={d.id}>
                  {d.number}. {d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Book</Label>
          <Select
            value={form.bookId ?? ANY}
            onValueChange={(v) =>
              setForm((f) => ({ ...f, bookId: v === ANY ? null : v, chapterIds: [] }))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Any book" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any book</SelectItem>
              {(books.data ?? []).map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Chapter</Label>
          <Select
            value={form.chapterIds[0] ?? ANY}
            disabled={!form.bookId}
            onValueChange={(v) => set("chapterIds", v === ANY ? [] : [v])}
          >
            <SelectTrigger>
              <SelectValue placeholder={form.bookId ? "Any chapter" : "Select a book first"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any chapter</SelectItem>
              {(chapters.data ?? []).map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.order_index}. {c.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Question type</Label>
          <Select
            value={form.questionType ?? ANY}
            onValueChange={(v) => set("questionType", v === ANY ? null : v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Any type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any type</SelectItem>
              {TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {labelize(t)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Difficulty</Label>
          <Select
            value={form.difficulty != null ? String(form.difficulty) : ANY}
            onValueChange={(v) => set("difficulty", v === ANY ? null : Number(v))}
          >
            <SelectTrigger>
              <SelectValue placeholder="Any difficulty" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any difficulty</SelectItem>
              {[1, 2, 3, 4, 5].map((d) => (
                <SelectItem key={d} value={String(d)}>
                  Level {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Tag</Label>
          <Select value={form.tagId ?? ANY} onValueChange={(v) => set("tagId", v === ANY ? null : v)}>
            <SelectTrigger>
              <SelectValue placeholder="Any tag" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any tag</SelectItem>
              {(tags.data ?? []).map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="md:col-span-2">
          <Button onClick={start} disabled={!countValid || create.isPending} className="w-full md:w-auto">
            {create.isPending ? "Starting…" : "Start practice"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- create-session-form`
Expected: PASS — 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/practice/create-session-form.tsx frontend/src/features/practice/__tests__/create-session-form.test.tsx
git commit -m "feat(practice): add full create-session filter form"
```

---

### Task 21: Resume panel

**Files:**
- Create: `frontend/src/features/practice/resume-panel.tsx`

**Interfaces:**
- Consumes: `getTrackedSessionIds`/`untrackSession`; `useQueries` from `@tanstack/react-query`; `apiJson`; `qk`; `SessionOut`; UI primitives; `next/link`; `EmptyState`.
- Produces: `<ResumePanel />` — reads tracked ids from localStorage, fetches each session, shows cards for `in_progress` ones with a progress indicator and a Resume link to the runner; auto-untracks ids that 404 or are no longer in progress; `<EmptyState>` when none.

- [ ] **Step 1: Create `frontend/src/features/practice/resume-panel.tsx`**

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { apiJson, ApiError } from "@/lib/api";
import { qk } from "@/lib/api/keys";
import type { SessionOut } from "@/lib/api/types";
import { getTrackedSessionIds, untrackSession } from "./session-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";

export function ResumePanel() {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    setIds(getTrackedSessionIds());
  }, []);

  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: qk.session(id),
      queryFn: () => apiJson<SessionOut>(`/api/practice/sessions/${id}`),
      retry: false,
    })),
  });

  // Untrack ids that no longer resolve or are no longer in progress.
  useEffect(() => {
    results.forEach((r, i) => {
      const id = ids[i];
      if (!id) return;
      if (r.isError && r.error instanceof ApiError && r.error.status === 404) {
        untrackSession(id);
      }
      if (r.data && r.data.status !== "in_progress") {
        untrackSession(id);
      }
    });
  }, [results, ids]);

  const active = useMemo(
    () =>
      results
        .map((r) => r.data)
        .filter((s): s is SessionOut => !!s && s.status === "in_progress"),
    [results]
  );

  if (ids.length === 0 || (results.every((r) => !r.isLoading) && active.length === 0)) {
    return (
      <EmptyState
        title="No sessions in progress"
        description="Create a new practice session from the New tab to get started."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {active.map((s) => {
        const answered = s.config && Array.isArray((s.config as { question_ids?: unknown[] }).question_ids)
          ? null
          : null;
        return (
          <Card key={s.id}>
            <CardHeader>
              <CardTitle className="text-base">Practice session</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {s.correct_count} correct of {s.total_questions} questions
              </p>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary"
                  style={{
                    width: `${
                      s.total_questions > 0
                        ? Math.round((s.correct_count / s.total_questions) * 100)
                        : 0
                    }%`,
                  }}
                />
              </div>
              <Button asChild size="sm">
                <Link href={`/practice/sessions/${s.id}`}>Resume</Link>
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/practice/resume-panel.tsx
git commit -m "feat(practice): add Resume panel backed by localStorage-tracked sessions"
```

---

### Task 22: Practice landing page (Resume / New tabs)

**Files:**
- Create: `frontend/src/app/(app)/practice/page.tsx`

**Interfaces:**
- Consumes: `PageHeader`; `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent`; `ResumePanel`; `CreateSessionForm`.
- Produces: `/practice` landing with a "Resume" tab and a "New session" tab.

- [ ] **Step 1: Create `frontend/src/app/(app)/practice/page.tsx`**

```tsx
"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ResumePanel } from "@/features/practice/resume-panel";
import { CreateSessionForm } from "@/features/practice/create-session-form";

export default function PracticePage() {
  return (
    <div>
      <PageHeader title="Practice" description="Build and resume scoped practice sessions." />
      <Tabs defaultValue="new">
        <TabsList>
          <TabsTrigger value="new">New session</TabsTrigger>
          <TabsTrigger value="resume">Resume</TabsTrigger>
        </TabsList>
        <TabsContent value="new">
          <CreateSessionForm />
        </TabsContent>
        <TabsContent value="resume">
          <ResumePanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds; `/practice` is part of the route tree.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(app)/practice/page.tsx"
git commit -m "feat(practice): add /practice landing with New/Resume tabs"
```

---

### Task 23: Practice runner

**Files:**
- Create: `frontend/src/features/practice/runner.tsx`
- Create: `frontend/src/app/(app)/practice/sessions/[id]/page.tsx`

**Interfaces:**
- Consumes: `useSession`/`useQuestion`/`useSubmitAnswer`/`usePauseSession`/`useResumeSession`/`useFinishSession`/`useUpdateQuestionState`; runner-machine (`initialRunnerState`/`toggleSelection`/`canSubmit`/`markSubmitted`/`RunnerState`); `OptionList`; `untrackSession`; `ApiError`; `useRouter`; UI primitives; `lucide-react` icons; `ErrorType`.
- Produces: `<Runner sessionId />` implementing Select → Submit → Feedback, Next/Finish, Pause/Resume, and the post-submit tools row (bookmark / flag / note / error-type). The route page reads `params.id` and renders `<Runner>`.

- [ ] **Step 1: Create `frontend/src/features/practice/runner.tsx`** (imports + state)

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useSession,
  useQuestion,
  useSubmitAnswer,
  usePauseSession,
  useResumeSession,
  useFinishSession,
  useUpdateQuestionState,
} from "@/lib/api/practice";
import {
  initialRunnerState,
  toggleSelection,
  canSubmit,
  markSubmitted,
  type RunnerState,
} from "./runner-machine";
import { OptionList } from "./option-list";
import { untrackSession } from "./session-tracker";
import { ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Bookmark, Flag, PauseCircle, PlayCircle } from "lucide-react";
import type { ErrorType } from "@/lib/api/types";

const ERROR_TYPES: ErrorType[] = [
  "concept_unclear",
  "misread_stem",
  "memory_lapse",
  "option_confusion",
  "time_pressure",
];

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Runner({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [position, setPosition] = useState(0);
  const [runner, setRunner] = useState<RunnerState>(initialRunnerState(null));
  const [startedAt, setStartedAt] = useState<string>("");

  const session = useSession(sessionId);
  const question = useQuestion(sessionId, position);
  const submitAnswer = useSubmitAnswer(sessionId);
  const pause = usePauseSession(sessionId);
  const resume = useResumeSession(sessionId);
  const finish = useFinishSession(sessionId);
  const updateState = useUpdateQuestionState();

  const delivery = question.data;
  const paused = !!session.data?.paused_at;
```

- [ ] **Step 2: Continue `runner.tsx`** (effects, handlers — append inside the component, before the return)

```tsx
  // Reset the per-question machine whenever a new question is delivered.
  useEffect(() => {
    if (!delivery) return;
    setRunner(initialRunnerState(delivery.previous_answer));
    setStartedAt(new Date().toISOString());
  }, [delivery?.question_id]); // eslint-disable-line react-hooks/exhaustive-deps

  function submit() {
    if (!delivery) return;
    submitAnswer.mutate(
      { position, selected: runner.selected, started_at: startedAt },
      {
        onSuccess: (result) => setRunner((s) => markSubmitted(s, result)),
        onError: (e) => {
          if (e instanceof ApiError && e.status === 409) {
            toast.error("This question has already been answered.");
          } else {
            toast.error("Could not submit your answer.");
          }
        },
      }
    );
  }

  function next() {
    if (!delivery) return;
    if (position + 1 >= delivery.total) {
      finish.mutate(undefined, {
        onSuccess: () => {
          untrackSession(sessionId);
          router.push(`/practice/sessions/${sessionId}/done`);
        },
        onError: () => toast.error("Could not finish the session."),
      });
    } else {
      setPosition((p) => p + 1);
    }
  }

  function setQuestionState(body: Parameters<typeof updateState.mutate>[0]["body"]) {
    if (!delivery) return;
    updateState.mutate(
      { questionId: delivery.question_id, body },
      {
        onSuccess: () => toast.success("Saved."),
        onError: () => toast.error("Could not save."),
      }
    );
  }
```

- [ ] **Step 3: Continue `runner.tsx`** (loading/error guards + return JSX — append after the handlers, then close the component)

```tsx
  if (session.isError) {
    const stale = session.error instanceof ApiError && session.error.status === 409;
    return (
      <ErrorState
        title={stale ? "Session unavailable" : "Could not load session"}
        message={stale ? "This session is finished or no longer available." : "Please go back and try again."}
        onRetry={() => router.push("/practice")}
      />
    );
  }
  if (session.isLoading || question.isLoading || !delivery) {
    return <Loading label="Loading question…" />;
  }
  if (question.isError) {
    return (
      <ErrorState
        message="Could not load this question."
        onRetry={() => question.refetch()}
      />
    );
  }

  const submitted = runner.phase === "submitted";
  const result = runner.result;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Question {delivery.position + 1} of {delivery.total}
        </div>
        <div className="flex items-center gap-2">
          {paused ? (
            <Button variant="outline" size="sm" onClick={() => resume.mutate()}>
              <PlayCircle className="h-4 w-4" /> Resume
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => pause.mutate()}>
              <PauseCircle className="h-4 w-4" /> Pause
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{labelize(delivery.question_type)}</Badge>
          </div>
          <CardTitle className="mt-2 text-lg font-medium leading-relaxed">{delivery.stem}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {paused ? (
            <p className="text-sm text-muted-foreground">Session paused. Resume to continue.</p>
          ) : (
            <OptionList
              questionType={delivery.question_type}
              options={delivery.options}
              selected={runner.selected}
              disabled={submitted || paused}
              onToggle={(i) => setRunner((s) => toggleSelection(s, i, delivery.question_type))}
              result={result}
            />
          )}

          {submitted && !result && delivery.previous_answer && (
            <p className="text-sm text-muted-foreground">
              You already answered this question
              {delivery.previous_answer.is_correct ? " correctly." : " incorrectly."}
            </p>
          )}

          {submitted && result && (
            <div className="space-y-3 rounded-md border bg-muted/30 p-4">
              <div className={result.is_correct ? "font-medium text-success" : "font-medium text-destructive"}>
                {result.is_correct ? "Correct" : "Incorrect"}
              </div>
              {result.correct_rationale && (
                <p className="text-sm leading-relaxed">{result.correct_rationale}</p>
              )}
              {result.key_point_summary && (
                <p className="text-sm text-muted-foreground">{result.key_point_summary}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {submitted && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setQuestionState({ is_bookmarked: true })}>
              <Bookmark className="h-4 w-4" /> Bookmark
            </Button>
            <Button variant="outline" size="sm" onClick={() => setQuestionState({ is_flagged_review: true })}>
              <Flag className="h-4 w-4" /> Flag for review
            </Button>
            <NoteDialog onSave={(note) => setQuestionState({ note })} />
            <Select onValueChange={(v) => setQuestionState({ error_type: v as ErrorType })}>
              <SelectTrigger className="h-9 w-[200px]">
                <SelectValue placeholder="Tag error type" />
              </SelectTrigger>
              <SelectContent>
                {ERROR_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {labelize(t)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Separator />
        </>
      )}

      <div className="flex justify-end gap-2">
        {!submitted ? (
          <Button onClick={submit} disabled={!canSubmit(runner) || paused || submitAnswer.isPending}>
            {submitAnswer.isPending ? "Submitting…" : "Submit"}
          </Button>
        ) : (
          <Button onClick={next} disabled={finish.isPending}>
            {position + 1 >= delivery.total ? (finish.isPending ? "Finishing…" : "Finish") : "Next"}
          </Button>
        )}
      </div>
    </div>
  );
}

function NoteDialog({ onSave }: { onSave: (note: string) => void }) {
  const [note, setNote] = useState("");
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Add note
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Note</DialogTitle>
        </DialogHeader>
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Your note…" />
        <DialogFooter>
          <DialogClose asChild>
            <Button onClick={() => onSave(note)}>Save note</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Create `frontend/src/app/(app)/practice/sessions/[id]/page.tsx`**

```tsx
"use client";

import { Runner } from "@/features/practice/runner";

export default function RunnerPage({ params }: { params: { id: string } }) {
  return <Runner sessionId={params.id} />;
}
```

- [ ] **Step 5: Verify typecheck + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no type errors; build succeeds.

- [ ] **Step 6: Commit**

```bash
git add "frontend/src/features/practice/runner.tsx" "frontend/src/app/(app)/practice/sessions/[id]/page.tsx"
git commit -m "feat(practice): add runner (Select→Submit→Feedback, pause/resume, tools, finish)"
```

---

### Task 24: Practice summary page

**Files:**
- Create: `frontend/src/features/practice/summary.tsx`
- Create: `frontend/src/app/(app)/practice/sessions/[id]/done/page.tsx`

**Interfaces:**
- Consumes: `useSessionSummary`; `PageHeader`; `Card`/`CardContent`/`CardHeader`/`CardTitle`; `Badge`; `Button`; `Loading`; `ErrorState`; `next/link`.
- Produces: `<Summary sessionId />` rendering total/answered/correct, accuracy %, total time, per-domain breakdown, and the wrong-question list (stem + selected vs correct indexes). "Start another" links to `/practice`. The route page reads `params.id`.

- [ ] **Step 1: Create `frontend/src/features/practice/summary.tsx`**

```tsx
"use client";

import Link from "next/link";
import { useSessionSummary } from "@/lib/api/practice";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";

function fmtPct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

function fmtDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}m ${s}s`;
}

export function Summary({ sessionId }: { sessionId: string }) {
  const summary = useSessionSummary(sessionId);

  if (summary.isLoading) return <Loading label="Loading summary…" />;
  if (summary.isError || !summary.data) {
    return <ErrorState message="Could not load the session summary." />;
  }
  const s = summary.data;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Session complete"
        description={`${s.answered_count} answered of ${s.total_questions} · ${s.correct_count} correct`}
        actions={
          <Button asChild>
            <Link href="/practice">Start another</Link>
          </Button>
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Accuracy</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{fmtPct(s.accuracy)}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Correct</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {s.correct_count}/{s.answered_count}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Time spent</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{fmtDuration(s.total_time_spent_ms)}</CardContent>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>By domain</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {s.domains.length === 0 && <p className="text-sm text-muted-foreground">No domain data.</p>}
          {s.domains.map((d, i) => (
            <div key={d.domain_id ?? `none-${i}`} className="flex items-center justify-between text-sm">
              <span>{d.domain_name ?? "Unmapped"}</span>
              <span className="text-muted-foreground">
                {d.correct}/{d.answered} correct
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Wrong questions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {s.wrong_questions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No wrong answers — well done.</p>
          ) : (
            s.wrong_questions.map((w) => (
              <div key={w.question_id} className="rounded-md border p-3">
                <p className="text-sm">{w.stem}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <Badge variant="destructive">Your answer: {w.selected_indexes.join(", ") || "—"}</Badge>
                  <Badge variant="success">Correct: {w.correct_indexes.join(", ")}</Badge>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/app/(app)/practice/sessions/[id]/done/page.tsx`**

```tsx
"use client";

import { Summary } from "@/features/practice/summary";

export default function DonePage({ params }: { params: { id: string } }) {
  return <Summary sessionId={params.id} />;
}
```

- [ ] **Step 3: Verify typecheck + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: no type errors; build succeeds.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/features/practice/summary.tsx" "frontend/src/app/(app)/practice/sessions/[id]/done/page.tsx"
git commit -m "feat(practice): add session summary + wrong-question review page"
```

---

### Task 25: Full verification + acceptance pass

**Files:** none (verification only).

**Interfaces:**
- Consumes: the entire I-1 build.
- Produces: a green build/lint/test run and a manual smoke confirming the acceptance criteria.

- [ ] **Step 1: Run the full frontend gate**

Run: `cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: lint clean; no type errors; all Vitest tests pass (smoke, utils, api, auth-store, require-permission, runner-machine, session-tracker, session-payload, option-list, create-session-form); production build succeeds.

- [ ] **Step 2: Confirm backend tests are untouched**

Run: `cd backend && pytest -q`
Expected: 366 passed (no frontend change touched the backend; acceptance criterion #7).

- [ ] **Step 3: Manual smoke against the full stack**

Run: `docker compose up -d --build && docker compose ps`
Then in a browser:
- Visit `http://localhost:3000/` → redirected to `/login`.
- Click "Dev login (admin / admin)" → lands on `/practice`.
- Reload `/practice` → stays authed (no flash to `/login`; `useHydratedAuth` restored the user via `/api/auth/me`).
- On the New tab: set count, optionally pick a domain/subset, click "Start practice" → routed to the runner.
- Answer a question: select → Submit → see correctness + rationale; bookmark/flag/add note/tag an error type (toasts confirm).
- Click Pause → options disabled; Resume → re-enabled.
- Advance through to the last question → Finish → summary page shows accuracy, per-domain breakdown, and wrong-question list.
- Go back to `/practice` → Resume tab no longer lists the finished session.
- Confirm the sidebar shows Practice (active), Exam/Analytics (disabled "Soon"), and Admin (visible because the dev user is system_admin).

Expected: all steps behave as described.

- [ ] **Step 4: Final commit (if any verification fixups were needed)**

```bash
git add -A
git commit -m "chore(frontend): I-1 verification fixups"
```

---

## Acceptance Criteria Coverage

| Spec criterion | Task(s) |
|---|---|
| 1. build / lint / test pass | Task 1 (harness), Task 25 (gate) |
| 2. Login → /practice → create → Select/Submit/Feedback + tools → pause/resume → finish → summary | Tasks 15, 20, 22, 23, 24 |
| 3. Route guards: unauthed → /login; intended-path redirect | Tasks 13, 15 |
| 4. Sidebar: Practice active, Exam/Analytics disabled, Admin perm-gated | Task 14 |
| 5. Design tokens; correct/incorrect & pass/fail use success/destructive | Tasks 2, 19, 23, 24 |
| 6. No raw-fetch-in-component; all server state via TanStack Query | Tasks 9, 10, 11, 21, 23, 24 |
| 7. No backend changes; 366 backend tests pass | Global constraint; Task 25 Step 2 |

## Notes / deferred (documented limitations)

- **Resume is device-local** (localStorage), per the approved decision — there is no backend session-list endpoint. Sessions started on another browser/device won't appear.
- **Chapter filter is single-select** mapped to `chapter_ids: [id]`. The backend accepts a multi-chapter array; a multi-select UI is a future enhancement, not required by I-1.
- **Revisited already-answered questions** show only "answered correctly/incorrectly" (from `previous_answer`), not the full rationale/correct options — the backend blocks re-submission (409) and `previous_answer` carries no correct-index data.
- **Pause does not stop the backend `elapsed_ms` clock** — pause only blocks submission. Matches backend behavior; no client timer is shown in I-1.
- **Knowledge-point dropdown intentionally omitted** — session creation has no KP filter.
