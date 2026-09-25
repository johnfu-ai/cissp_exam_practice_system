// Shared e2e helpers: idempotent backend seeding (mockpapers ETL commit) over
// the API, so the specs only drive the UI.

import { APIRequestContext, expect } from "@playwright/test";
import { API_BASE } from "../playwright.config";

export const ADMIN_EMAIL = process.env.E2E_EMAIL ?? "admin@example.com";
export const ADMIN_PASSWORD = process.env.E2E_PASSWORD ?? "Adminadmin1";

export async function loginToken(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API_BASE}/api/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  });
  expect(res.ok(), `admin login failed: ${res.status()}`).toBeTruthy();
  const body = await res.json();
  return body.access_token as string;
}

/** Idempotently ensure the mockpapers dataset is committed (8 papers). */
export async function ensureMockPapersImported(request: APIRequestContext): Promise<void> {
  const token = await loginToken(request);
  const headers = { Authorization: `Bearer ${token}` };

  const papers = await request.get(`${API_BASE}/api/papers`, { headers });
  if (papers.ok()) {
    const body = await papers.json();
    if ((body.total ?? 0) >= 8) return; // already imported
  }

  const run = await request.post(`${API_BASE}/api/etl/runs`, {
    headers,
    data: { dataset_slug: "mockpapers" },
  });
  expect(run.ok(), `etl preview failed: ${run.status()} ${await run.text()}`).toBeTruthy();
  const { run_id: runId } = await run.json();
  const commit = await request.post(`${API_BASE}/api/etl/runs/${runId}/commit`, {
    headers,
  });
  expect(commit.ok(), `etl commit failed: ${commit.status()}`).toBeTruthy();
}

/**
 * Determinism on local reruns: finish every in-progress PRACTICE session of
 * the e2e account. Earlier local runs may have left sessions behind (CI
 * always starts from a fresh DB); with several in-progress sessions for the
 * same paper+mode the Continue prompt's target becomes ambiguous.
 */
export async function finishInProgressPractices(
  request: APIRequestContext,
): Promise<void> {
  const headers = { Authorization: `Bearer ${await loginToken(request)}` };
  const res = await request.get(`${API_BASE}/api/papers/sessions/in-progress`, {
    headers,
  });
  if (!res.ok()) return;
  const items = ((await res.json()).items ?? []) as Array<{
    kind: string;
    session_id: string;
  }>;
  for (const item of items) {
    if (item.kind !== "practice") continue;
    await request
      .post(`${API_BASE}/api/practice/sessions/${item.session_id}/finish`, {
        headers,
      })
      .catch(() => {});
  }
}

/** Login through the UI and land on /papers. */
export async function uiLogin(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
  await page.getByLabel(/password/i).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /log in|登录/i }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15_000 });
}

/**
 * Start a paper session through the first paper card, handling the
 * FR-PAPER-12 continue prompt: earlier runs of the suite may have left an
 * in-progress session for the same paper+mode, in which case clicking
 * Practice/Exam opens the 继续答题 dialog — always choose Start over so the
 * spec drives a fresh session.
 */
export async function startPaperSession(
  page: import("@playwright/test").Page,
  mode: "Practice" | "Exam",
): Promise<void> {
  const firstCard = page.getByTestId("papers-grid").locator("> div").first();
  await firstCard.getByRole("button", { name: new RegExp(`^${mode}:`) }).click();
  const startOver = page.getByRole("button", { name: "Start over" });
  await Promise.race([
    page.waitForURL(/\/paper-play\/[0-9a-f-]+/, { timeout: 15_000 }),
    startOver.waitFor({ state: "visible", timeout: 15_000 }),
  ]);
  if (await startOver.isVisible()) {
    await startOver.click();
    await page.waitForURL(/\/paper-play\/[0-9a-f-]+/, { timeout: 15_000 });
  }
}

// The e2e account is a real shared account whose persisted UI language may
// be zh while the specs assert English chrome. Pin it to English for the
// run and restore the saved value afterwards (partial PUT: other
// preferences are untouched). Best-effort: a 429/timeout mid-run must not
// leave the account flipped — restore retries and never throws.
let savedUiLanguage: string | null = null;

export async function enforceEnglishUi(request: APIRequestContext): Promise<void> {
  const headers = { Authorization: `Bearer ${await loginToken(request)}` };
  const me = await request.get(`${API_BASE}/api/auth/me`, { headers });
  if (me.ok()) {
    savedUiLanguage = ((await me.json()).interface_language as string) ?? "en";
  }
  if (savedUiLanguage !== "en") {
    await request.put(`${API_BASE}/api/users/me/preferences`, {
      headers,
      data: { interface_language: "en" },
    });
  }
}

export async function restoreUiLanguage(request: APIRequestContext): Promise<void> {
  if (savedUiLanguage == null) return;
  const target = savedUiLanguage;
  savedUiLanguage = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const headers = { Authorization: `Bearer ${await loginToken(request)}` };
      const res = await request.put(`${API_BASE}/api/users/me/preferences`, {
        headers,
        data: { interface_language: target },
      });
      if (res.ok()) return;
    } catch {
      // fall through to the retry/backoff
    }
    await new Promise((r) => setTimeout(r, 5_000 * (attempt + 1)));
  }
}
