#!/usr/bin/env node
"use strict";

/**
 * Characterization test for the admin-editor V2 groundwork: storybook-reader.js's
 * shared page builders gained an additive `opts.editable` flag (data-sb-editable-zone
 * hooks for the WYSIWYG canvas). This proves the flag is purely additive — the public
 * reader's actual output (opts.editable unset) is byte-identical to before the change,
 * and only differs from the editable variant by the new data attributes, never by
 * layout/content.
 *
 * Pure Node, no browser, no backend, no framework — run directly:
 *   node project/frontend/tests/storybook-editable-characterization.test.js
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadReaderModule() {
  const src = fs.readFileSync(path.join(__dirname, "..", "storybook-reader.js"), "utf8");
  const sandbox = { window: {} };
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: "storybook-reader.js" });
  return sandbox.window.MesencsiStorybookReader;
}

const PAGE_TEXT_ONLY = {
  id: 1,
  page_index: 1,
  title: null,
  body_text: "Egyszer volt, hol nem volt.",
  image_url: null,
  audio_url: null,
  image_placement: "none",
};

const PAGE_WITH_IMAGE = {
  id: 2,
  page_index: 2,
  title: "Cím",
  body_text: "Szöveg a kép mellett.",
  image_url: "/media/uploads/storybooks/1/x.png",
  audio_url: null,
  image_placement: "left",
};

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

console.log("storybook-reader.js editable passthrough (characterization)");

check("public (non-editable) output has no editable hooks", () => {
  const SBR = loadReaderModule();
  const html = SBR.buildV2LeftPageHtml(PAGE_WITH_IMAGE, {}, { pageNumber: 2 });
  assert.equal(html.includes("data-sb-editable-zone"), false);
  assert.equal(html.includes("sbv2-zone--page-image"), true);
  assert.equal(html.includes("sbv2-zone--page-text"), true);
});

check("editable output adds hooks without changing zone classes/content", () => {
  const SBR = loadReaderModule();
  const plain = SBR.buildV2LeftPageHtml(PAGE_WITH_IMAGE, {}, { pageNumber: 2 });
  const editable = SBR.buildV2LeftPageHtml(PAGE_WITH_IMAGE, { editable: true }, { pageNumber: 2 });

  assert.equal(editable.includes('data-sb-editable-zone="image"'), true);
  assert.equal(editable.includes('data-sb-editable-zone="text"'), true);

  const stripped = editable.replace(/ data-sb-editable-zone="(image|text)"/g, "");
  assert.equal(stripped, plain);
});

check("text-only page: editable flag is a no-op on the (absent) image zone", () => {
  const SBR = loadReaderModule();
  const plain = SBR.buildV2RightPageHtml(PAGE_TEXT_ONLY, {}, { pageNumber: 1 });
  const editable = SBR.buildV2RightPageHtml(PAGE_TEXT_ONLY, { editable: true }, { pageNumber: 1 });
  assert.equal(plain.includes("sbv2-zone--page-image"), false);
  assert.equal(editable.includes("sbv2-zone--page-image"), false);
  const stripped = editable.replace(/ data-sb-editable-zone="(image|text)"/g, "");
  assert.equal(stripped, plain);
});

check("advanced/custom-layout pages are untouched by the editable flag (different code path)", () => {
  const SBR = loadReaderModule();
  const advancedPage = Object.assign({}, PAGE_WITH_IMAGE, {
    image_x_percent: 10,
    image_y_percent: 6,
    image_width_percent: 80,
    image_height_percent: 34,
  });
  const plain = SBR.buildV2LeftPageHtml(advancedPage, {}, { pageNumber: 2 });
  const editable = SBR.buildV2LeftPageHtml(advancedPage, { editable: true }, { pageNumber: 2 });
  assert.equal(editable, plain);
  assert.equal(plain.includes("data-sb-editable-zone"), false);
});

if (failures > 0) {
  console.log(failures + " failure(s).");
  process.exit(1);
}
console.log("All checks passed.");
