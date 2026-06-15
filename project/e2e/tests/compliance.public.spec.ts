import { expect, test } from "@playwright/test";

test.describe("Compliance storefront", () => {
  test("cookie consent is versioned, reopenable, changeable and withdrawable", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#cookieBanner")).toBeVisible();

    const blockedBeforeConsent = await page.evaluate(() =>
      (window as any).Mesencsi.storage.setLocal("mesencsi_selected_coupon", "WELCOME"),
    );
    expect(blockedBeforeConsent).toBe(false);

    await page.locator("#cookieNecessaryOnly").click();
    await expect(page.locator("#cookieBanner")).toBeHidden();
    const necessaryConsent = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("mesencsi_cookie_consent_v1") || "null"),
    );
    expect(necessaryConsent).toMatchObject({
      version: "2026-06-14",
      necessary: true,
      functional: false,
    });

    await page.locator("#cookieSettingsOpen").click();
    await expect(page.locator("#cookiePreferences")).toBeVisible();
    await page.locator("#cookieFunctionalConsent").check();
    await page.locator("#cookiePreferencesSave").click();

    const stored = await page.evaluate(() => {
      const ok = (window as any).Mesencsi.storage.setLocal("mesencsi_selected_coupon", "WELCOME");
      return { ok, value: localStorage.getItem("mesencsi_selected_coupon") };
    });
    expect(stored).toEqual({ ok: true, value: "WELCOME" });

    await page.locator("#cookieSettingsOpen").click();
    await page.locator("#cookieWithdraw").click();
    const withdrawn = await page.evaluate(() => ({
      consent: JSON.parse(localStorage.getItem("mesencsi_cookie_consent_v1") || "null"),
      optionalValue: localStorage.getItem("mesencsi_selected_coupon"),
    }));
    expect(withdrawn.consent.functional).toBe(false);
    expect(withdrawn.optionalValue).toBeNull();
  });

  test("all legal routes render the matching view", async ({ page }) => {
    for (const route of [
      "aszf",
      "adatkezeles",
      "impresszum",
      "elallas",
      "szallitas",
      "fizetes",
      "panaszkezeles",
      "sutik",
    ]) {
      await page.goto(`/${route}`);
      await expect(page.locator(`#view-${route}`)).toBeVisible();
    }
  });

  test("registration and checkout compliance controls are wired", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#regTermsAccepted")).toHaveAttribute("required", "");
    await expect(page.locator("#regPrivacyAcknowledged")).toHaveAttribute("required", "");
    await expect(page.getByText("A fizetési folyamatot a Barion kezeli.")).toHaveCount(2);
    await expect(page.getByText("Megrendelés fizetési kötelezettséggel")).toHaveCount(1);
  });
});
