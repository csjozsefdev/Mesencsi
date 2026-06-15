import { chromium, request } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";
import fs from "fs";
import path from "path";
import { adminLogin, ensureVerifiedShopUser, shopLogin } from "./helpers/auth-api";
import { E2E_API_URL, E2E_BASE_URL } from "./helpers/env";

const AUTH_DIR = path.join(__dirname, ".auth");

async function saveShopStorage(api: APIRequestContext, user: object): Promise<void> {
  const state = await api.storageState();
  const browser = await chromium.launch();
  const context = await browser.newContext({
    baseURL: E2E_BASE_URL,
    storageState: { cookies: state.cookies, origins: [] },
  });
  await context.addInitScript(({ user: u }) => {
    localStorage.setItem("mesencsi_user_profile_json", JSON.stringify(u));
  }, { user });
  const page = await context.newPage();
  await page.goto("/");
  await page.waitForSelector("[data-testid=auth-logged-in]", { state: "visible", timeout: 15_000 });
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  await context.storageState({ path: path.join(AUTH_DIR, "shop-user.json") });
  await browser.close();
}

async function saveAdminStorage(api: APIRequestContext): Promise<void> {
  const state = await api.storageState();
  const browser = await chromium.launch();
  const context = await browser.newContext({
    baseURL: E2E_BASE_URL,
    storageState: { cookies: state.cookies, origins: [] },
  });
  const page = await context.newPage();
  await page.goto("/admin");
  await page.waitForSelector("[data-testid=admin-dashboard]", { state: "visible", timeout: 20_000 });
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  await context.storageState({ path: path.join(AUTH_DIR, "admin-owner.json") });
  await browser.close();
}

export default async function globalSetup(): Promise<void> {
  const healthApi = await request.newContext({ baseURL: E2E_API_URL });
  const health = await healthApi.get("/health");
  if (!health.ok()) {
    throw new Error(
      `E2E: backend nem elérhető (${E2E_API_URL}/health → ${health.status()}). Indítsd: backend\\run.bat`
    );
  }
  await healthApi.dispose();

  if ((process.env.E2E_PUBLIC_ONLY || "").toLowerCase() === "true") {
    return;
  }

  const shopApi = await request.newContext({ baseURL: E2E_API_URL });
  await ensureVerifiedShopUser(shopApi);
  const shop = await shopLogin(shopApi);
  await saveShopStorage(shopApi, shop.user);
  await shopApi.dispose();

  const adminApi = await request.newContext({ baseURL: E2E_API_URL });
  try {
    await adminLogin(adminApi);
    await saveAdminStorage(adminApi);
    fs.writeFileSync(path.join(AUTH_DIR, ".admin-ready"), "1", "utf8");
  } catch (e) {
    console.warn("[e2e global-setup] Admin auth state skipped:", (e as Error).message);
    console.warn("  Állítsd be ADMIN_JWT_SECRET + OWNER_PASSWORD a backend .env-ben.");
  } finally {
    await adminApi.dispose();
  }
}
