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
      if (body && !body.querySelector(".mt-tip")) {
        var tip = document.createElement("div");
        tip.className = "mt-tip";
        tip.innerHTML =
          '<svg width="44" height="44" viewBox="0 0 64 64" aria-hidden="true" style="flex:none"><path d="M6 8l16 12 10-3 10 3 16-12-4 26c0 14-9 26-22 26S10 48 10 34z" fill="#e58a3c"/><path d="M14 36c4 10 10 14 18 14s14-4 18-14c-6 4-12 6-18 6s-12-2-18-6z" fill="#fff4de"/><circle cx="23" cy="32" r="3.4" fill="#2a1808"/><circle cx="41" cy="32" r="3.4" fill="#2a1808"/><ellipse cx="32" cy="42" rx="4" ry="3" fill="#2a1808"/></svg>' +
          "<div><b>Mesesegéd tipp</b>A képeket a sarkuknál fogva húzva átméretezheted. Ha a szöveg betelik, folytasd a mesét egy új oldalon.</div>";
        body.appendChild(tip);
      }
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
