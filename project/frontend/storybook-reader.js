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
    let style = String(p.text_box_style || "card").toLowerCase();
    if (!BOX_IDS.has(style)) style = "card";
    return { v: v, h: h, style: style };
  }

  function pageHasCustomDragPos(p) {
    return parsePercent(p && p.text_x_percent) != null && parsePercent(p && p.text_y_percent) != null;
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
      const u = assetUrl(String(page.image_url).trim());
      if (u) {
        imageHtml =
          '<div class="sb-read-image-wrap"><img src="' +
          esc(u) +
          '" alt="" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"/></div>';
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

  function buildFlowTextHtml(page, opts) {
    const h = panelOptsHelpers(opts);
    const n = normPageLayout(page);
    const bodyRaw = String((page && page.body_text) || "");
    const body = bodyRaw.trim() ? h.esc(bodyRaw) : "";
    if (!body) return "";
    const boxClass = "sb-text-box " + boxStyleClass(n.style);
    return (
      '<div class="sb-read-text-host">' +
      '<div class="sb-read-text-stage sb-pos-v-top sb-pos-h-left">' +
      '<div class="sb-read-text-overlay">' +
      '<div class="sb-read-text-wrap">' +
      '<div class="' +
      boxClass +
      '"><div class="sb-canvas-text">' +
      body +
      "</div></div></div></div></div></div>"
    );
  }

  function buildPageImageHtml(page, opts, role) {
    const h = panelOptsHelpers(opts);
    page = page || {};
    if (!page.image_url) return "";
    const u = h.assetUrl(String(page.image_url).trim());
    if (!u) return "";
    const wrapClass =
      "sb-read-image-wrap" + (role === "hero" ? " sbv2-hero-image" : " sbv2-vignette-image");
    return (
      '<div class="' +
      wrapClass +
      '"><img src="' +
      h.esc(u) +
      '" alt="" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"/></div>'
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

  /**
   * V2 spread — left (TEXT_FORWARD): running title, vignette, story, audio, folio.
   * @param {object} page
   * @param {object} [opts]
   * @param {{ pageNumber?: number, opts?: object }} [context]
   */
  function buildV2LeftPageHtml(page, optsOrContext, context) {
    const r = resolveV2PageArgs.apply(null, arguments);
    const h = panelOptsHelpers(r.opts);
    page = r.page;
    context = r.context;
    const opts = r.opts;
    let headerHtml = "";
    if (page.title) {
      headerHtml =
        '<header class="sbv2-zone sbv2-zone--header">' +
        '<p class="sbv2-running-title">' +
        h.esc(String(page.title)) +
        "</p></header>";
    }
    const vignetteHtml = buildPageImageHtml(page, opts, "vignette");
    const vignetteZone = vignetteHtml
      ? '<figure class="sbv2-zone sbv2-zone--vignette">' + vignetteHtml + "</figure>"
      : "";
    const storyHtml = buildFlowTextHtml(page, opts);
    const storyZone = storyHtml
      ? '<div class="sbv2-zone sbv2-zone--story">' + storyHtml + "</div>"
      : '<div class="sbv2-zone sbv2-zone--story"><p class="empty"> </p></div>';
    return (
      '<div class="sbv2-spread-layout sbv2-spread-layout--left">' +
      headerHtml +
      vignetteZone +
      storyZone +
      buildPageAudioHtml(page, opts) +
      buildFolioHtml(context.pageNumber) +
      "</div>"
    );
  }

  /**
   * V2 spread — right (VISUAL_FORWARD): title, hero image, supporting text, audio, folio.
   * @param {object} page
   * @param {object} [opts]
   * @param {{ pageNumber?: number, opts?: object }} [context]
   */
  function buildV2RightPageHtml(page, optsOrContext, context) {
    const r = resolveV2PageArgs.apply(null, arguments);
    const h = panelOptsHelpers(r.opts);
    page = r.page;
    context = r.context;
    const opts = r.opts;
    let titleHtml = "";
    if (page.title) {
      titleHtml =
        '<header class="sbv2-zone sbv2-zone--title">' +
        '<h2 class="sbv2-page-title">' +
        h.esc(String(page.title)) +
        "</h2></header>";
    }
    const heroInner = buildPageImageHtml(page, opts, "hero");
    const heroZone = heroInner
      ? '<figure class="sbv2-zone sbv2-zone--hero">' + heroInner + "</figure>"
      : "";
    const supportInner = buildFlowTextHtml(page, opts);
    const supportZone = supportInner
      ? '<div class="sbv2-zone sbv2-zone--support">' + supportInner + "</div>"
      : "";
    return (
      '<div class="sbv2-spread-layout sbv2-spread-layout--right">' +
      titleHtml +
      heroZone +
      supportZone +
      buildPageAudioHtml(page, opts) +
      buildFolioHtml(context.pageNumber) +
      "</div>"
    );
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
    parsePercent: parsePercent,
    pageHasCustomDragPos: pageHasCustomDragPos,
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
