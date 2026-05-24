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

  const MAGIC_MS = 420;

  const RM_CLASSES = [
    "sb-read-panel--enter-next",
    "sb-read-panel--enter-prev",
    "sb-read-panel--exit-next",
    "sb-read-panel--exit-prev",
    "page-exit",
    "page-exit--next",
    "page-exit--prev",
    "page-enter-prep",
    "page-enter-prep--next",
    "page-enter-prep--prev",
    "page-enter",
    "sb-page-rm-fade-out",
    "sb-page-rm-fade-in-prep",
    "sb-page-rm-fade-in",
    "page-transition-out",
    "page-transition-out--next",
    "page-transition-out--prev",
    "page-transition-in-prep",
    "page-transition-in",
  ];

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
      textBlock =
        '<div class="sb-read-text-host">' +
        '<div class="sb-read-text-stage sb-text-stage--overlay">' +
        '<div class="sb-read-text-overlay">' +
        '<div class="sb-read-text-wrap" style="left:' +
        xp +
        "%;top:" +
        yp +
        '%;transform:translate(-50%,-50%)">' +
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

  function buildPublicReaderShellHtml() {
    return (
      '<div class="sb-public-reader-inner">' +
      '<div class="sb-read-dynamic-header"></div>' +
      '<p class="sb-public-read-pageind" aria-live="polite"></p>' +
      '<div class="sb-read-page-stage">' +
      '<div class="sb-read-page-panel storybook-page"></div>' +
      "</div>" +
      '<div class="sb-read-nav" style="display:flex;flex-wrap:wrap;gap:0.75rem;justify-content:center;margin:1rem 0 0">' +
      '<button type="button" class="btn-outline-ghost" data-sb-nav="prev" aria-label="Előző oldal">← Előző oldal</button>' +
      '<button type="button" class="btn-outline-ghost" data-sb-nav="next" aria-label="Következő oldal">Következő oldal →</button>' +
      "</div></div>"
    );
  }

  function preloadAdjacentImages(pages, idx, assetUrl) {
    if (!Array.isArray(pages) || typeof assetUrl !== "function") return;
    const i = Number(idx);
    if (!Number.isFinite(i)) return;
    [i - 1, i + 1].forEach(function (j) {
      const p = pages[j];
      if (!p || !p.image_url) return;
      const u = assetUrl(String(p.image_url).trim());
      if (!u) return;
      try {
        const img = new Image();
        img.decoding = "async";
        img.src = u;
      } catch (_) {}
    });
  }

  function clearPanelClasses(panel) {
    RM_CLASSES.forEach(function (c) {
      panel.classList.remove(c);
    });
  }

  function prefersReducedMotion() {
    try {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (_) {
      return false;
    }
  }

  function runPanelTransition(panel, direction, applyPanel, opts) {
    opts = opts || {};
    const dir = direction === "prev" ? "prev" : "next";

    function finish() {
      if (typeof opts.setAnimating === "function") opts.setAnimating(false);
      if (typeof opts.preloadAdjacent === "function") opts.preloadAdjacent();
      if (typeof opts.onDone === "function") opts.onDone();
    }

    if (!panel || typeof applyPanel !== "function" || prefersReducedMotion()) {
      if (typeof opts.setAnimating === "function") opts.setAnimating(true);
      applyPanel();
      finish();
      return;
    }

    if (typeof opts.setAnimating === "function") opts.setAnimating(true);

    let finished = false;
    function doneOnce() {
      if (finished) return;
      finished = true;
      clearPanelClasses(panel);
      finish();
    }

    clearPanelClasses(panel);
    panel.classList.add("page-exit", dir === "next" ? "page-exit--next" : "page-exit--prev");

    const fallback = window.setTimeout(function () {
      if (finished) return;
      clearPanelClasses(panel);
      applyPanel();
      doneOnce();
    }, MAGIC_MS + 140);

    function startEnter() {
      clearPanelClasses(panel);
      applyPanel();
      panel.classList.add("page-enter-prep", dir === "next" ? "page-enter-prep--next" : "page-enter-prep--prev");
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          panel.classList.remove("page-enter-prep", "page-enter-prep--next", "page-enter-prep--prev");
          panel.classList.add("page-enter");
          window.setTimeout(doneOnce, MAGIC_MS + 80);
        });
      });
    }

    function onExitEnd(ev) {
      if (ev.target !== panel) return;
      if (ev.propertyName && ev.propertyName !== "opacity" && ev.propertyName !== "transform") return;
      panel.removeEventListener("transitionend", onExitEnd);
      window.clearTimeout(fallback);
      startEnter();
    }

    panel.addEventListener("transitionend", onExitEnd);
  }

  window.MesencsiStorybookReader = {
    boxStyleClass: boxStyleClass,
    normPageLayout: normPageLayout,
    parsePercent: parsePercent,
    pageHasCustomDragPos: pageHasCustomDragPos,
    buildPanelHtml: buildPanelHtml,
    buildPublicReaderShellHtml: buildPublicReaderShellHtml,
    preloadAdjacentImages: preloadAdjacentImages,
    runPanelTransition: runPanelTransition,
  };
})();
