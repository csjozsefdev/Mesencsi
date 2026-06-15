import { expect, test } from "@playwright/test";
import { attachConsoleCollector, assertNoCriticalConsoleErrors } from "../helpers/console";
import { sel } from "../helpers/selectors";

test.describe("Public storefront smoke", () => {
  test("homepage loads with hero and navigation", async ({ page }) => {
    const errors = attachConsoleCollector(page);
    await page.goto("/");
    await expect(page.locator(sel.storefront)).toBeVisible();
    await expect(page.locator(sel.heroGlass)).toBeVisible();
    await expect(page.locator(sel.sideNav)).toBeVisible();
    await expect(page.locator(sel.navGallery)).toBeVisible();
    await expect(page.locator(sel.navStories)).toBeVisible();
    assertNoCriticalConsoleErrors(errors, "homepage");
  });

  test("logged-out user sees webshop nav and not storybooks", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(sel.authLoggedOut)).toBeVisible();
    await expect(page.locator(sel.navWebshop)).toBeVisible();
    await expect(page.locator(sel.navStorybooks)).toBeHidden();
  });

  test("guest can open webshop view", async ({ page }) => {
    await page.goto("/");
    await page.locator(sel.navWebshop).click();
    await expect(page.locator(sel.viewWebshop)).toBeVisible();
  });

  test("gallery view loads for anonymous user", async ({ page }) => {
    await page.goto("/");
    await page.locator(sel.navGallery).click();
    await expect(page.locator(sel.viewGallery)).toBeVisible();
    await expect(page.locator(sel.galleryPublicOut)).toBeVisible();
  });

  test("background image is served", async ({ request }) => {
    const res = await request.get("/images/mesencsi-bg.jpg");
    expect(res.status()).toBe(200);
    expect((res.headers()["content-type"] || "").toLowerCase()).toMatch(/image/);
  });
});
