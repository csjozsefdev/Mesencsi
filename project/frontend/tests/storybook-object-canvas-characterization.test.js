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

check("opacity < 1 renders as an inline style declaration", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
      { id: "img-1", type: "image", x: 0, y: 0, w: 40, h: 40, rotation: 0, opacity: 0.5 },
    ],
  };
  const page = { body_text: "x", image_url: "y.png" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.equal(html.includes("opacity:0.5;"), true);
});

["1", "1.0", undefined].forEach((opacity) => {
  check("opacity=" + opacity + " omits the opacity declaration (no regression for existing pages)", () => {
    const SBR = loadReaderModule();
    const obj = { id: "img-1", type: "image", x: 0, y: 0, w: 40, h: 40, rotation: 0 };
    if (opacity !== undefined) obj.opacity = Number(opacity);
    const layout = {
      version: 1,
      objects: [
        { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
        obj,
      ],
    };
    const page = { body_text: "x", image_url: "y.png" };
    const html = SBR.buildObjectCanvasHtml(layout, page, opts);
    assert.equal(html.includes("opacity:"), false);
  });
});

check("rotation renders continuously — a non-90-multiple angle is never snapped to a step", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
      { id: "img-1", type: "image", x: 0, y: 0, w: 40, h: 40, rotation: 37 },
    ],
  };
  const page = { body_text: "x", image_url: "y.png" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.equal(html.includes("transform:rotate(37deg);"), true);
});

// --- V3.2: selection-based rich text (obj.html) -----------------------------

check("obj.html renders verbatim (unescaped) for primary text", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0, html: "<strong>bold</strong> plain" },
    ],
  };
  const page = { body_text: "bold plain" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.equal(html.includes("<strong>bold</strong> plain"), true);
});

check("obj.html renders verbatim (unescaped) for secondary text", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
      {
        id: "cap-1",
        type: "text",
        role: "secondary",
        x: 0,
        y: 60,
        w: 50,
        h: 20,
        rotation: 0,
        content: "highlighted",
        html: "<mark>highlighted</mark>",
      },
    ],
  };
  const page = { body_text: "x" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.equal(html.includes("<mark>highlighted</mark>"), true);
});

check("a legacy object with no html key renders exactly as escaped plain text (regression lock)", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0, format: { bold: true } },
    ],
  };
  const page = { body_text: "<script>not real markup, just text</script>" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  // The plain path always HTML-escapes body_text — proves obj.html absence
  // never changes the old behavior, even if the plain text itself looks
  // tag-like.
  assert.equal(html.includes("&lt;script>"), true);
  assert.equal(html.includes("<script>"), false);
  assert.equal(html.includes("font-weight:700;"), true);
});

check("an unsafe obj.html value falls back to safe plain rendering at render time", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0, html: "<script>alert(1)</script>" },
    ],
  };
  const page = { body_text: "fallback text" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.equal(html.includes("<script>"), false);
  assert.equal(html.includes("fallback text"), true);
});

// --- V3.2: full-page image / background mode --------------------------------

check("fill-page image renders 0/0/100/100 geometry with object-fit:cover", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
      { id: "img-1", type: "image", x: 0, y: 0, w: 100, h: 100, rotation: 0, image: { fit: "cover" } },
    ],
  };
  const page = { body_text: "x", image_url: "bg.png" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.equal(html.includes("left:0%;top:0%;width:100%;height:100%;"), true);
  assert.equal(html.includes("object-fit:cover"), true);
});

check("contain fit mode renders object-fit:contain", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
      { id: "img-1", type: "image", x: 55, y: 5, w: 40, h: 50, rotation: 0, image: { fit: "contain" } },
    ],
  };
  const page = { body_text: "x", image_url: "y.png" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.equal(html.includes("object-fit:contain"), true);
});

check("z-order: array order drives DOM order — image first renders before text", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "img-1", type: "image", x: 0, y: 0, w: 100, h: 100, rotation: 0 },
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
    ],
  };
  const page = { body_text: "x", image_url: "bg.png" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.ok(html.indexOf("sbv2-obj--image") < html.indexOf("sbv2-obj--text"), "image markup precedes text markup");
});

check("z-order: text first renders before image", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
      { id: "img-1", type: "image", x: 0, y: 0, w: 100, h: 100, rotation: 0 },
    ],
  };
  const page = { body_text: "x", image_url: "bg.png" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  assert.ok(html.indexOf("sbv2-obj--text") < html.indexOf("sbv2-obj--image"), "text markup precedes image markup");
});

check("z-order: arbitrary 3-item permutation (decoration, image, text) drives DOM order exactly", () => {
  const SBR = loadReaderModule();
  const layout = {
    version: 1,
    objects: [
      { id: "deco-1", type: "decoration", x: 10, y: 10, w: 8, h: 8, rotation: 0, decoration: { glyph: "⭐" } },
      { id: "img-1", type: "image", x: 0, y: 0, w: 100, h: 100, rotation: 0 },
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
    ],
  };
  const page = { body_text: "x", image_url: "bg.png" };
  const html = SBR.buildObjectCanvasHtml(layout, page, opts);
  const decoIdx = html.indexOf("sbv2-obj--decoration");
  const imgIdx = html.indexOf("sbv2-obj--image");
  const textIdx = html.indexOf("sbv2-obj--text");
  assert.ok(decoIdx < imgIdx && imgIdx < textIdx, "DOM order must be decoration, image, text — not sorted by type");
});

// --- V3.3: Layers panel — name is admin-only organizational metadata --------

check("obj.name is a pure passthrough — present or absent, it never changes rendered HTML", () => {
  const SBR = loadReaderModule();
  const page = { body_text: "x", image_url: "y.png" };
  const layoutWithout = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0 },
      { id: "img-1", type: "image", x: 0, y: 0, w: 40, h: 40, rotation: 0 },
    ],
  };
  const layoutWith = {
    version: 1,
    objects: [
      { id: "primary-text", type: "text", role: "primary", x: 0, y: 0, w: 50, h: 50, rotation: 0, name: "Cím" },
      { id: "img-1", type: "image", x: 0, y: 0, w: 40, h: 40, rotation: 0, name: "Háttérkép" },
    ],
  };
  const htmlWithout = SBR.buildObjectCanvasHtml(layoutWithout, page, opts);
  const htmlWith = SBR.buildObjectCanvasHtml(layoutWith, page, opts);
  assert.equal(htmlWith, htmlWithout);
  assert.equal(htmlWith.includes("Cím"), false);
  assert.equal(htmlWith.includes("Háttérkép"), false);
});

if (failures > 0) {
  console.log(failures + " failure(s).");
  process.exit(1);
}
console.log("All checks passed.");
