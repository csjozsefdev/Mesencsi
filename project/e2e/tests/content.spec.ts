import { expect, test } from "@playwright/test";
import { sel } from "../helpers/selectors";

test.describe("Public content smoke", () => {
  test("featured news area loads on homepage", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(sel.heroGlass)).toBeVisible();
    const heroText = await page.locator(sel.heroGlass).innerText();
    expect(heroText.length).toBeGreaterThan(20);
  });

  test("products catalog (Termékek) loads without login", async ({ page }) => {
    await page.goto("/");
    await page.locator(sel.navStories).click();
    await expect(page.locator("#view-stories")).toBeVisible();
    await expect(page.locator(sel.productsCatalogOut)).toBeVisible();
    await expect(page.locator(sel.productsCatalogOut)).not.toContainText("Betöltés…", {
      timeout: 15_000,
    });
  });
});

test.describe("Authenticated content", () => {
  test("gallery view loads items grid", async ({ page }) => {
    await page.goto("/");
    await page.locator(sel.navGallery).click();
    await expect(page.locator(sel.viewGallery)).toBeVisible();
    await expect(page.locator(sel.galleryPublicOut)).toBeVisible();
    await expect(page.locator(sel.galleryPublicOut)).not.toContainText("Betöltés…", {
      timeout: 15_000,
    });
  });

  test("storybooks list view opens when menu available", async ({ page }) => {
    await page.goto("/");
    const nav = page.locator(sel.navStorybooks);
    const visible = await nav.isVisible();
    test.skip(!visible, "Mesekönyvek menü rejtve — nincs közzétett könyv vagy feature ki");
    await nav.click();
    await expect(page.locator(sel.viewStorybooks)).toBeVisible();
    await expect(page.locator("#storybooksCatalogOut")).toBeVisible();
  });
});
