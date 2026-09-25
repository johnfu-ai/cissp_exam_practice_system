// E2E (NFR-TEST-02): paper exam mode — timed session, revisable answers,
// submit, raw paper-scoring report.

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

test("paper exam: answer, submit, report", async ({ page }) => {
  await uiLogin(page);

  await page.goto("/papers");
  const firstCard = page.getByTestId("papers-grid").locator("> div").first();
  await firstCard.getByRole("button", { name: /Exam:/ }).click();
  await page.waitForURL(/\/paper-play\/[0-9a-f-]+/);

  // exam mode badge + countdown timer + red submit
  await expect(page.getByText("Exam", { exact: true })).toBeVisible();
  await expect(page.getByLabel("timer")).not.toContainText("--:--");

  // answer the first two questions (option A), navigating forward auto-saves
  await page.locator("button", { hasText: /^A\./ }).first().click();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.getByText("Question 2 of")).toBeVisible();
  await page.locator("button", { hasText: /^A\./ }).first().click();

  // answer sheet cell 1 is answered
  await expect(
    page.getByRole("button", { name: "question 1 answered" }),
  ).toBeVisible({ timeout: 15_000 });

  // submit the paper -> report page
  await page.getByRole("button", { name: "Submit paper" }).click();
  await page.waitForURL(/\/report$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Exam report" })).toBeVisible();
  await expect(page.getByText(/Passed|Not passed/)).toBeVisible();

  // review list with per-question explanations
  const firstReview = page.getByRole("button", { name: "Show explanation" }).first();
  await firstReview.click();
  await expect(
    page.getByRole("button", { name: "Hide explanation" }).first(),
  ).toBeVisible();
});
