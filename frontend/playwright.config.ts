import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 10000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5183",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "off", // Do not persist credentials entered during sign-in.
  },
});
