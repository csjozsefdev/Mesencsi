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
      version: "2026-07-13",
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

  test("approved legal text is split across the matching legal pages", async ({ page }) => {
    await page.goto("/aszf");
    const terms = page.locator("#view-aszf");
    await expect(terms).toContainText("Hatályos: 2026.07.13-tól visszavonásig");
    await expect(terms).toContainText("A Szolgáltató nyilvántartási száma: 61964093");
    await expect(terms).toContainText("Kellékszavatosság");
    await expect(terms).not.toContainText("Fogyasztóvédelem - Fogyasztói vita");
    await expect(terms.locator(".legal-placeholder")).toHaveCount(0);

    await page.goto("/elallas");
    await expect(page.locator("#view-elallas")).toContainText("Elállási jog");
    await page.goto("/szallitas");
    await expect(page.locator("#view-szallitas")).toContainText("Házhoz szállítás futárszolgálattal");
    await page.goto("/fizetes");
    await expect(page.locator("#view-fizetes")).toContainText("Barion Payment Zrt.");
    await page.goto("/panaszkezeles");
    await expect(page.locator("#view-panaszkezeles")).toContainText("Fogyasztóvédelem - Fogyasztói vita");
  });

  test("cookie and privacy policies render the 2026-07-13 versions without placeholders", async ({ page }) => {
    await page.goto("/sutik");
    const cookies = page.locator("#view-sutik");
    await expect(cookies).toContainText("Dokumentumverzió: 2026-07-13");
    await expect(cookies).toContainText("mesencsi_guest_checkout_token");
    await expect(cookies).toContainText("A weboldal nem használ analitikai vagy marketing célú sütit");
    await expect(cookies.locator(".legal-placeholder")).toHaveCount(0);

    await page.goto("/adatkezeles");
    await expect(page.locator("#view-adatkezeles")).toContainText("Dokumentumverzió: 2026-07-13");
  });

  test("registration and checkout compliance controls are wired", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#regTermsAccepted")).toHaveAttribute("required", "");
    await expect(page.locator("#regPrivacyAcknowledged")).toHaveAttribute("required", "");
    await expect(page.getByText("A fizetési folyamatot a Barion kezeli.")).toHaveCount(2);
    await expect(page.getByText("Megrendelés fizetési kötelezettséggel")).toHaveCount(1);
  });
});
