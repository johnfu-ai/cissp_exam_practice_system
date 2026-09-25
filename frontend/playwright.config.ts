import { defineConfig, devices } from "@playwright/test";

// Playwright e2e (NFR-TEST-02): core learner journey against a REAL backend.
//
// The backend is expected at PLAYWRIGHT_API_BASE (default http://localhost:8000)
// — locally that's the docker compose stack (`docker compose up -d`, which
// also runs migrate + seed; commit the mockpapers dataset once via the ETL API,
// or let this suite's setup do it — it is idempotent). CI starts uvicorn with
// postgres+redis service containers instead.
//
// Only the frontend web server is managed here; reuseExistingServer lets a
// dev server (`npm run dev`) be reused when present.

export const API_BASE = process.env.PLAYWRIGHT_API_BASE ?? "http://localhost:8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_API_URL: API_BASE,
    },
  },
});
