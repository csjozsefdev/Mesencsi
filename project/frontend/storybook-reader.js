/**
 * Mesencsi digitális mesekönyv olvasó — közös modul bolt + admin számára.
 * API: window.MesencsiStorybookReader
 */
(function () {
  "use strict";

  const BOX_IDS = new Set([
    "card",
    "rounded",
    "cloud",
    "bubble",
    "parchment",
    "letter",
    "star",
    "storyboard",
    "bookpage",
    "magic_frame",
  ]);

  function defaultEscape(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function boxStyleClass(styleId) {
    const raw = String(styleId || "card")
      .trim()
      .toLowerCase();
    const id = BOX_IDS.has(raw) ? raw : "card";
    return "sb-box-" + id.replace(/_/g, "-");
  }

  function parsePercent(v) {
    if (v == null || v === "") return null;
    const n = Number(v);
    if (!Number.isFinite(n)) return null;
    return Math.max(0, Math.min(100, n));
  }

  function normPageLayout(p) {
    p = p || {};
    let v = String(p.text_position_vertical || "center").toLowerCase();
    if (v !== "top" && v !== "bottom") v = "center";
    let h = String(p.text_position_horizontal || "center").toLowerCase();
    if (h !== "left" && h !== "right") h = "center";
    // text_box_style was removed (always transparent in the real reader) — the
    // legacy/advanced canvas path still calls boxStyleClass(), which now always
    // resolves to the single fixed "card" class regardless of input.
    return { v: v, h: h, style: "card" };
  }

  function normImagePlacement(p) {
    const raw = String((p && p.image_placement) || "none").toLowerCase();
    if (raw === "left" || raw === "right" || raw === "above" || raw === "below") return raw;
    return "none";
  }

  // Mirrors backend STORYBOOK_TEXT_ONLY_MAX_CHARS / STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS
  // (models.py) — measured against the real V2 reader CSS geometry so a page can
  // never overflow. Keep these two values in sync with the backend constants.
  const STORYBOOK_TEXT_ONLY_MAX_CHARS = 600;
  const STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS = 150;

  function storybookPageTextLimit(hasImage) {
    return hasImage ? STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS : STORYBOOK_TEXT_ONLY_MAX_CHARS;
  }

  function pageHasCustomDragPos(p) {
    return parsePercent(p && p.text_x_percent) != null && parsePercent(p && p.text_y_percent) != null;
  }

  function pageHasCustomImageLayout(p) {
    return (
      parsePercent(p && p.image_x_percent) != null &&
      parsePercent(p && p.image_y_percent) != null &&
      parsePercent(p && p.image_width_percent) != null
    );
  }

  function panelOptsHelpers(opts) {
    opts = opts || {};
    return {
      esc: typeof opts.escapeHtml === "function" ? opts.escapeHtml : defaultEscape,
      assetUrl:
        typeof opts.assetUrl === "function"
          ? opts.assetUrl
          : function (u) {
              return u;
            },
    };
  }

  function buildPageAudioHtml(page, opts) {
    const h = panelOptsHelpers(opts);
    page = page || {};
    if (!page.audio_url) return "";
    const au = h.assetUrl(String(page.audio_url).trim());
    if (!au) return "";
    return (
      '<div class="sbv2-zone sbv2-zone--audio sb-read-audio-wrap">' +
      '<audio controls preload="metadata" src="' +
      h.esc(au) +
      '"></audio></div>'
    );
  }

  function buildFolioHtml(pageNumber) {
    const n = Math.floor(Number(pageNumber));
    if (!Number.isFinite(n) || n < 1) return "";
    return (
      '<footer class="sbv2-zone sbv2-zone--folio" aria-label="Oldalszám">' +
      "<span>" +
      n +
      "</span></footer>"
    );
  }

  function resolveV2PageArgs(page, optsOrContext, context) {
    let opts;
    let ctx;
    if (arguments.length === 2) {
      ctx = optsOrContext || {};
      opts = ctx.opts || {};
    } else {
      opts = optsOrContext || {};
      ctx = context || {};
    }
    return { page: page || {}, opts: opts, context: ctx };
  }

  // ----- V3 object-canvas renderer -----
  //
  // One rendering function for every page, used unconditionally by both the
  // admin editor canvas and the public reader — no more branching on whether
  // a page has "custom" layout data. A page's layout is either its own
  // layout_json (set once an admin saves it in the object-canvas editor) or,
  // for every page that predates this feature, an in-memory-only equivalent
  // synthesized by legacyPageToLayout() from the legacy enum/percent fields —
  // never persisted, so opening/viewing a legacy page never mutates it.

  const STORYBOOK_LAYOUT_FONT_SIZE_PX = { s: 14, m: 17, l: 21, xl: 26 };

  function _safeHexColor(v) {
    return typeof v === "string" && /^#[0-9a-fA-F]{3,8}$/.test(v) ? v : null;
  }

  function _layoutRectStyle(obj) {
    obj = obj || {};
    const x = Number(obj.x);
    const y = Number(obj.y);
    const w = Number(obj.w);
    const hh = Number(obj.h);
    const rot = Number(obj.rotation) || 0;
    let style =
      "position:absolute;left:" +
      (Number.isFinite(x) ? x : 0) +
      "%;top:" +
      (Number.isFinite(y) ? y : 0) +
      "%;width:" +
      (Number.isFinite(w) ? w : 10) +
      "%;height:" +
      (Number.isFinite(hh) ? hh : 10) +
      "%;";
    if (rot) style += "transform:rotate(" + rot + "deg);";
    if (obj.opacity != null) {
      const op = Number(obj.opacity);
      if (Number.isFinite(op) && op < 1) style += "opacity:" + Math.max(0, Math.min(1, op)) + ";";
    }
    return style;
  }

  function _layoutTextFormatStyle(fmt) {
    fmt = fmt || {};
    const px = STORYBOOK_LAYOUT_FONT_SIZE_PX[fmt.fontSize] || STORYBOOK_LAYOUT_FONT_SIZE_PX.m;
    let style = "font-size:" + px + "px;";
    if (fmt.bold) style += "font-weight:700;";
    if (fmt.italic) style += "font-style:italic;";
    if (fmt.underline) style += "text-decoration:underline;";
    style += "text-align:" + (fmt.align === "center" || fmt.align === "right" ? fmt.align : "left") + ";";
    const color = _safeHexColor(fmt.color);
    if (color) style += "color:" + color + ";";
    const highlight = _safeHexColor(fmt.highlight);
    if (highlight) style += "background-color:" + highlight + ";";
    return style;
  }

  // Render-time defense-in-depth for obj.html (the optional sanitized rich-text
  // fragment) — mirrors, but does not replace, the authoritative server-side
  // allowlist validator (_rich_text_html_ok in models.py). Same pattern as
  // _safeHexColor being re-checked here even though the server already
  // validated it: if this string contains anything outside the small allowed
  // set (bare <strong>/<em>/<u>/<mark>, or <span style="color:#hex">), treat
  // it as unsafe and fall back to plain rendering rather than trust it.
  const _RICH_TEXT_ALLOWED_TAG_RE =
    /<\/?(strong|em|u|mark)>|<span style="color:#[0-9a-fA-F]{3,8}">|<\/span>/g;

  function _isRichTextHtmlSafe(htmlStr) {
    if (typeof htmlStr !== "string" || !htmlStr) return false;
    const stripped = htmlStr.replace(_RICH_TEXT_ALLOWED_TAG_RE, "");
    return stripped.indexOf("<") === -1 && stripped.indexOf(">") === -1;
  }

  function buildLayoutObjectHtml(obj, page, opts) {
    const h = panelOptsHelpers(opts);
    const editable = !!(opts && opts.editable);
    obj = obj || {};
    page = page || {};
    const rectStyle = _layoutRectStyle(obj);
    const dataAttrs = editable
      ? ' data-sb-obj-id="' +
        h.esc(String(obj.id || "")) +
        '" data-sb-obj-type="' +
        h.esc(String(obj.type || "")) +
        '"'
      : "";

    if (obj.type === "text") {
      const isPrimary = obj.role === "primary";
      const rawContent = isPrimary ? page.body_text || "" : obj.content || "";
      const hasContent = String(rawContent).trim().length > 0;
      // obj.html is an optional additive field (sanitized on the client before
      // persisting, validated authoritatively by _rich_text_html_ok server-side)
      // carrying per-range formatting (bold/italic/underline/highlight/color)
      // that a single whole-object `format` style can't express. Absent or
      // unsafe -> the exact old plain-escaped path, so every pre-existing
      // object renders byte-for-byte unchanged.
      const richHtml = typeof obj.html === "string" ? obj.html : "";
      const useRichHtml = richHtml.trim().length > 0 && _isRichTextHtmlSafe(richHtml);
      // Editable: leave a truly empty div when there's no content, so the
      // CSS-only placeholder (:empty::before) can show through. Read-only:
      // keep the old &nbsp; fallback so an empty box doesn't collapse.
      const body = useRichHtml
        ? richHtml
        : hasContent
          ? h.esc(String(rawContent))
          : editable
            ? ""
            : "&nbsp;";
      const fmtStyle = _layoutTextFormatStyle(obj.format);
      const roleAttr = editable ? ' data-sb-obj-role="' + (isPrimary ? "primary" : "secondary") + '"' : "";
      const editAttrs = editable
        ? ' contenteditable="true" spellcheck="true" role="textbox" aria-multiline="true" aria-label="Oldal szövege"'
        : "";
      return (
        '<div class="sbv2-obj sbv2-obj--text' +
        (isPrimary ? " sbv2-obj--text-primary" : " sbv2-obj--text-secondary") +
        '" style="' +
        rectStyle +
        '"' +
        dataAttrs +
        roleAttr +
        '><div class="sb-canvas-text"' +
        editAttrs +
        ' style="' +
        fmtStyle +
        '">' +
        body +
        "</div></div>"
      );
    }
    if (obj.type === "image") {
      if (!page.image_url) return "";
      const u = h.assetUrl(String(page.image_url).trim());
      if (!u) return "";
      const fit = obj.image && obj.image.fit === "cover" ? "cover" : "contain";
      return (
        '<figure class="sbv2-obj sbv2-obj--image" style="' +
        rectStyle +
        '"' +
        dataAttrs +
        '><img src="' +
        h.esc(u) +
        '" alt="" loading="lazy" decoding="async" style="object-fit:' +
        fit +
        '" onerror="this.style.display=\'none\'"/></figure>'
      );
    }
    if (obj.type === "decoration") {
      const glyph = (obj.decoration && obj.decoration.glyph) || "";
      return (
        '<div class="sbv2-obj sbv2-obj--decoration" style="' +
        rectStyle +
        '"' +
        dataAttrs +
        '><span class="sbv2-obj-decoration-glyph">' +
        h.esc(String(glyph)) +
        "</span></div>"
      );
    }
    return "";
  }

  /**
   * Renders a page from a resolved layout ({version, objects}) — the ONE
   * function both the admin object-canvas editor and the public reader call.
   * @param {{version:number, objects:object[]}} layout
   * @param {object} page
   * @param {object} [opts] — opts.editable=true adds data-sb-obj-* hooks only.
   * @param {{pageNumber?: number}} [context]
   */
  function buildObjectCanvasHtml(layout, page, opts, context) {
    const h = panelOptsHelpers(opts);
    page = page || {};
    context = context || {};
    const objects = layout && Array.isArray(layout.objects) ? layout.objects : [];

    let titleHtml = "";
    if (page.title) {
      titleHtml =
        '<header class="sbv2-zone sbv2-zone--title">' +
        '<h2 class="sbv2-page-title">' +
        h.esc(String(page.title)) +
        "</h2></header>";
    }
    const objectsHtml = objects.map((obj) => buildLayoutObjectHtml(obj, page, opts)).join("");

    return (
      '<div class="sbv2-standard-page sbv2-object-canvas">' +
      titleHtml +
      '<div class="sbv2-object-canvas-stage">' +
      objectsHtml +
      "</div>" +
      buildPageAudioHtml(page, opts) +
      buildFolioHtml(context.pageNumber) +
      "</div>"
    );
  }

  function _legacyPlacementRects(placement) {
    switch (placement) {
      case "left":
        return { image: { x: 0, y: 0, w: 42, h: 100 }, text: { x: 44, y: 0, w: 56, h: 100 } };
      case "right":
        return { image: { x: 58, y: 0, w: 42, h: 100 }, text: { x: 0, y: 0, w: 56, h: 100 } };
      case "above":
        return { image: { x: 0, y: 0, w: 100, h: 40 }, text: { x: 0, y: 42, w: 100, h: 58 } };
      case "below":
        return { image: { x: 0, y: 58, w: 100, h: 40 }, text: { x: 0, y: 0, w: 100, h: 56 } };
      default:
        return { image: { x: 0, y: 0, w: 0, h: 0 }, text: { x: 6, y: 6, w: 88, h: 88 } };
    }
  }

  // Legacy advanced-image-only pages (custom image_x/y/width/height_percent but
  // NOT a free-dragged text position) used sb-pos-v/h-* flex alignment to place
  // the text box within whatever page area the image left free. Approximated
  // here as a same-sized box anchored to match that alignment's intent.
  function _legacyEnumTextRect(page, hasImage) {
    const n = normPageLayout(page);
    const w = hasImage ? 50 : 88;
    const hh = 30;
    let x = 6;
    let y = 6;
    if (n.h === "center") x = (100 - w) / 2;
    else if (n.h === "right") x = 94 - w;
    if (n.v === "center") y = (100 - hh) / 2;
    else if (n.v === "bottom") y = 94 - hh;
    return { x: Math.max(0, x), y: Math.max(0, y), w: w, h: hh };
  }

  /**
   * Synthesizes a layout object list from a page's legacy enum/percent fields —
   * in-memory only, NEVER persisted. This is what makes buildObjectCanvasHtml the
   * single renderer for every page: legacy pages just resolve to an equivalent
   * layout on the fly instead of going through a second rendering implementation.
   */
  function legacyPageToLayout(page) {
    page = page || {};
    const objects = [];
    const advanced = pageHasCustomImageLayout(page) || pageHasCustomDragPos(page);

    if (advanced) {
      const hasImage = pageHasCustomImageLayout(page);
      if (hasImage) {
        objects.push({
          id: "legacy-image",
          type: "image",
          x: parsePercent(page.image_x_percent) || 0,
          y: parsePercent(page.image_y_percent) || 0,
          w: parsePercent(page.image_width_percent) || 40,
          h: parsePercent(page.image_height_percent) != null ? parsePercent(page.image_height_percent) : 34,
          rotation: 0,
          image: { fit: "contain", aspectLocked: true },
        });
      }
      let textRect;
      if (pageHasCustomDragPos(page)) {
        const cx = parsePercent(page.text_x_percent) || 50;
        const cy = parsePercent(page.text_y_percent) || 50;
        const w = 44;
        const hh = 22;
        textRect = {
          x: Math.max(0, Math.min(100 - w, cx - w / 2)),
          y: Math.max(0, Math.min(100 - hh, cy - hh / 2)),
          w: w,
          h: hh,
        };
      } else {
        textRect = _legacyEnumTextRect(page, hasImage);
      }
      objects.push({
        id: "primary-text",
        type: "text",
        role: "primary",
        x: textRect.x,
        y: textRect.y,
        w: textRect.w,
        h: textRect.h,
        rotation: 0,
        format: { fontSize: "m", bold: false, italic: false, underline: false, align: "left" },
      });
    } else {
      const placement = normImagePlacement(page);
      const hasImage = !!(page.image_url && placement !== "none");
      if (hasImage) {
        const rects = _legacyPlacementRects(placement);
        objects.push({
          id: "legacy-image",
          type: "image",
          x: rects.image.x,
          y: rects.image.y,
          w: rects.image.w,
          h: rects.image.h,
          rotation: 0,
          image: { fit: "contain", aspectLocked: true },
        });
        objects.push({
          id: "primary-text",
          type: "text",
          role: "primary",
          x: rects.text.x,
          y: rects.text.y,
          w: rects.text.w,
          h: rects.text.h,
          rotation: 0,
          format: { fontSize: "m", bold: false, italic: false, underline: false, align: "left" },
        });
      } else {
        objects.push({
          id: "primary-text",
          type: "text",
          role: "primary",
          x: 6,
          y: 6,
          w: 88,
          h: 88,
          rotation: 0,
          format: { fontSize: "m", bold: false, italic: false, underline: false, align: "left" },
        });
      }
    }

    return { version: 1, objects: objects };
  }

  function resolvePageLayout(page) {
    page = page || {};
    return page.layout_json && typeof page.layout_json === "object"
      ? page.layout_json
      : legacyPageToLayout(page);
  }

  // Unconditional now — every page (legacy or layout_json) renders through
  // buildObjectCanvasHtml via resolvePageLayout(). The pre-V3 dual-dispatch
  // builders (buildV2CanvasLayoutPageHtml, buildV2StandardPageHtml, buildPanelHtml,
  // buildPositionedImageHtml, ...) were removed in the Phase 8 cleanup once nothing
  // referenced them from this dispatch or from any external caller.
  function buildV2LeftPageHtml(page, optsOrContext, context) {
    const r = resolveV2PageArgs.apply(null, arguments);
    return buildObjectCanvasHtml(resolvePageLayout(r.page), r.page, r.opts, r.context);
  }

  function buildV2RightPageHtml(page, optsOrContext, context) {
    const r = resolveV2PageArgs.apply(null, arguments);
    return buildObjectCanvasHtml(resolvePageLayout(r.page), r.page, r.opts, r.context);
  }

  /* ----- Spread math + content helpers (V2 reader) ----- */

  function spreadCount(pages) {
    if (!Array.isArray(pages) || !pages.length) return 0;
    return Math.ceil(pages.length / 2);
  }

  function spreadIndexForPageIndex(pageIndex) {
    const i = Number(pageIndex);
    if (!Number.isFinite(i) || i < 0) return 0;
    return Math.floor(i / 2);
  }

  function pagesForSpread(pages, spreadIndex) {
    const list = Array.isArray(pages) ? pages : [];
    const si = Math.max(0, Math.floor(Number(spreadIndex) || 0));
    const leftIndex = si * 2;
    const rightIndex = leftIndex + 1;
    return {
      spreadIndex: si,
      left: leftIndex < list.length ? list[leftIndex] : null,
      right: rightIndex < list.length ? list[rightIndex] : null,
      leftIndex: leftIndex < list.length ? leftIndex : -1,
      rightIndex: rightIndex < list.length ? rightIndex : -1,
    };
  }

  function canSpreadPrev(spreadIndex) {
    return Math.floor(Number(spreadIndex) || 0) > 0;
  }

  function canSpreadNext(spreadIndex, pages) {
    const si = Math.floor(Number(spreadIndex) || 0);
    return si < spreadCount(pages) - 1;
  }

  function formatSpreadIndicator(spreadIndex, pages) {
    const n = Array.isArray(pages) ? pages.length : 0;
    if (!n) return "";
    const s = pagesForSpread(pages, spreadIndex);
    const leftNum = s.leftIndex >= 0 ? s.leftIndex + 1 : "—";
    const rightNum = s.rightIndex >= 0 ? s.rightIndex + 1 : "—";
    if (leftNum === rightNum) return "Oldal " + leftNum + " / " + n;
    return "Oldal " + leftNum + "–" + rightNum + " / " + n;
  }

  function pauseAudioInBook(root) {
    if (!root) return;
    root.querySelectorAll("audio").forEach(function (a) {
      try {
        a.pause();
      } catch (_) {}
    });
  }

  function preloadSpreadImages(pages, spreadIndex, assetUrl) {
    if (!Array.isArray(pages) || typeof assetUrl !== "function") return;
    const si = Math.floor(Number(spreadIndex) || 0);
    [-1, 0, 1].forEach(function (delta) {
      const spread = pagesForSpread(pages, si + delta);
      [spread.left, spread.right].forEach(function (p) {
        if (!p || !p.image_url) return;
        const u = assetUrl(String(p.image_url).trim());
        if (!u) return;
        try {
          const img = new Image();
          img.decoding = "async";
          img.src = u;
        } catch (_) {}
      });
    });
  }

  window.MesencsiStorybookReader = {
    boxStyleClass: boxStyleClass,
    normPageLayout: normPageLayout,
    normImagePlacement: normImagePlacement,
    storybookPageTextLimit: storybookPageTextLimit,
    STORYBOOK_TEXT_ONLY_MAX_CHARS: STORYBOOK_TEXT_ONLY_MAX_CHARS,
    STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS: STORYBOOK_TEXT_WITH_IMAGE_MAX_CHARS,
    parsePercent: parsePercent,
    pageHasCustomDragPos: pageHasCustomDragPos,
    pageHasCustomImageLayout: pageHasCustomImageLayout,
    buildObjectCanvasHtml: buildObjectCanvasHtml,
    legacyPageToLayout: legacyPageToLayout,
    resolvePageLayout: resolvePageLayout,
    buildV2LeftPageHtml: buildV2LeftPageHtml,
    buildV2RightPageHtml: buildV2RightPageHtml,
    spreadCount: spreadCount,
    spreadIndexForPageIndex: spreadIndexForPageIndex,
    pagesForSpread: pagesForSpread,
    canSpreadPrev: canSpreadPrev,
    canSpreadNext: canSpreadNext,
    formatSpreadIndicator: formatSpreadIndicator,
    preloadSpreadImages: preloadSpreadImages,
    pauseAudioInBook: pauseAudioInBook,
  };
})();
