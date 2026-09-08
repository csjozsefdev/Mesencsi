#!/usr/bin/env node
"use strict";

/**
 * Barion merchant-acceptance frontend characterization: guards the fixes made after the
 * Barion compliance audit (branding presence, single authoritative Pixel implementation,
 * Privacy Policy/Cookie Policy consistency, no leftover foreign-template copy).
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

check("Barion logo asset file exists on disk and is a real SVG", () => {
  const logoPath = path.join(FRONTEND_DIR, "images", "barion-logo.svg");
  assert.ok(fs.existsSync(logoPath), "images/barion-logo.svg is missing");
  const svg = fs.readFileSync(logoPath, "utf8");
  assert.ok(svg.trim().startsWith("<svg"), "images/barion-logo.svg does not look like a valid SVG file");
  assert.ok(svg.length > 500, "images/barion-logo.svg looks truncated/empty");
});

check("Barion logo is referenced on the site-wide footer (renders on the homepage)", () => {
  const footer = html.slice(html.indexOf('class="site-footer"'), html.indexOf("</footer>"));
  assert.ok(footer.includes("/images/barion-logo.svg"), "footer does not reference the Barion logo asset");
  assert.ok(footer.includes('class="barion-badge"'), "footer Barion badge markup missing");
});

check("Barion logo is referenced in the checkout/payment area", () => {
  const disclosure = html.slice(
    html.indexOf('class="checkout-payment-disclosure"'),
    html.indexOf('class="checkout-payment-disclosure"') + 400
  );
  assert.ok(disclosure.includes("/images/barion-logo.svg"), "checkout payment disclosure does not reference the Barion logo asset");
});

check("Barion badge has non-intrusive sizing rules in style.css", () => {
  assert.ok(css.includes(".barion-badge__logo"), "no .barion-badge__logo rule found in style.css");
  assert.match(css, /\.barion-badge__logo\s*{[^}]*height:\s*1[5-8]px/, "badge logo height should stay small (15-18px), not oversized");
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

if (failures > 0) {
  console.log(failures + " failure(s).");
  process.exit(1);
}
console.log("All checks passed.");
