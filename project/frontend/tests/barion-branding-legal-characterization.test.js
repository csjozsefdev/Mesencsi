#!/usr/bin/env node
"use strict";

/**
 * Barion merchant-acceptance frontend characterization: guards the fixes made after Barion's
 * rejection review — the official unmodified payment-method logo strip, mandatory ÁSZF/Privacy
 * consent at checkout, the complete competent conciliation board (Fejér Vármegyei Békéltető
 * Testület), single authoritative Pixel implementation, and no leftover foreign-template copy.
 *
 * Pure Node, no browser, no backend — run directly:
 *   node project/frontend/tests/barion-branding-legal-characterization.test.js
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const FRONTEND_DIR = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(FRONTEND_DIR, "mesencsi.html"), "utf8");
const css = fs.readFileSync(path.join(FRONTEND_DIR, "style.css"), "utf8");
const forgotHtml = fs.readFileSync(path.join(FRONTEND_DIR, "forgot-password.html"), "utf8");
const resetHtml = fs.readFileSync(path.join(FRONTEND_DIR, "reset-password.html"), "utf8");
const PIXEL_LOADER_TAG = '<script src="/js/barion-pixel.js"></script>';
const PIXEL_SLOT = "<!-- BARION_PIXEL_SLOT -->";

function countOccurrences(haystack, needle) {
  return haystack.split(needle).length - 1;
}

function sectionHtml(id) {
  const start = html.indexOf('id="' + id + '"');
  assert.ok(start !== -1, `section #${id} not found`);
  const end = html.indexOf("</section>", start);
  assert.ok(end !== -1, `closing </section> for #${id} not found`);
  return html.slice(start, end);
}

let failures = 0;
function check(name, fn) {
  try {
    fn();
    console.log("  ok - " + name);
  } catch (err) {
    failures++;
    console.log("  FAIL - " + name);
    console.log("    " + (err && err.message ? err.message : err));
  }
}

console.log("Barion branding / legal-copy characterization");

const OFFICIAL_STRIP_ASSET = "barion-smart-banner-light.svg";

check("Official Barion payment-method logo strip exists in source control, unmodified", () => {
  const stripPath = path.join(FRONTEND_DIR, "images", OFFICIAL_STRIP_ASSET);
  assert.ok(fs.existsSync(stripPath), `images/${OFFICIAL_STRIP_ASSET} is missing — must be the supplied official Barion asset, not a redraw`);
  const svg = fs.readFileSync(stripPath, "utf8");
  assert.ok(svg.trim().startsWith("<svg"), `images/${OFFICIAL_STRIP_ASSET} does not look like a valid SVG file`);
  assert.ok(svg.length > 5000, `images/${OFFICIAL_STRIP_ASSET} looks truncated — the official strip is a single multi-logo asset, not a stripped-down copy`);
  // The old standalone Barion-only wordmark must be gone, not left alongside the strip.
  assert.equal(fs.existsSync(path.join(FRONTEND_DIR, "images", "barion-logo.svg")), false, "old standalone barion-logo.svg should be removed now that the official strip replaces it everywhere");
});

check("Homepage (site-wide footer) includes the official logo strip as a single image, not split logos", () => {
  const footer = html.slice(html.indexOf('class="site-footer"'), html.indexOf("</footer>"));
  assert.ok(footer.includes(`/images/${OFFICIAL_STRIP_ASSET}`), "footer does not reference the official Barion logo strip");
  assert.equal(countOccurrences(footer, "<img"), 1, "footer payment-method branding must be exactly one <img> (the whole strip), not separate per-brand images");
  assert.ok(footer.includes('class="barion-badge"'), "footer Barion badge markup missing");
});

check("Checkout/payment area includes the official logo strip as a single image, not split logos", () => {
  const disclosure = html.slice(
    html.indexOf('class="checkout-payment-disclosure"'),
    html.indexOf('class="checkout-payment-disclosure"') + 400
  );
  assert.ok(disclosure.includes(`/images/${OFFICIAL_STRIP_ASSET}`), "checkout payment disclosure does not reference the official Barion logo strip");
  assert.equal(countOccurrences(disclosure, "<img"), 1, "checkout payment-method branding must be exactly one <img> (the whole strip), not separate per-brand images");
});

check("Logo strip keeps its original aspect ratio and is scaled only proportionally via CSS", () => {
  assert.ok(html.includes(`width="567" height="108"`), "the <img> width/height attributes should match the official asset's native 567x108 aspect ratio");
  assert.ok(css.includes(".barion-badge__strip"), "no .barion-badge__strip rule found in style.css");
  assert.match(css, /\.barion-badge__strip\s*{[^}]*height:\s*\d+px;\s*width:\s*auto;/, "strip must be scaled via a fixed height + width:auto (proportional), never a fixed width+height that could distort it");
});

check("Static Base Pixel loader exists in source control with the official Barion URL and a single init", () => {
  const loaderPath = path.join(FRONTEND_DIR, "js", "barion-pixel.js");
  assert.ok(fs.existsSync(loaderPath), "frontend/js/barion-pixel.js is missing — it must be the authoritative, version-controlled Base Pixel loader");
  const loader = fs.readFileSync(loaderPath, "utf8");
  assert.ok(loader.includes("https://pixel.barion.com/bp.js"), "loader must load the official Barion bp.js");
  assert.equal(countOccurrences(loader, "addBarionPixelId"), 1, "loader must call addBarionPixelId exactly once");
  assert.ok(loader.includes("__mesencsiBarionPixelInitialized"), "loader should guard itself against being executed twice on the same page");
});

check("Storefront (mesencsi.html) references the static Pixel loader exactly once", () => {
  assert.equal(countOccurrences(html, PIXEL_LOADER_TAG), 1, "mesencsi.html must include the static Pixel loader script exactly once");
});

check("forgot-password.html references the static Pixel loader exactly once", () => {
  assert.equal(countOccurrences(forgotHtml, PIXEL_LOADER_TAG), 1, "forgot-password.html must include the static Pixel loader script exactly once");
});

check("reset-password.html references the static Pixel loader exactly once", () => {
  assert.equal(countOccurrences(resetHtml, PIXEL_LOADER_TAG), 1, "reset-password.html must include the static Pixel loader script exactly once");
});

check("No page carries both the static loader and the server-injection slot (no duplicate Base Pixel init)", () => {
  for (const [name, doc] of [
    ["mesencsi.html", html],
    ["forgot-password.html", forgotHtml],
    ["reset-password.html", resetHtml],
  ]) {
    const hasLoader = doc.includes(PIXEL_LOADER_TAG);
    const hasSlot = doc.includes(PIXEL_SLOT);
    assert.ok(hasLoader, `${name} is missing the static Pixel loader`);
    assert.equal(hasSlot, false, `${name} still has the BARION_PIXEL_SLOT marker alongside the static loader — barion_pixel.py would inject a second Base Pixel init into this page`);
  }
});

check("No leftover foreign-template domain remnants (mesencsi.com, bookline.*)", () => {
  assert.equal(/mesencsi\.com/i.test(html), false, "found a leftover 'mesencsi.com' reference (should be mesencsi.hu)");
  assert.equal(/bookline\.(hu|ro|sk)/i.test(html), false, "found a leftover 'bookline.*' template remnant");
});

check("No stale 'bank szerverere' / malformed CVC wording remains", () => {
  assert.equal(html.includes("bank szerverére"), false, "stale 'bank szerverére' wording still present — should read 'Barion fizetési oldalára'");
  assert.equal(/ellenőrző szám utolsó 3 jegye/.test(html), false, "old malformed CVC sentence still present");
  assert.ok(html.includes("CVC/CVV"), "expected the corrected CVC/CVV wording to be present");
});

check("ÁSZF service-provider block has hosting provider, email and phone filled in", () => {
  const aszf = sectionHtml("view-aszf");
  assert.ok(aszf.includes("Rackhost Zrt."), "ÁSZF hosting-provider field is still blank");
  assert.ok(aszf.includes("info@mesencsi.hu"), "ÁSZF Szolgáltató block is missing the email line");
  assert.ok(aszf.includes("+36 20 972 3916"), "ÁSZF Szolgáltató block is missing the phone line");
  assert.ok(aszf.includes("www.mesencsi.hu") && !aszf.includes("mesencsi.com"), "ÁSZF opening sentence should name mesencsi.hu, not mesencsi.com");
});

check("Fizetési tájékoztató page uses accurate Barion redirect + CVC wording", () => {
  const fizetes = sectionHtml("view-fizetes");
  assert.ok(fizetes.includes("Barion fizetési oldalára"), "Fizetési tájékoztató should say the user is redirected to Barion's own payment page");
  assert.ok(fizetes.includes("CVC/CVV"), "Fizetési tájékoztató should use the corrected CVC/CVV wording");
  assert.equal(/bookline/i.test(fizetes), false, "Fizetési tájékoztató still references bookline.* domains");
});

check("Privacy Policy mentions Barion, consistent with the Cookie Policy", () => {
  const privacy = sectionHtml("view-adatkezeles");
  assert.ok(/Barion/.test(privacy), "Privacy Policy (adatkezeles) does not mention Barion at all");
  assert.ok(/GDPR/.test(privacy), "Privacy Policy Barion section should state a GDPR legal basis");
});

check("Cookie Policy documents the Base Barion Pixel actually implemented in code", () => {
  const cookies = sectionHtml("view-sutik");
  assert.ok(/Alap \(Base\) Barion Pixel/.test(cookies), "Cookie Policy no longer documents the Base Barion Pixel");
  assert.ok(/Full Pixel/.test(cookies) && /nem küld/.test(cookies), "Cookie Policy should still state that Full Pixel event tracking is NOT implemented");
});

check("Checkout has mandatory ÁSZF + Privacy consent checkboxes, unchecked by default", () => {
  const termsMatch = html.match(/<input[^>]*id="checkoutTermsAccepted"[^>]*>/);
  const privacyMatch = html.match(/<input[^>]*id="checkoutPrivacyAcknowledged"[^>]*>/);
  assert.ok(termsMatch, "checkoutTermsAccepted checkbox not found");
  assert.ok(privacyMatch, "checkoutPrivacyAcknowledged checkbox not found");
  assert.equal(termsMatch[0].includes("checked"), false, "checkoutTermsAccepted must not carry a default 'checked' attribute");
  assert.equal(privacyMatch[0].includes("checked"), false, "checkoutPrivacyAcknowledged must not carry a default 'checked' attribute");
  assert.ok(termsMatch[0].includes('type="checkbox"'), "checkoutTermsAccepted must be a real checkbox input");
  assert.ok(privacyMatch[0].includes('type="checkbox"'), "checkoutPrivacyAcknowledged must be a real checkbox input");
});

check("Checkout consent checkboxes link to the real ÁSZF and Adatkezelés routes", () => {
  const legalBlock = html.slice(html.indexOf('class="legal-acknowledgements'), html.indexOf('class="legal-acknowledgements') + 600);
  assert.ok(/<a href="\/aszf"[^>]*>ÁSZF-et<\/a>/.test(legalBlock), "ÁSZF link missing or not pointing to /aszf");
  assert.ok(/<a href="\/adatkezeles"[^>]*>adatkezelési tájékoztatót<\/a>/.test(legalBlock), "Adatkezelés link missing or not pointing to /adatkezeles");
});

check("Checkout JS blocks submission when consent checkboxes are unchecked, before any payment call", () => {
  const checkoutJs = fs.readFileSync(path.join(FRONTEND_DIR, "js", "checkout.js"), "utf8");
  const guardIdx = checkoutJs.indexOf("checkoutTermsAccepted");
  assert.ok(guardIdx !== -1, "checkout.js has no reference to checkoutTermsAccepted — consent is not enforced client-side");
  const guardBlock = checkoutJs.slice(guardIdx, guardIdx + 600);
  assert.ok(/if\s*\(\s*!termsAccepted\s*\|\|\s*!privacyAcknowledged\s*\)/.test(guardBlock), "checkout.js must return/block when either consent flag is false");
  assert.ok(guardBlock.includes("return"), "the unchecked-consent branch must return early, not just show a message and continue");
  const fetchIdx = checkoutJs.indexOf("terms_accepted:", guardIdx);
  assert.ok(fetchIdx > guardIdx, "terms_accepted must be read/sent only after the consent guard runs");
});

check("Fejér Vármegyei Békéltető Testület is the named competent conciliation board with full contact details", () => {
  const legal = sectionHtml("view-panaszkezeles");
  assert.ok(legal.includes("Fejér Vármegyei Békéltető Testület"), "competent board name missing from ÁSZF");
  assert.ok(legal.includes("8000 Székesfehérvár, Hosszúsétatér"), "competent board address missing");
  assert.ok(legal.includes("8050 Székesfehérvár, Pf. 357"), "competent board postal/mailing address missing");
  assert.ok(legal.includes("bekeltetes@fmkik.hu"), "competent board email missing");
  assert.ok(legal.includes("+36 22 510 310"), "competent board phone missing");
  assert.ok(legal.includes("https://www.bekeltetesfejer.hu/"), "competent board website missing");
});

if (failures > 0) {
  console.log(failures + " failure(s).");
  process.exit(1);
}
console.log("All checks passed.");
