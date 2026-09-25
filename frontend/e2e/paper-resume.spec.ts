// E2E (PRD v1.5 FR-PAPER-11/12): resume + mode switch — answer part of a
// paper, "leave" (reload), come back via the in-progress list with the sheet
// and progress restored, then switch practice -> exam with answers carried.

import { test, expect } from "@playwright/test";
import {
  enforceEnglishUi,
  ensureMockPapersImported,
  restoreUiLanguage,
  uiLogin,
} from "./helpers";

test.beforeAll(async ({ request }) => {
  await ensureMockPapersImported(request);
  await enforceEnglishUi(request);
});

test.afterAll(async ({ request }) => {
  await restoreUiLanguage(request);
});

test("exit and resume keeps answers, progress, and mode switch carries them", async ({ page }) => {
  await uiLogin(page);

  // Start a fresh practice on the first paper
  await page.goto("/papers");
  const firstCard = page.getByTestId("papers-grid").locator("> div").first();
  await firstCard.getByRole("button", { name: /Practice:/ }).click();
  await page.waitForURL(/\/paper-play\/[0-9a-f-]+\?kind=practice/);
  const sessionUrl = page.url();

  // The in-progress section on /papers lists it
  await page.goto("/papers");
  await expect(page.getByRole("heading", { name: "In progress" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Continue:/ }).first()).toBeVisible();

  // Re-enter the session directly (simulating continue)
  await page.goto(sessionUrl);

  // Answer the first question, then jump ahead to question 3 via the palette
  await page.locator("button", { hasText: /^B\./ }).first().click();
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await expect(
    page.getByText("Correct").or(page.getByText("Incorrect")),
  ).toBeVisible({ timeout: 15_000 });
  await page
    .getByRole("button", { name: "question 3 unanswered" })
    .click();
  await expect(page.getByText(/Question 3 of \d+/)).toBeVisible();

  // "Leave" mid-session: a full reload must resume where we left off —
  // question 2 is the first unanswered, cell 1 stays answered
  await page.reload();
  await expect(page.getByText(/Question 2 of \d+/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.getByRole("button", { name: "question 1 answered" }),
  ).toBeVisible();

  // FR-PAPER-11: switch to exam mode; answers and the paper carry over
  await page.getByRole("button", { name: "Switch to exam" }).click();
  await page.waitForURL(/\/paper-play\/[0-9a-f-]+\?kind=exam/);
  await expect(page.getByText("Exam", { exact: true })).toBeVisible();
  await expect(page.getByLabel("timer")).toBeVisible();
  // the first question's saved answer is present in the converted session
  await page.getByRole("button", { name: "question 1 answered" }).click();
  await expect(page.getByText(/Question 1 of \d+/)).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.locator("button", { hasText: /^B\./ }).first(),
  ).toHaveClass(/border-primary/);
});
