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

/** Login through the UI and land on /papers. */
export async function uiLogin(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
  await page.getByLabel(/password/i).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /log in|登录/i }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15_000 });
}
