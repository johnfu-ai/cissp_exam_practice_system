import { defineConfig } from "vitest/config";

// Unit tests for the mini program's pure lib layer (NFR-TEST-03): the `wx`
// global is mocked per-test by tests/wx-mock.js. No DOM needed — the
// environment runs in plain node so CommonJS `require` matches the runtime.
export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.js"],
  },
});
