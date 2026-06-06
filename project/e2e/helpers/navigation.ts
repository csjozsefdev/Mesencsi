import type { Page } from "@playwright/test";
import { sel } from "./selectors";

/** Desktop: kosár FAB; mobil: oldalsó „Kosár” menü. */
export async function openCartView(page: Page): Promise<void> {
  const navCart = page.locator(sel.navCart);
  if (await navCart.isVisible()) {
    await navCart.click();
    return;
  }
  await page.locator(sel.cartFab).click();
}

/** Bejelentkezett user: Webshop; vendég: Termékek katalógus. */
export async function openProductsBrowse(page: Page): Promise<void> {
  const webshop = page.locator(sel.navWebshop);
  try {
    await webshop.waitFor({ state: "visible", timeout: 15_000 });
    await webshop.click();
    return;
  } catch {
    /* kijelentkezett — Termékek menü */
  }
  await page.locator(sel.navStories).click();
}
