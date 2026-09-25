// E2E (PRD v1.5/1.6 FR-PAPER-11/12): re-entry + resume — start a paper,
// answer part of it, come back via the continue prompt (继续答题: continue
// last attempt / start over), resume with the sheet and progress restored,
// then switch practice -> exam with answers carried.

import { test, expect } from "@playwright/test";
import {
  enforceEnglishUi,
  ensureMockPapersImported,
  finishInProgressPractices,
  restoreUiLanguage,
  startPaperSession,
  uiLogin,
} from "./helpers";

test.beforeAll(async ({ request }) => {
  await ensureMockPapersImported(request);
  await enforceEnglishUi(request);
  // local reruns accumulate sessions; the Continue assertions below need an
  // unambiguous in-progress practice session (CI always starts fresh)
  await finishInProgressPractices(request);
});

test.afterAll(async ({ request }) => {
  await restoreUiLanguage(request);
});

test("continue prompt + resume keeps answers, progress, and mode switch carries them", async ({ page }) => {
  await uiLogin(page);

  // Start a fresh practice on the first paper (Start over if an old run left
  // an in-progress session behind)
  await page.goto("/papers");
  await startPaperSession(page, "Practice");
  await page.waitForURL(/\/paper-play\/[0-9a-f-]+\?kind=practice/);
  const sessionPath = new URL(page.url()).pathname + new URL(page.url()).search;

  // No dedicated "In progress" section exists anymore (FR-PAPER-12, v1.6)
  await page.goto("/papers");
  await expect(page.getByRole("heading", { name: "In progress" })).toHaveCount(0);

  // Starting the SAME paper+mode again opens the 继续答题 prompt
  const firstCard = page.getByTestId("papers-grid").locator("> div").first();
  await firstCard.getByRole("button", { name: /^Practice:/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Continue answering");
  await expect(dialog).toContainText("unfinished attempt");

  // "Continue last attempt" returns to the SAME session
  await page.getByRole("button", { name: "Continue last attempt" }).click();
  await page.waitForURL((u) => u.pathname + u.search === sessionPath);

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

  // "Start over" creates a FRESH session (different URL, empty sheet)
  await page.goto("/papers");
  await firstCard.getByRole("button", { name: /^Practice:/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Start over" }).click();
  await page.waitForURL(
    (u) => /\/paper-play\/[0-9a-f-]+\?kind=practice/.test(u.pathname + u.search)
      && u.pathname + u.search !== sessionPath,
  );
  await expect(
    page.getByRole("button", { name: "question 1 unanswered" }),
  ).toBeVisible({ timeout: 15_000 });

  // Finish the start-over session so only the ORIGINAL one stays in
  // progress (the continue prompt picks the newest otherwise)
  await page.getByRole("button", { name: "Finish" }).click();
  await expect(page.getByRole("heading", { name: "Session summary" })).toBeVisible();

  // Answer-records modal (FR-PAPER-14) lists the paper's attempts
  await page.goto("/papers");
  await firstCard.getByRole("button", { name: /^Records:/ }).click();
  const records = page.getByRole("dialog");
  await expect(records).toBeVisible();
  await expect(records).toContainText(/· Records/);
  await page.keyboard.press("Escape");
  await expect(records).toBeHidden();

  // v1.7: Start over also ABANDONED the original in-progress session — with
  // nothing in progress, starting practice again goes straight to a fresh
  // session (no continue prompt)
  await firstCard.getByRole("button", { name: /^Practice:/ }).click();
  await page.waitForURL(/\/paper-play\/[0-9a-f-]+\?kind=practice/);

  // FR-PAPER-11: answer q1, then switch to exam via the segment — answers
  // and the paper carry over
  await page.locator("button", { hasText: /^B\./ }).first().click();
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await expect(
    page.getByText("Correct").or(page.getByText("Incorrect")),
  ).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Exam", exact: true }).click();
  await page.waitForURL(/\/paper-play\/[0-9a-f-]+\?kind=exam/);
  await expect(
    page.getByRole("group", { name: "Mode switch" }),
  ).toBeVisible();
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
