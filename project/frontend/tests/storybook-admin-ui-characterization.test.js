#!/usr/bin/env node
"use strict";

/**
 * V3.4 UI-simplification characterization: admin.html is one giant file with
 * no jsdom/browser test harness in this repo, so real DOM-structure checks
 * live in the manual QA walkthrough instead — this file only asserts on the
 * raw HTML/JS *source text*, which is enough to lock in "the removed buttons
 * and their handlers are gone" and "the merged accordion exists" without
 * needing a DOM. Renderer-level behavior (Cover/Contain, legacy geometry)
 * belongs in storybook-object-canvas-characterization.test.js instead, since
 * that operates on the real shared renderer.
 *
 * Pure Node, no browser, no backend: run directly:
 *   node project/frontend/tests/storybook-admin-ui-characterization.test.js
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "..", "admin.html"), "utf8");

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

console.log("Storybook admin editor V3.4: UI simplification characterization");

check("Teljes oldal / Háttérként buttons are gone", () => {
  assert.equal(html.includes("btnSbImageFillPage"), false);
  assert.equal(html.includes("btnSbImageSendToBack"), false);
  assert.equal(html.includes("Teljes oldal"), false);
  assert.equal(html.includes("Háttérként"), false);
});

check("Teljes oldal / Háttérként handlers are gone", () => {
  assert.equal(html.includes("sbFillPageSelectedImage"), false);
  assert.equal(html.includes("sbSendImageToBack"), false);
});

check('"Szerkesztés" accordion exists', () => {
  assert.equal(html.includes('<summary class="sb-editor-acc-summary">Szerkesztés</summary>'), true);
});

check('old "Elemek" accordion is gone', () => {
  assert.equal(html.includes('<summary class="sb-editor-acc-summary">Elemek</summary>'), false);
});

check('old "Kijelölt elem tulajdonságai" accordion is gone', () => {
  assert.equal(html.includes('<summary class="sb-editor-acc-summary">Kijelölt elem tulajdonságai</summary>'), false);
  assert.equal(html.includes("Kijelölt elem tulajdonságai"), false);
});

check("left panel has exactly the four expected accordions, no more, no fewer", () => {
  const summaries = [...html.matchAll(/<summary class="sb-editor-acc-summary">([^<]*)<\/summary>/g)].map((m) => m[1]);
  assert.deepEqual(summaries, ["Oldalak", "Szerkesztés", "Rétegek", "Oldal tulajdonságai"]);
});

check("object-creation controls still exist (text, image shortcut, decoration, undo/redo, delete)", () => {
  assert.equal(html.includes('id="btnSbAddSecondaryText"'), true);
  assert.equal(html.includes('id="btnSbAddImageShortcut"'), true);
  assert.equal(html.includes('id="sbAddDecorationSelect"'), true);
  assert.equal(html.includes('id="btnSbUndo"'), true);
  assert.equal(html.includes('id="btnSbRedo"'), true);
  assert.equal(html.includes('id="btnSbDeleteSelectedObject"'), true);
});

check("the Kép shortcut reuses the existing page-image upload handler, no duplicated logic", () => {
  assert.equal(html.includes('$("btnSbAddImageShortcut").addEventListener("click", () => $("btnSbCurPageImg").click());'), true);
  // The original upload/replace + remove controls still live in "Oldal tulajdonságai".
  assert.equal(html.includes('id="btnSbCurPageImg"'), true);
  assert.equal(html.includes('id="btnSbCurPageRemoveImg"'), true);
});

check('no-selection hint reads the new "Válassz ki egy elemet a szerkesztéshez." text', () => {
  assert.equal(html.includes('<p id="sbNoSelectionHint" class="sb-props-note">Válassz ki egy elemet a szerkesztéshez.</p>'), true);
  assert.equal(html.includes("Nincs kijelölt elem. Jelölj ki egy elemet az előnézeten."), false);
});

check("selected-text property controls still render", () => {
  assert.equal(html.includes('id="sbToolbarTextGroup"'), true);
  assert.equal(html.includes('id="btnSbTextBold"'), true);
  assert.equal(html.includes('id="btnSbTextItalic"'), true);
  assert.equal(html.includes('id="btnSbTextUnderline"'), true);
  assert.equal(html.includes('id="sbTextFontSize"'), true);
  assert.equal(html.includes('id="btnSbTextAlignLeft"'), true);
  assert.equal(html.includes('id="btnSbTextHighlight"'), true);
  assert.equal(html.includes('id="sbTextColor"'), true);
});

check("selected-image property controls still render, without the removed actions", () => {
  assert.equal(html.includes('id="sbToolbarImageGroup"'), true);
  assert.equal(html.includes('id="sbObjRotationRange"'), true);
  assert.equal(html.includes('id="sbObjOpacityRange"'), true);
  assert.equal(html.includes('id="sbImageSizeW"'), true);
  assert.equal(html.includes('id="sbImageSizeH"'), true);
  assert.equal(html.includes('id="btnSbImageAlignLeft"'), true);
  assert.equal(html.includes('id="btnSbToggleAspectLock"'), true);
  assert.equal(html.includes('id="btnSbImageFitCover"'), true);
  assert.equal(html.includes('id="btnSbImageFitContain"'), true);
});

check("selected-decoration property controls still render", () => {
  assert.equal(html.includes('id="sbToolbarDecorationGroup"'), true);
  assert.equal(html.includes('id="sbDecoSize"'), true);
});

check("Layers panel still exists, untouched", () => {
  assert.equal(html.includes('id="sbLayersList"'), true);
  assert.equal(html.includes('id="btnSbLayerToFront"'), true);
  assert.equal(html.includes('id="btnSbLayerToBack"'), true);
});

check("page list container still has its bounded scroll region for many pages", () => {
  const m = html.match(/\.sb-page-thumb-list\s*\{([^}]*)\}/);
  assert.ok(m, "expected a .sb-page-thumb-list rule");
  assert.match(m[1], /overflow-y:\s*auto/);
  assert.match(m[1], /max-height:\s*240px/);
});

if (failures > 0) {
  console.log(failures + " failure(s).");
  process.exit(1);
}
console.log("All checks passed.");
