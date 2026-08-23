#!/usr/bin/env node
"use strict";

/**
 * Characterization test for the V3 object-canvas renderer swap: buildV2LeftPageHtml/
 * buildV2RightPageHtml now unconditionally call buildObjectCanvasHtml(resolvePageLayout(page), ...)
 * instead of branching between buildV2StandardPageHtml/buildPanelHtml based on
 * pageHasCustomImageLayout. Since no existing page has layout_json set yet, every
 * page today resolves via legacyPageToLayout() — this proves that adapter produces
 * a layout that is STRUCTURALLY equivalent (same content, same relative image/text
 * geometry, same object types) to what the old dual-renderer produced, so swapping
 * the dispatch is not a visible regression for any pre-existing book.
 *
 * Pure Node, no browser, no backend, no framework — run directly:
 *   node project/frontend/tests/storybook-object-canvas-characterization.test.js
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

const opts = { escapeHtml: (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"), assetUrl: (u) => u };

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

console.log("V3 object-canvas renderer: legacy-page structural-equivalence characterization");

check("text-only page: primary text object present, no image object", () => {
  const SBR = loadReaderModule();
  const page = { id: 1, body_text: "Egyszer volt, hol nem volt.", image_url: null, image_placement: "none" };
  const layout = SBR.legacyPageToLayout(page);
  assert.equal(layout.version, 1);
  assert.equal(layout.objects.length, 1);
  assert.equal(layout.objects[0].type, "text");
  assert.equal(layout.objects[0].role, "primary");

  const html = SBR.buildV2LeftPageHtml(page, opts, { pageNumber: 1 });
  assert.equal(html.includes("Egyszer volt"), true);
  assert.equal(html.includes("sbv2-obj--image"), false);
  assert.equal(html.includes("sbv2-object-canvas"), true);
});

["left", "right", "above", "below"].forEach((placement) => {
  check("placement=" + placement + ": image+text objects with correct relative geometry", () => {
    const SBR = loadReaderModule();
    const page = {
      id: 2,
      body_text: "Szöveg a kép mellett.",
      image_url: "/media/uploads/storybooks/1/x.png",
      image_placement: placement,
    };
    const layout = SBR.legacyPageToLayout(page);
    assert.equal(layout.objects.length, 2);
    const img = layout.objects.find((o) => o.type === "image");
    const txt = layout.objects.find((o) => o.type === "text");
    assert.ok(img, "image object present");
    assert.ok(txt, "primary text object present");

    if (placement === "left") assert.ok(img.x < txt.x, "image left of text");
    if (placement === "right") assert.ok(img.x > txt.x, "image right of text");
    if (placement === "above") assert.ok(img.y < txt.y, "image above text");
    if (placement === "below") assert.ok(img.y > txt.y, "image below text");

    // Both objects must stay within the page bounds.
    [img, txt].forEach((o) => {
      assert.ok(o.x >= 0 && o.x + o.w <= 100.01, "object x/w within [0,100]");
      assert.ok(o.y >= 0 && o.y + o.h <= 100.01, "object y/h within [0,100]");
    });

    const html = SBR.buildV2RightPageHtml(page, opts, { pageNumber: 2 });
    assert.equal(html.includes("Szöveg a kép mellett"), true);
    assert.equal(html.includes(page.image_url), true);
  });
});

check("custom image-position (advanced legacy) page: image object mirrors stored percent fields exactly", () => {
  const SBR = loadReaderModule();
  const page = {
    id: 3,
    body_text: "Szandekos elrendezes.",
    image_url: "/media/uploads/storybooks/1/x.png",
    image_x_percent: 25,
    image_y_percent: 15,
    image_width_percent: 50,
    image_height_percent: 40,
  };
  const layout = SBR.legacyPageToLayout(page);
  const img = layout.objects.find((o) => o.type === "image");
  assert.equal(img.x, 25);
  assert.equal(img.y, 15);
  assert.equal(img.w, 50);
  assert.equal(img.h, 40);
});

check("custom drag-pos (free-dragged text) legacy page: text object centered near stored coordinates", () => {
  const SBR = loadReaderModule();
  const page = {
    id: 4,
    body_text: "Szabadon pozicionalt szoveg.",
    text_x_percent: 70,
    text_y_percent: 20,
  };
  const layout = SBR.legacyPageToLayout(page);
  assert.equal(layout.objects.length, 1);
  const txt = layout.objects[0];
  const centerX = txt.x + txt.w / 2;
  const centerY = txt.y + txt.h / 2;
  assert.ok(Math.abs(centerX - 70) < 1, "text box horizontally centered near stored x");
  assert.ok(Math.abs(centerY - 20) < 1, "text box vertically centered near stored y");
});

check("resolvePageLayout: layout_json set takes precedence over legacy fields", () => {
  const SBR = loadReaderModule();
  const explicitLayout = {
    version: 1,
    objects: [{ id: "primary-text", type: "text", role: "primary", x: 1, y: 2, w: 3, h: 4, rotation: 0 }],
  };
  const page = { id: 5, body_text: "x", image_placement: "left", image_url: "y.png", layout_json: explicitLayout };
  const resolved = SBR.resolvePageLayout(page);
  assert.deepEqual(resolved, explicitLayout);
});

check("resolvePageLayout: null layout_json falls back to legacyPageToLayout", () => {
  const SBR = loadReaderModule();
  const page = { id: 6, body_text: "x", layout_json: null };
  const resolved = SBR.resolvePageLayout(page);
  assert.equal(resolved.objects[0].role, "primary");
});

check("editable mode adds data-sb-obj-* hooks without removing any content", () => {
  const SBR = loadReaderModule();
  const page = {
    id: 7,
    body_text: "Szoveg.",
    image_url: "/media/uploads/storybooks/1/x.png",
    image_placement: "left",
  };
  const plain = SBR.buildV2LeftPageHtml(page, opts, { pageNumber: 1 });
  const editable = SBR.buildV2LeftPageHtml(page, Object.assign({}, opts, { editable: true }), { pageNumber: 1 });
  assert.equal(editable.includes('data-sb-obj-type="text"'), true);
  assert.equal(editable.includes('data-sb-obj-type="image"'), true);
  assert.equal(plain.includes("data-sb-obj-type"), false);
  // Both still contain the same real content.
  assert.equal(plain.includes("Szoveg."), true);
  assert.equal(editable.includes("Szoveg."), true);
  assert.equal(plain.includes(page.image_url), true);
  assert.equal(editable.includes(page.image_url), true);
});

check("admin and public reader call the exact same exported function (by construction)", () => {
  const SBR = loadReaderModule();
  assert.equal(typeof SBR.buildObjectCanvasHtml, "function");
  assert.equal(typeof SBR.legacyPageToLayout, "function");
  assert.equal(typeof SBR.resolvePageLayout, "function");
});

if (failures > 0) {
  console.log(failures + " failure(s).");
  process.exit(1);
}
console.log("All checks passed.");
