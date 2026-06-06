import { expect, test } from "@playwright/test";
import { openCartView } from "../helpers/navigation";
import { sel } from "../helpers/selectors";

test.describe("Shop / cart boundary", () => {
  test("webshop view loads for logged-in user", async ({ page }) => {
    await page.goto("/");
    await page.locator(sel.navWebshop).click();
    await expect(page.locator(sel.viewWebshop)).toBeVisible();
    await expect(page.locator(sel.productsOut)).toBeVisible();
    await expect(page.locator(sel.productsOut)).not.toContainText("Betöltés…", {
      timeout: 15_000,
    });
  });

  test("cart view opens and shows empty or items state", async ({ page }) => {
    await page.goto("/");
    await openCartView(page);
    await expect(page.locator(sel.viewCart)).toBeVisible();
    await expect(page.locator(sel.viewCart)).toContainText(/kosar|Összesen|rendelés/i);
  });

  test("add to cart when products exist", async ({ page }) => {
    await page.goto("/");
    await page.locator(sel.navWebshop).click();
    await expect(page.locator(sel.viewWebshop)).toBeVisible();
    const addBtn = page.locator(".btn-add-cart").first();
    const count = await addBtn.count();
    test.skip(count === 0, "Nincs termék az adatbázisban — E2E add-to-cart kihagyva");
    await addBtn.click();
    await expect(page.locator(sel.cartFab)).toBeVisible();
    const badge = page.locator("#cartFabBadge");
    await expect(badge).toBeVisible();
  });

  test("checkout panel visible without starting Barion payment", async ({ page }) => {
    await page.goto("/");
    await page.locator(sel.navWebshop).click();
    const addBtn = page.locator(".btn-add-cart").first();
    if ((await addBtn.count()) === 0) {
      test.skip(true, "Nincs termék — checkout smoke kihagyva");
    }
    await addBtn.click();
    await openCartView(page);
    await expect(page.locator(sel.viewCart)).toBeVisible();
    await expect(page.locator("#cartWithItems")).toBeVisible();
    await expect(page.locator('#checkoutForm button[type="submit"]')).toBeVisible();
    // Nem submitelünk — valódi Barion / POST /orders elkerülése
  });

  test("barion stub return URL does not crash storefront", async ({ page }) => {
    await page.goto("/?payment=barion&pid=preview-e2e-test&sandbox=true");
    await expect(page.locator(sel.storefront)).toBeVisible();
    await expect(page.locator(sel.heroGlass)).toBeVisible();
  });
});
