import { expect, test } from "@playwright/test";
import { E2E_USER_EMAIL, E2E_USER_PASSWORD } from "../helpers/env";
import { sel } from "../helpers/selectors";

test.describe("Shop auth flow", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("login shows user panel and protected nav", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(sel.authLoggedOut)).toBeVisible();
    await page.locator(sel.loginEmail).fill(E2E_USER_EMAIL);
    await page.locator(sel.loginPassword).fill(E2E_USER_PASSWORD);
    await page.locator(sel.loginForm).locator('button[type="submit"]').click();
    await expect(page.locator(sel.authLoggedIn)).toBeVisible({ timeout: 15_000 });
    await expect(page.locator(sel.navWebshop)).toBeVisible();
    await expect(page.locator(sel.cartFab)).toBeVisible();
  });

  test("logout hides protected elements", async ({ page }) => {
    await page.goto("/");
    await page.locator(sel.loginEmail).fill(E2E_USER_EMAIL);
    await page.locator(sel.loginPassword).fill(E2E_USER_PASSWORD);
    await page.locator(sel.loginForm).locator('button[type="submit"]').click();
    await expect(page.locator(sel.authLoggedIn)).toBeVisible();
    await page.locator(sel.logoutBtn).click();
    await expect(page.locator(sel.authLoggedOut)).toBeVisible();
    await expect(page.locator(sel.navWebshop)).toBeHidden();
    await expect(page.locator(sel.cartFab)).toBeHidden();
  });
});

test.describe("Shop session (storageState)", () => {
  test("restored session shows logged-in UI", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(sel.authLoggedIn)).toBeVisible();
    await expect(page.locator(sel.navWebshop)).toBeVisible();
  });
});
