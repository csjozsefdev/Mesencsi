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

check("Exactly one authoritative Barion Pixel injection point (server-side slot)", () => {
  assert.equal(countOccurrences(html, "<!-- BARION_PIXEL_SLOT -->"), 1, "expected exactly one BARION_PIXEL_SLOT placeholder");
});

check("No stray static barion-pixel.js script tag in version-controlled frontend", () => {
  assert.equal(/<script[^>]+barion-pixel\.js/i.test(html), false, "found a <script src=...barion-pixel.js> tag — this would duplicate the server-injected Base Pixel");
  const strayFile = path.join(FRONTEND_DIR, "js", "barion-pixel.js");
  assert.equal(fs.existsSync(strayFile), false, "a static js/barion-pixel.js file exists in the repo — remove it, the server-side injection in barion_pixel.py is authoritative");
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
