#!/usr/bin/env node
"use strict";

/**
 * V3.6 professional-editor-layout characterization: admin.html is one giant
 * file with no jsdom/browser test harness in this repo, so real DOM-structure
 * checks live in the manual QA walkthrough instead — this file only asserts
 * on the raw HTML/JS *source text*, which is enough to lock in "every control
 * still exists with its original id/handler" and "the old accordion stack is
 * gone" without needing a DOM. Renderer-level behavior (Cover/Contain, legacy
 * geometry) belongs in storybook-object-canvas-characterization.test.js
 * instead, since that operates on the real shared renderer.
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

console.log("Storybook admin editor V3.7: immersive-editor-layout characterization");

// --- no-duplicate-id scan (catches copy/relocate mistakes) -------------------

check("no duplicate element ids anywhere in the file", () => {
  const ids = [...html.matchAll(/<[a-zA-Z][^>]*\sid="([^"]+)"/g)].map((m) => m[1]);
  const counts = {};
  ids.forEach((id) => {
    counts[id] = (counts[id] || 0) + 1;
  });
  const dupes = Object.entries(counts).filter(([, n]) => n > 1);
  assert.deepEqual(dupes, []);
});

// --- V3.4 removals stay removed ----------------------------------------------

check("Teljes oldal / Háttérként buttons and handlers stay gone", () => {
  assert.equal(html.includes("btnSbImageFillPage"), false);
  assert.equal(html.includes("btnSbImageSendToBack"), false);
  assert.equal(html.includes("Teljes oldal"), false);
  assert.equal(html.includes("Háttérként"), false);
  assert.equal(html.includes("sbFillPageSelectedImage"), false);
  assert.equal(html.includes("sbSendImageToBack"), false);
});

check('old "Elemek" / "Kijelölt elem tulajdonságai" / "Oldalak" / "Oldal tulajdonságai" accordion summaries are gone', () => {
  assert.equal(html.includes('<summary class="sb-editor-acc-summary">Elemek</summary>'), false);
  assert.equal(html.includes('<summary class="sb-editor-acc-summary">Kijelölt elem tulajdonságai</summary>'), false);
  assert.equal(html.includes('<summary class="sb-editor-acc-summary">Oldalak</summary>'), false);
  assert.equal(html.includes('<summary class="sb-editor-acc-summary">Oldal tulajdonságai</summary>'), false);
  assert.equal(html.includes("Kijelölt elem tulajdonságai"), false);
  // The old 2-column accordion-stack grid is fully retired.
  assert.equal(/\.sb-editor-split\s*\{/.test(html), false);
  assert.equal(/\.sb-editor-left\s*\{/.test(html), false);
});

// --- V3.5 new structural containers ------------------------------------------

check("top bar, left rail, main column, context toolbar, canvas workspace, page strip, and right dock all exist", () => {
  assert.equal(html.includes('class="sb-creator-topbar"'), true);
  assert.equal(html.includes('class="sb-ed-body"'), true);
  assert.equal(html.includes('class="sb-ed-rail"'), true);
  assert.equal(html.includes('class="sb-ed-main"'), true);
  assert.equal(html.includes('id="sbEdContextToolbar"'), true);
  assert.equal(html.includes('class="sb-ed-canvas-workspace"'), true);
  assert.match(html, /class="[^"]*\bsb-ed-page-strip\b[^"]*"/);
  assert.equal(html.includes('id="sbEdDock"'), true);
});

check("right dock is collapsible via a dedicated toggle button, wired once at boot", () => {
  assert.equal(html.includes('id="btnSbToggleDock"'), true);
  assert.equal(html.includes('$("btnSbToggleDock")'), true);
  assert.equal(/\.sb-ed-body\.sb-ed-dock-collapsed\s*\{/.test(html), true);
});

check("page settings collapse into a gear-triggered popover reusing sbPropsPanel's native details/summary", () => {
  assert.equal(html.includes('id="sbPropsPanel"'), true);
  assert.equal(html.includes('class="sb-ed-gear-btn"'), true);
  // sbRenderAll()'s hasPages-based hide must still target this exact id.
  assert.match(html, /propsPanel\.hidden\s*=\s*!hasPages/);
});

// --- every control still exists with its original id -------------------------

check("object-creation controls still exist on the left rail (text, image shortcut, decoration, undo/redo, delete)", () => {
  assert.equal(html.includes('id="btnSbAddSecondaryText"'), true);
  assert.equal(html.includes('id="btnSbAddImageShortcut"'), true);
  assert.equal(html.includes('id="sbAddDecorationSelect"'), true);
  assert.equal(html.includes('id="btnSbUndo"'), true);
  assert.equal(html.includes('id="btnSbRedo"'), true);
  assert.equal(html.includes('id="btnSbDeleteSelectedObject"'), true);
});

check("the Kép shortcut still reuses the existing page-image upload handler, no duplicated logic", () => {
  assert.equal(html.includes('$("btnSbAddImageShortcut").addEventListener("click", () => $("btnSbCurPageImg").click());'), true);
  assert.equal(html.includes('id="btnSbCurPageImg"'), true);
  assert.equal(html.includes('id="btnSbCurPageRemoveImg"'), true);
});

check('no-selection hint still reads "Válassz ki egy elemet a szerkesztéshez."', () => {
  assert.equal(html.includes('<p id="sbNoSelectionHint" class="sb-props-note">Válassz ki egy elemet a szerkesztéshez.</p>'), true);
  assert.equal(html.includes("Nincs kijelölt elem. Jelölj ki egy elemet az előnézeten."), false);
});

check("selected-text context-toolbar controls still exist", () => {
  assert.equal(html.includes('id="sbToolbarTextGroup"'), true);
  assert.equal(html.includes('id="btnSbTextBold"'), true);
  assert.equal(html.includes('id="btnSbTextItalic"'), true);
  assert.equal(html.includes('id="btnSbTextUnderline"'), true);
  assert.equal(html.includes('id="sbTextFontSize"'), true);
  assert.equal(html.includes('id="btnSbTextAlignLeft"'), true);
  assert.equal(html.includes('id="btnSbTextHighlight"'), true);
  assert.equal(html.includes('id="sbTextColor"'), true);
});

check("selected-text detailed numeric fields moved to the right-dock Properties section", () => {
  assert.equal(html.includes('id="sbPropsTextGroup"'), true);
  assert.equal(html.includes('id="sbTextPosX"'), true);
  assert.equal(html.includes('id="sbTextPosY"'), true);
  assert.equal(html.includes('id="sbTextSizeW"'), true);
  assert.equal(html.includes('id="sbTextSizeH"'), true);
  // sbUpdateQuickToolbarState() must toggle the new dock wrapper by the same
  // isText condition as the context-toolbar group.
  assert.match(html, /propsTextGroup\.hidden\s*=\s*!isText/);
});

check("selected-image context-toolbar controls still exist, without the removed actions", () => {
  assert.equal(html.includes('id="sbToolbarImageGroup"'), true);
  assert.equal(html.includes('id="sbObjRotationRange"'), true);
  assert.equal(html.includes('id="sbObjOpacityRange"'), true);
  assert.equal(html.includes('id="btnSbImageAlignLeft"'), true);
  assert.equal(html.includes('id="btnSbToggleAspectLock"'), true);
  assert.equal(html.includes('id="btnSbImageFitCover"'), true);
  assert.equal(html.includes('id="btnSbImageFitContain"'), true);
});

check("selected-image detailed numeric fields moved to the right-dock Properties section", () => {
  assert.equal(html.includes('id="sbPropsImageGroup"'), true);
  assert.equal(html.includes('id="sbImageSizeW"'), true);
  assert.equal(html.includes('id="sbImageSizeH"'), true);
  assert.match(html, /propsImageGroup\.hidden\s*=\s*!isImage/);
});

check("selected-decoration context-toolbar controls still exist (size stays inline, per spec)", () => {
  assert.equal(html.includes('id="sbToolbarDecorationGroup"'), true);
  assert.equal(html.includes('id="sbDecoSize"'), true);
});

check("Layers panel still exists in the right dock, untouched", () => {
  assert.equal(html.includes('id="sbLayersList"'), true);
  assert.equal(html.includes('id="btnSbLayerToFront"'), true);
  assert.equal(html.includes('id="btnSbLayerToBack"'), true);
});

check("page-settings popover still exposes audio/image/delete-page controls", () => {
  assert.equal(html.includes('id="btnSbCurPageAud"'), true);
  assert.equal(html.includes('id="sbCurPageAudFile"'), true);
  assert.equal(html.includes('id="btnSbCurPageDelete"'), true);
});

// --- V3.6 new structural containers ------------------------------------------

check("top bar has compact undo/redo shortcuts kept in sync with the rail buttons", () => {
  assert.equal(html.includes('id="btnSbUndoTop"'), true);
  assert.equal(html.includes('id="btnSbRedoTop"'), true);
  assert.equal(html.includes('$("btnSbUndoTop").addEventListener("click", sbUndo);'), true);
  assert.equal(html.includes('$("btnSbRedoTop").addEventListener("click", sbRedo);'), true);
  // Both the rail and top-bar buttons must be updated from one place.
  assert.match(html, /\[\$\("btnSbUndo"\), \$\("btnSbUndoTop"\)\]\.forEach/);
});

check("top bar has a Preview button reusing sbOpenReaderFromList, returning to the editor afterward", () => {
  assert.equal(html.includes('id="btnSbEdPreview"'), true);
  assert.equal(html.includes("sbOpenReaderFromList(bookId)"), true);
  assert.equal(html.includes("sbReaderOpenedFromEditor = true;"), true);
  assert.match(html, /if \(sbReaderOpenedFromEditor\)/);
});

check("cover controls are collapsed into a top-bar overflow menu, not permanently visible", () => {
  assert.equal(html.includes('class="sb-ed-overflow-menu"'), true);
  assert.equal(html.includes('id="btnSbPickCover"'), true);
  assert.equal(html.includes('id="btnSbRemoveCover"'), true);
});

check("hidden book metadata cannot consume canvas height in the authoring view", () => {
  assert.match(html, /\.sb-creator-subbar\[hidden\]\s*\{[^}]*display:\s*none\s*!important;/);
  assert.match(html, /#sbEditorRoot \[hidden\]\s*\{[^}]*display:\s*none\s*!important;/);
});

check("left rail items show a short visible label under each icon", () => {
  assert.equal(html.includes('class="sb-ed-rail-item"'), true);
  assert.equal(html.includes('class="sb-ed-rail-label">Szöveg</span>'), true);
  assert.equal(html.includes('class="sb-ed-rail-label">Kép</span>'), true);
  assert.equal(html.includes('class="sb-ed-rail-label">Törlés</span>'), true);
});

check("dock has a permanent Háttér (background color) section, relocated not duplicated", () => {
  assert.equal(html.includes('id="sbPropsPageBg"'), true);
  // Must appear exactly once — relocated into the dock, not left behind too.
  const occurrences = html.split('id="sbPropsPageBg"').length - 1;
  assert.equal(occurrences, 1);
  assert.match(html, /<h5 class="sb-ed-dock-heading">Háttér<\/h5>/);
});

check("Layers reorder/delete controls are visually hover-revealed, not permanently shown", () => {
  assert.match(html, /\.sb-layer-icon-btn\s*\{[^}]*opacity:\s*0;/);
  assert.match(html, /\.sb-layer-row:hover \.sb-layer-icon-btn,\s*\n\s*\.sb-layer-row\.is-selected \.sb-layer-icon-btn/);
});

check("image layer deletion reuses the persisted image-removal handler", () => {
  const disabledFn = html.match(/function sbLayerDeleteDisabled\(obj\)\s*\{([\s\S]*?)\n\s*\}/);
  assert.ok(disabledFn, "expected sbLayerDeleteDisabled");
  assert.equal(/obj\.type\s*===\s*"image"/.test(disabledFn[1]), false);
  assert.match(html, /if \(obj\.type === "image"\)\s*\{\s*\$\("btnSbCurPageRemoveImg"\)\.click\(\);/);
});

check("Delete and Backspace remove the selected deletable layer outside form fields", () => {
  assert.equal(html.includes("function sbWireEditorDeleteKeysOnce()"), true);
  assert.match(html, /e\.key !== "Delete" && e\.key !== "Backspace"/);
  assert.match(html, /\^\(INPUT\|TEXTAREA\|SELECT\|BUTTON\)\$/);
  assert.equal(html.includes("sbWireEditorDeleteKeysOnce();"), true);
});

check("page-strip thumbnails and toolbar buttons share the unified sb-ed design tokens", () => {
  assert.equal(html.includes("--sb-ed-radius:"), true);
  assert.equal(html.includes("--sb-ed-hover-bg:"), true);
  assert.match(html, /\.sb-quick-toolbar-btn\s*\{[^}]*background:\s*transparent;/);
});

check("page strip container has a horizontal (not vertical) scroll region for many pages", () => {
  const rules = [...html.matchAll(/\.sb-page-thumb-list\s*\{([^}]*)\}/g)].map((m) => m[1]);
  assert.ok(rules.length, "expected a .sb-page-thumb-list rule");
  assert.equal(rules.some((rule) => /overflow-x:\s*auto/.test(rule)), true);
  assert.equal(rules.some((rule) => /flex-direction:\s*column/.test(rule)), false);
});

check("add-page button still exists in the page strip", () => {
  assert.equal(html.includes('id="btnSbAddPage"'), true);
});

check("editor mode becomes an immersive viewport shell without changing the list view", () => {
  assert.match(html, /#view-storybooks-admin\.sb-editor-active\s*\{/);
  assert.match(html, /view\.classList\.add\("sb-editor-active"\)/);
  assert.match(html, /view\.classList\.remove\("sb-editor-active"\)/);
});

check("immersive context toolbar is a compact single row", () => {
  assert.match(html, /#view-storybooks-admin\.sb-editor-active \.sb-ed-context-toolbar\s*\{[^}]*flex:\s*0 0 58px;/);
  assert.match(html, /#view-storybooks-admin\.sb-editor-active \.sb-ed-context-toolbar\s*\{[^}]*flex-wrap:\s*nowrap;/);
  assert.match(html, /#view-storybooks-admin\.sb-editor-active \.sb-ed-context-toolbar \.sb-props-group\s*\{[^}]*flex-direction:\s*row;/);
});

check("canvas remains dominant while the page strip stays horizontal and compact", () => {
  assert.match(html, /#view-storybooks-admin\.sb-editor-active \.sb-ed-page-strip\s*\{[^}]*flex:\s*0 0 166px;/);
  assert.match(html, /#view-storybooks-admin\.sb-editor-active \.sb-ed-page-strip\.is-collapsed\s*\{[^}]*flex-basis:\s*38px;/);
  assert.match(html, /#view-storybooks-admin\.sb-editor-active \.sb-canvas-stage \.sbv2-standard-page\.sbv2-object-canvas\s*\{[^}]*100cqw[^}]*100cqh/);
});

check("page strip toggle defaults collapsed, is accessible, and preserves existing page controls", () => {
  assert.equal(html.includes('id="sbPageStrip"'), true);
  assert.equal(html.includes('id="btnSbTogglePageStrip"'), true);
  assert.equal(html.includes('aria-controls="sbPageStripBody"'), true);
  assert.match(html, /initiallyCollapsed\s*=\s*true/);
  assert.match(html, /sessionStorage\.getItem\("mesencsi_sb_page_strip_collapsed"\)/);
  assert.equal(html.includes('id="btnSbAddPage"'), true);
  assert.equal(html.includes('id="sbPageNavList"'), true);
});

if (failures > 0) {
  console.log(failures + " failure(s).");
  process.exit(1);
}
console.log("All checks passed.");
