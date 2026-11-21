/* Mesekönyv szerkesztő téma — feliratok, ikonok, kis segítségek.
 * A szerkesztő működéséhez nem nyúl: csak szövegeket és ikonokat cserél, az azonosítók és az eseménykezelők maradnak.
 * Admin (/admin) és felhasználói mód (/meseiro) is betölti. Minden lépés ismételhető (idempotens). */
(function () {
  "use strict";
  if (window.__mtThemeInstalled) return;
  window.__mtThemeInstalled = true;

  var ICONS = {
    pen: '<path d="M20 4c-6 1-11 5-13 11l-2 5 5-2c6-2 10-7 11-13z"/><path d="M9 15l6-6"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M3 17l5-4 4 3 4-5 5 5"/>',
    undo: '<path d="M3 7v6h6"/><path d="M3 13a9 9 0 1 0 3-7"/>',
    redo: '<path d="M21 7v6h-6"/><path d="M21 13a9 9 0 1 1-3-7"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    back: '<path d="M15 5l-7 7 7 7"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>'
  };

  function svg(name, size) {
    return (
      '<svg viewBox="0 0 24 24" width="' + (size || 24) + '" height="' + (size || 24) +
      '" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      ICONS[name] + "</svg>"
    );
  }

  function $(id) {
    return document.getElementById(id);
  }

  function setIcon(id, name, size) {
    var el = $(id);
    if (!el || el.dataset.mtIcon === name) return;
    el.dataset.mtIcon = name;
    el.innerHTML = svg(name, size);
  }

  function setText(el, text) {
    if (el && el.textContent !== text) el.textContent = text;
  }

  // ---------------------------------------------------------------- Mesesegéd (a róka)
  var FOX =
    '<svg class="mt-fox" width="46" height="46" viewBox="0 0 64 64" aria-hidden="true"><path d="M6 8l16 12 10-3 10 3 16-12-4 26c0 14-9 26-22 26S10 48 10 34z" fill="#e58a3c"/><path d="M14 36c4 10 10 14 18 14s14-4 18-14c-6 4-12 6-18 6s-12-2-18-6z" fill="#fff4de"/><circle cx="23" cy="32" r="3.4" fill="#2a1808"/><circle cx="41" cy="32" r="3.4" fill="#2a1808"/><ellipse cx="32" cy="42" rx="4" ry="3" fill="#2a1808"/></svg>';

  var GENERAL_TIPS = [
    "A képeket a sarkuknál fogva húzva átméretezheted, a közepüknél fogva pedig odébb tolhatod.",
    "Kattints a szövegre, és az oldal fölött megjelennek a formázó gombok: félkövér, betűméret, szín.",
    "A Díszek gombbal csillagokat és más díszeket tehetsz az oldalra.",
    "Elrontottál valamit? A Vissza gomb visszahozza az előző állapotot.",
    "Az oldalak sorában az oldalakat húzással átrendezheted."
  ];

  var tipState = { sig: "", idx: 0, hidden: false, loaded: false };

  function tipStore(set) {
    try {
      if (set !== undefined) localStorage.setItem("mtTipHidden", set ? "1" : "0");
      else return localStorage.getItem("mtTipHidden") === "1";
    } catch (_) {}
    return false;
  }

  function readContext() {
    var pageCount = document.querySelectorAll("#sbPageNavList .sb-page-thumb").length;
    var counter = $("sbCurPageCharCounter");
    var m = counter && counter.textContent.match(/(\d+)\s*\/\s*(\d+)/);
    var chars = m ? parseInt(m[1], 10) : 0;
    var max = m ? parseInt(m[2], 10) : 600;
    var rows = Array.prototype.slice.call(document.querySelectorAll("#sbLayersList .sb-layer-row"));
    var hasImage = rows.some(function (r) {
      return /k[ée]p/i.test(r.textContent);
    });
    var coverEl = $("sbCoverUrl");
    var noSel = $("sbNoSelectionHint");
    return {
      pageCount: pageCount,
      chars: chars,
      max: max,
      hasImage: hasImage,
      hasPageContent: rows.length > 0,
      hasCover: !!(coverEl && coverEl.value),
      noSelection: !noSel || !noSel.hidden,
      canSubmit: !!$("btnMeseiroSubmit")
    };
  }

  function buildTips(c) {
    var tips = [];
    if (c.pageCount === 0) {
      tips.push({ t: "Kezdd az első oldallal!", m: "Az alsó sorban nyomd meg az „Új oldal” gombot, aztán kattints a szövegre, és írd az első mondatot." });
    }
    if (c.pageCount > 0 && c.max && c.chars > c.max) {
      tips.push({ t: "Ez az oldal már túl hosszú", m: "A szöveg túllépte a megengedett hosszt. Vágd ketté, és a folytatást írd egy új oldalra." });
    } else if (c.pageCount > 0 && c.max && c.chars / c.max >= 0.8) {
      tips.push({ t: "Mindjárt betelik az oldal", m: "A szöveg a hely 80%-ánál tart. Ha folytatni szeretnéd, nyiss egy új oldalt." });
    }
    if (c.pageCount > 0 && c.hasPageContent && !c.hasImage) {
      tips.push({ t: "Egy kép sokat dobna rajta", m: "Ezen az oldalon még nincs kép. A bal oldali „Kép” gombbal feltölthetsz egyet (legfeljebb 3 MB)." });
    }
    if (c.pageCount >= 3 && !c.hasCover) {
      tips.push({ t: "Hiányzik a borítókép", m: "A fent jobbra lévő ⋮ menüben feltölthetsz borítóképet. Nem kötelező, de szebben mutat a könyvespolcon." });
    }
    if (c.canSubmit && c.pageCount >= 3 && c.hasCover) {
      tips.push({ t: "Szerintem kész vagy!", m: "Mindent kipipáltál. Ha elégedett vagy a mesével, küldd be az adminnak.", action: "check" });
    } else if (c.canSubmit && c.pageCount >= 1) {
      tips.push({ t: "Mielőtt beküldöd", m: "Megnézzük együtt, minden megvan-e: cím, oldalak, szöveg és borítókép.", action: "check" });
    }
    if (c.pageCount > 0 && c.noSelection) {
      tips.push({ t: "Kattints a szövegre", m: "Ha a szövegre vagy a képre kattintasz, az oldal fölött megjelennek a hozzá való gombok." });
    }
    GENERAL_TIPS.forEach(function (g, i) {
      tips.push({ t: "Mesesegéd tipp", m: g, g: i });
    });
    return tips;
  }

  function renderTip(body) {
    var tipEl = body.querySelector(".mt-tip");
    if (!tipState.loaded) {
      tipState.loaded = true;
      tipState.hidden = tipStore();
    }
    var c = readContext();
    var tips = buildTips(c);
    var sig = [c.pageCount, c.chars > c.max ? "over" : c.chars / (c.max || 1) >= 0.8 ? "near" : "ok", c.hasImage, c.hasCover, c.noSelection, c.canSubmit, tipState.hidden].join("|");
    if (tipEl && sig === tipState.sig && !tipEl.dataset.mtDirty) return;
    if (sig !== tipState.sig) tipState.idx = 0; // új helyzet: újra az első (leghasznosabb) tippel kezdünk
    tipState.sig = sig;
    if (tipState.idx >= tips.length) tipState.idx = 0;
    var tip = tips[tipState.idx];
    if (!tipEl) {
      tipEl = document.createElement("div");
      body.appendChild(tipEl);
      tipEl.addEventListener("click", function (ev) {
        var b = ev.target.closest("[data-mt]");
        if (!b) return;
        var kind = b.getAttribute("data-mt");
        if (kind === "next") {
          var n = buildTips(readContext()).length;
          tipState.idx = (tipState.idx + 1) % Math.max(1, n);
          tipEl.dataset.mtDirty = "1";
          schedule();
        } else if (kind === "close") {
          tipState.hidden = true;
          tipStore(true);
          tipEl.dataset.mtDirty = "1";
          schedule();
        } else if (kind === "check") {
          var sb = $("btnMeseiroSubmit");
          if (sb) sb.click();
        }
      });
    }
    delete tipEl.dataset.mtDirty;
    if (tipState.hidden) {
      tipEl.className = "mt-tip mt-tip--min";
      tipEl.innerHTML = '<button type="button" class="mt-tip__fox" aria-label="Mesesegéd megnyitása" title="Kérdezd a rókát!">' + FOX + "<span>Mesesegéd</span></button>";
      tipEl.querySelector(".mt-tip__fox").addEventListener("click", function () {
        tipState.hidden = false;
        tipStore(false);
        tipEl.dataset.mtDirty = "1";
        schedule();
      });
      return;
    }
    tipEl.className = "mt-tip mt-tip--bounce";
    tipEl.innerHTML =
      FOX +
      '<div class="mt-tip__txt"><b>' + tip.t + "</b><span>" + tip.m + "</span>" +
      '<div class="mt-tip__actions">' +
      (tip.action === "check" ? '<button type="button" class="mt-tip__btn mt-tip__btn--go" data-mt="check">Beküldés ellenőrzése</button>' : "") +
      (tips.length > 1 ? '<button type="button" class="mt-tip__btn" data-mt="next">Következő tipp</button>' : "") +
      "</div></div>" +
      '<button type="button" class="mt-tip__x" data-mt="close" aria-label="Mesesegéd elrejtése" title="Elrejtés">&times;</button>';
  }

  var firstRun = true;

  function apply() {
    var root = $("sbEditorRoot");
    if (!root) return;
    var isUser = document.documentElement.classList.contains("meseiro");

    // bal eszköztár: ikonok + érthető feliratok
    setIcon("btnSbAddSecondaryText", "pen", 32);
    setIcon("btnSbAddImageShortcut", "image", 32);
    setIcon("btnSbUndo", "undo", 28);
    setIcon("btnSbRedo", "redo", 28);
    setIcon("btnSbDeleteSelectedObject", "trash", 28);
    var labels = { "Dekor": "Díszek", "Szöveg": "Szöveg", "Kép": "Kép" };
    root.querySelectorAll(".sb-ed-rail-label").forEach(function (l) {
      var t = l.textContent.trim();
      if (labels[t] && labels[t] !== t) setText(l, labels[t]);
    });
    var add = $("btnSbAddSecondaryText");
    if (add) add.title = "Új szöveg az oldalra";
    var addImg = $("btnSbAddImageShortcut");
    if (addImg) addImg.title = "Kép feltöltése az oldalra";

    // felső sáv
    var back = $("btnSbBackToList");
    if (back && !back.dataset.mt) {
      back.dataset.mt = "1";
      back.innerHTML = svg("back", 20) + "<span>" + (isUser ? "Meséim" : "Mesekönyvek") + "</span>";
    }
    var prev = $("btnSbEdPreview");
    if (prev && !prev.dataset.mt) {
      prev.dataset.mt = "1";
      prev.innerHTML = svg("eye", 20) + "<span> Előnézet</span>";
    }
    var gear = root.querySelector(".sb-ed-gear-btn");
    if (gear && !gear.dataset.mt) {
      gear.dataset.mt = "1";
      gear.innerHTML = svg("gear", 20) + "<span>Oldal beállításai</span>";
    }

    // eszköztár súgó
    var hint = $("sbNoSelectionHint");
    setText(hint, "Kattints a szövegre vagy a képre az oldalon, és itt megjelennek a formázó gombok.");

    // jobb panel: érthető elnevezések
    var dock = $("sbEdDock");
    if (dock) {
      dock.querySelectorAll(".sb-ed-dock-heading").forEach(function (h) {
        var t = h.textContent.trim();
        if (t === "Rétegek") setText(h, "Mi van az oldalon?");
        if (t === "Háttér") setText(h, "Az oldal háttere");
        if (t === "Tulajdonságok" || t === "Pontos elhelyezés ▾" || t === "Pontos elhelyezés") {
          var sec = h.closest(".sb-ed-dock-section");
          if (sec && !sec.dataset.mtCollapse) {
            sec.dataset.mtCollapse = "1";
            sec.classList.add("mt-collapsible", "mt-closed");
            h.setAttribute("role", "button");
            h.tabIndex = 0;
            var toggle = function () {
              sec.classList.toggle("mt-closed");
              h.textContent = "Pontos elhelyezés " + (sec.classList.contains("mt-closed") ? "▾" : "▴");
            };
            h.addEventListener("click", toggle);
            h.addEventListener("keydown", function (e) {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                toggle();
              }
            });
          }
          setText(h, "Pontos elhelyezés " + (sec && sec.classList.contains("mt-closed") ? "▾" : "▴"));
        }
      });
      var hintEl = dock.querySelector(".sb-sidebar-hint");
      if (hintEl && !hintEl.dataset.mt) {
        hintEl.dataset.mt = "1";
        hintEl.textContent = "Ami feljebb van a listában, az van legelöl az oldalon.";
      }
      var front = $("btnSbLayerToFront");
      var backBtn = $("btnSbLayerToBack");
      setText(front, "Eléje hozom");
      setText(backBtn, "Mögé teszem");
      var body = dock.querySelector(".sb-ed-dock-body");
      if (body) renderTip(body);
    }

    // az oldalak sora induláskor legyen nyitva
    if (firstRun) {
      firstRun = false;
      var strip = $("sbPageStrip");
      if (strip) {
        strip.classList.remove("is-collapsed");
        var tg = $("btnSbTogglePageStrip");
        if (tg) tg.setAttribute("aria-expanded", "true");
      }
    }
  }

  var timer = null;
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(apply, 80);
  }

  document.addEventListener("DOMContentLoaded", function () {
    apply();
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  });
})();
