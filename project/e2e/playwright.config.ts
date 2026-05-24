import { defineConfig, devices } from "@playwright/test";
import dotenv from "dotenv";
import fs from "fs";
import path from "path";

dotenv.config({ path: path.join(__dirname, ".env") });

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:8000";
const startServer = (process.env.E2E_START_SERVER || "false").toLowerCase() === "true";
const traceMode = process.env.E2E_TRACE || "on-first-retry";
const videoMode = process.env.E2E_VIDEO || "off";
const adminStatePath = path.join(__dirname, ".auth", "admin-owner.json");
const adminStorageState = fs.existsSync(adminStatePath) ? adminStatePath : undefined;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  globalSetup: require.resolve("./global-setup"),
  timeout: 45_000,
  expect: { timeout: 12_000 },
  use: {
    baseURL,
    trace: traceMode as "on" | "off" | "retain-on-failure" | "on-first-retry",
    video: videoMode as "on" | "off" | "retain-on-failure" | "on-first-retry",
    screenshot: "only-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 20_000,
  },
  projects: [
    {
      name: "public",
      testMatch: /public\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "shop-user",
      testMatch: /(auth|content|shop)\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: path.join(__dirname, ".auth", "shop-user.json"),
      },
    },
    {
      name: "admin",
      testMatch: /admin\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: adminStorageState,
      },
    },
  ],
  webServer: startServer
    ? {
        command:
          process.platform === "win32"
            ? "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn mesencsi:app --host 127.0.0.1 --port 8000"
            : "../backend/.venv/bin/python -m uvicorn mesencsi:app --host 127.0.0.1 --port 8000",
        cwd: path.join(__dirname, "../backend"),
        url: `${baseURL}/health`,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      }
    : undefined,
});
