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

  function imageLayoutStyle(page) {
    page = page || {};
    const x = parsePercent(page.image_x_percent);
    const y = parsePercent(page.image_y_percent);
    const w = parsePercent(page.image_width_percent);
    const h = parsePercent(page.image_height_percent);
    if (x == null || y == null || w == null) return "";
    let style = "left:" + x + "%;top:" + y + "%;width:" + w + "%;";
    if (h != null) style += "height:" + h + "%;";
    return style;
  }

  function buildPositionedImageHtml(page, opts, extraClass) {
    const h = panelOptsHelpers(opts);
    page = page || {};
    if (!page.image_url) return "";
    const u = h.assetUrl(String(page.image_url).trim());
    if (!u) return "";
    const style = imageLayoutStyle(page);
    if (!style) return "";
    const cls = "sb-read-image-frame" + (extraClass ? " " + extraClass : "");
    return (
      '<div class="sb-read-image-canvas">' +
      '<div class="' +
      cls +
      '" style="' +
      style +
      '"><img src="' +
      h.esc(u) +
      '" alt="" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"/></div></div>'
    );
  }

  function buildPanelHtml(page, opts) {
    opts = opts || {};
    const esc = typeof opts.escapeHtml === "function" ? opts.escapeHtml : defaultEscape;
    const assetUrl =
      typeof opts.assetUrl === "function"
        ? opts.assetUrl
        : function (u) {
            return u;
          };

    page = page || {};
    const n = normPageLayout(page);
    const custom = pageHasCustomDragPos(page);
    const bodyRaw = String(page.body_text || "");
    const body = bodyRaw.trim() ? esc(bodyRaw) : "&nbsp;";
    const boxClass = "sb-text-box " + boxStyleClass(n.style);

    let titleHtml = "";
    if (page.title) {
      titleHtml = '<h3 class="sb-read-page-title">' + esc(String(page.title)) + "</h3>";
    }

    let imageHtml = "";
    if (page.image_url) {
      if (pageHasCustomImageLayout(page)) {
        imageHtml = buildPositionedImageHtml(page, opts, "sb-read-image-frame--panel");
      } else {
        const u = assetUrl(String(page.image_url).trim());
        if (u) {
          imageHtml =
            '<div class="sb-read-image-wrap"><img src="' +
            esc(u) +
            '" alt="" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"/></div>';
        }
      }
    }

    let audioHtml = "";
    if (page.audio_url) {
      const au = assetUrl(String(page.audio_url).trim());
      if (au) {
        audioHtml =
          '<div class="sb-read-audio-wrap"><audio controls preload="metadata" src="' +
          esc(au) +
          '"></audio></div>';
      }
    }

    let textBlock;
    if (custom) {
      const xp = parsePercent(page.text_x_percent);
      const yp = parsePercent(page.text_y_percent);
      const posStyle =
        Number.isFinite(xp) && Number.isFinite(yp)
          ? "left:" + xp + "%;top:" + yp + "%;transform:translate(-50%, -50%)"
          : "";
      textBlock =
        '<div class="sb-read-text-host">' +
        '<div class="sb-read-text-stage sb-text-stage--overlay">' +
        '<div class="sb-read-text-overlay">' +
        '<div class="sb-read-text-wrap"' +
        (posStyle ? ' style="' + posStyle + '"' : "") +
        ">" +
        '<div class="' +
        boxClass +
        '"><div class="sb-canvas-text">' +
        body +
        "</div></div></div></div></div></div>";
    } else {
      textBlock =
        '<div class="sb-read-text-host">' +
        '<div class="sb-read-text-stage sb-pos-v-' +
        n.v +
        " sb-pos-h-" +
        n.h +
        '">' +
        '<div class="sb-read-text-overlay">' +
        '<div class="sb-read-text-wrap">' +
        '<div class="' +
        boxClass +
        '"><div class="sb-canvas-text">' +
        body +
        "</div></div></div></div></div></div>";
    }

    return titleHtml + '<div class="sb-read-canvas-stack">' + imageHtml + textBlock + audioHtml + "</div>";
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

  function buildSimplePageTextHtml(page, opts) {
    const h = panelOptsHelpers(opts);
    const bodyRaw = String((page && page.body_text) || "");
    const body = bodyRaw.trim() ? h.esc(bodyRaw) : "&nbsp;";
    return '<div class="sbv2-zone sbv2-zone--page-text"><div class="sb-canvas-text">' + body + "</div></div>";
  }

  function buildPlacedPageImageHtml(page, opts) {
    const h = panelOptsHelpers(opts);
    page = page || {};
    if (!page.image_url) return "";
    const u = h.assetUrl(String(page.image_url).trim());
    if (!u) return "";
    return (
      '<figure class="sbv2-zone sbv2-zone--page-image">' +
      '<img src="' +
      h.esc(u) +
      '" alt="" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"/></figure>'
    );
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

  function buildV2CanvasLayoutPageHtml(page, opts, context, side) {
    const h = panelOptsHelpers(opts);
    page = page || {};
    context = context || {};
    const inner =
      buildPanelHtml(page, opts) +
      buildPageAudioHtml(page, opts) +
      buildFolioHtml(context.pageNumber);
    return (
      '<div class="sbv2-spread-layout sbv2-spread-layout--' +
      h.esc(side) +
      ' sbv2-spread-layout--canvas">' +
      '<div class="sbv2-page-canvas">' +
      inner +
      "</div></div>"
    );
  }

  /**
   * V2 standard page: every page renders the same way regardless of which spread
   * slot it lands in — story text plus an optional normal-sized illustration
   * placed exactly where the owner chose (left/right/above/below), or a clean
   * text-only page when there's no image. No automatic vignette/hero sizing.
   * @param {object} page
   * @param {object} [opts]
   * @param {{ pageNumber?: number, opts?: object }} [context]
   */
  function buildV2StandardPageHtml(page, opts, context) {
    const h = panelOptsHelpers(opts);
    page = page || {};
    context = context || {};
    let titleHtml = "";
    if (page.title) {
      titleHtml =
        '<header class="sbv2-zone sbv2-zone--title">' +
        '<h2 class="sbv2-page-title">' +
        h.esc(String(page.title)) +
        "</h2></header>";
    }
    const placement = page.image_url ? normImagePlacement(page) : "none";
    const imageHtml = placement !== "none" ? buildPlacedPageImageHtml(page, opts) : "";
    const textHtml = buildSimplePageTextHtml(page, opts);
    return (
      '<div class="sbv2-standard-page">' +
      titleHtml +
      '<div class="sbv2-page-split sbv2-page-split--' +
      placement +
      '">' +
      imageHtml +
      textHtml +
      "</div>" +
      buildPageAudioHtml(page, opts) +
      buildFolioHtml(context.pageNumber) +
      "</div>"
    );
  }

  function buildV2LeftPageHtml(page, optsOrContext, context) {
    const r = resolveV2PageArgs.apply(null, arguments);
    if (pageHasCustomImageLayout(r.page)) {
      return buildV2CanvasLayoutPageHtml(r.page, r.opts, r.context, "left");
    }
    return buildV2StandardPageHtml(r.page, r.opts, r.context);
  }

  function buildV2RightPageHtml(page, optsOrContext, context) {
    const r = resolveV2PageArgs.apply(null, arguments);
    if (pageHasCustomImageLayout(r.page)) {
      return buildV2CanvasLayoutPageHtml(r.page, r.opts, r.context, "right");
    }
    return buildV2StandardPageHtml(r.page, r.opts, r.context);
  }

  /** @deprecated Use buildV2LeftPageHtml — alias for older callers. */
  /** @deprecated Use buildV2LeftPageHtml / buildV2RightPageHtml — kept for external callers. */
  function buildV2StandardLeftPageHtml(page, opts, context) {
    return buildV2LeftPageHtml(page, opts, context);
  }

  /** @deprecated Use buildV2RightPageHtml — alias for older callers. */
  function buildV2StandardRightPageHtml(page, opts, context) {
    return buildV2RightPageHtml(page, opts, context);
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
    imageLayoutStyle: imageLayoutStyle,
    buildPositionedImageHtml: buildPositionedImageHtml,
    buildPanelHtml: buildPanelHtml,
    buildV2LeftPageHtml: buildV2LeftPageHtml,
    buildV2RightPageHtml: buildV2RightPageHtml,
    buildV2StandardLeftPageHtml: buildV2StandardLeftPageHtml,
    buildV2StandardRightPageHtml: buildV2StandardRightPageHtml,
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
