import { expect, test } from "@playwright/test";

import fs from "fs";

import path from "path";

import {

  E2E_ADMIN_PASSWORD,

  E2E_ADMIN_USER,

  hasAdminE2eSession,

} from "../helpers/env";

import { sel } from "../helpers/selectors";



const adminStateFile = path.join(__dirname, "../.auth/admin-owner.json");

const hasAdminState = () => fs.existsSync(adminStateFile);



test.describe("Admin access", () => {

  test.use({ storageState: { cookies: [], origins: [] } });



  test("admin login reaches dashboard", async ({ page }) => {

    test.skip(!hasAdminE2eSession(), "Admin E2E: állítsd be E2E_ADMIN_PASSWORD a backend OWNER jelszavával");

    await page.goto("/admin/login");

    await page.locator(sel.adminUsername).fill(E2E_ADMIN_USER);

    await page.locator(sel.adminPassword).fill(E2E_ADMIN_PASSWORD);

    await page.locator(sel.adminLoginForm).locator('button[type="submit"]').click();

    await expect(page).toHaveURL(/\/admin(?:$|[?#])/);

    await expect(page.locator(sel.adminDashboard)).toBeVisible();

    await expect(page.locator(sel.adminTopnav)).toBeVisible();

  });



  test("logged-out admin route shows login", async ({ page }) => {

    await page.goto("/admin");

    await expect(page).toHaveURL(/\/admin\/login/, { timeout: 15_000 });

    await expect(page.locator(sel.adminLoginForm)).toBeVisible();

  });

});



test.describe("Admin panel (owner session)", () => {

  test.beforeEach(() => {

    test.skip(!hasAdminState(), "Admin storageState hiányzik — állítsd be E2E_ADMIN_PASSWORD a backend OWNER jelszavával");

  });



  test("admin navigation modules are reachable", async ({ page }) => {

    await page.goto("/admin");

    await expect(page.locator(sel.adminDashboard)).toBeVisible();

    await page.locator(sel.adminNavOrders).click();

    await expect(page.locator("#view-orders")).toHaveClass(/is-active/);

    await page.locator(sel.adminNavGallery).click();

    await expect(page.locator("#view-gallery")).toHaveClass(/is-active/);

    await page.locator(sel.adminNavStorybooks).click();

    await expect(page.locator("#view-storybooks-admin")).toHaveClass(/is-active/);

  });



  test("admin news module via dashboard card", async ({ page }) => {

    await page.goto("/admin");

    await page.locator('button.dash-card[data-nav="news"]').first().click();

    await expect(page.locator(sel.adminNews)).toHaveClass(/is-active/);

  });

});

