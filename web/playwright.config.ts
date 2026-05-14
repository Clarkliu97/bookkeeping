import { defineConfig } from "@playwright/test";


const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3100";
const useManagedWebServer = !process.env.E2E_BASE_URL;


export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 120_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL,
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  ...(useManagedWebServer
    ? {
        webServer: {
          command: "npm run build && npm run start -- --hostname 127.0.0.1 --port 3100",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 300_000,
        },
      }
    : {}),
});