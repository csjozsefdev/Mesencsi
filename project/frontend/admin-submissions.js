/* Admin: beküldött felhasználói mesék — számláló jelvény, lista kiegészítés, visszaküldés.
 * Az admin.html az auth.js után tölti be. Ha a végpont nem elérhető (pl. nincs belépve), csendben nem csinál semmit.
 * A publikálás továbbra is a meglévő "Publikálás" gomb (kizárólag owner). */
(function () {
  "use strict";
  var auth = window.MesencsiAdminAuth;
  if (!auth || window.__adminSubsInstalled || document.documentElement.classList.contains("meseiro")) return;
  window.__adminSubsInstalled = true;

  var pending = 0;
  var subs = {}; // book_id -> beküldési adat
  var subsAt = 0;
  var filterOn = false;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var css = document.createElement("style");
  css.textContent =
    ".admin-sub-badge{display:inline-block;min-width:1.35em;padding:0 .4em;margin-left:.4em;border-radius:999px;" +
    "background:#c62828;color:#fff;font-size:.78em;font-weight:800;line-height:1.5;text-align:center}" +
    ".admin-sub-pill{display:inline-flex;align-items:center;gap:.4em;margin-right:.75rem;padding:.2rem .7rem;border-radius:999px;" +
    "background:#c62828;color:#fff;font-weight:700;font-size:.85rem;border:0;cursor:pointer}" +
    ".admin-sub-pill[hidden]{display:none}" +
    ".sb-book-card.is-submission{outline:2px solid #c62828;outline-offset:-2px}" +
    ".admin-sub-note{margin:.35rem 0;font-size:.86rem;line-height:1.35}" +
    ".admin-sub-note .badge{margin-right:.35rem}";
  document.head.appendChild(css);

  async function fetchCount() {
    try {
      var r = await auth.api("/admin/storybook-submissions/pending-count");
      pending = (r && r.pending) | 0;
    } catch (_) {
      return;
    }
    renderBadges();
  }

  function renderBadges() {
    var nav = document.querySelector('.admin-topnav__links [data-nav="storybooks"]');
    if (nav) {
      var b = nav.querySelector(".admin-sub-badge");
      if (pending > 0) {
        if (!b) {
          b = document.createElement("span");
          b.className = "admin-sub-badge";
          nav.appendChild(b);
        }
        if (b.textContent !== String(pending)) b.textContent = String(pending);
      } else if (b) {
        b.remove();
      }
    }
    var meta = document.querySelector(".admin-topnav__meta");
    if (meta) {
      var pill = document.getElementById("adminSubPill");
      if (!pill) {
        pill = document.createElement("button");
        pill.type = "button";
        pill.id = "adminSubPill";
        pill.className = "admin-sub-pill";
        pill.setAttribute("data-nav", "storybooks");
        meta.insertBefore(pill, meta.firstChild);
      }
      pill.hidden = pending <= 0;
      var label = "🔔 " + pending + " beküldött mese vár elbírálásra";
      if (pill.textContent !== label) pill.textContent = label;
    }
    var chip = document.getElementById("adminSubFilter");
    if (chip) chip.textContent = "Beküldött (" + pending + ")";
  }

  async function loadSubs() {
    if (Date.now() - subsAt < 8000) return;
    subsAt = Date.now();
    try {
      var rows = await auth.api("/admin/storybook-submissions?state=all");
      subs = {};
      (rows || []).forEach(function (r) {
        subs[r.book_id] = r;
      });
    } catch (_) {}
  }

  function applyFilter() {
    document.querySelectorAll(".sb-book-card[data-sb-card-id]").forEach(function (card) {
      var s = subs[parseInt(card.getAttribute("data-sb-card-id"), 10)];
      var isPending = !!s && s.status === "submitted";
      card.style.display = filterOn && !isPending ? "none" : "";
    });
    var chip = document.getElementById("adminSubFilter");
    if (chip) chip.classList.toggle("is-active", filterOn);
  }

  function ensureChip() {
    var bar = document.querySelector("#sbToolbar .sb-toolbar-filters");
    if (!bar || document.getElementById("adminSubFilter")) return;
    var chip = document.createElement("button");
    chip.type = "button";
    chip.id = "adminSubFilter";
    chip.className = "admin-nav-item btn-sm";
    chip.addEventListener("click", function () {
      filterOn = !filterOn;
      // a többi szűrő kiválasztása kikapcsolja a beküldött szűrőt
      applyFilter();
    });
    bar.appendChild(chip);
    bar.addEventListener("click", function (ev) {
      if (ev.target.closest("[data-sb-filter]")) {
        filterOn = false;
        applyFilter();
      }
    });
    renderBadges();
  }

  async function decorate() {
    var cards = document.querySelectorAll(".sb-book-card[data-sb-card-id]:not([data-admin-sub])");
    if (!cards.length) return;
    await loadSubs();
    cards.forEach(function (card) {
      var id = parseInt(card.getAttribute("data-sb-card-id"), 10);
      var s = subs[id];
      card.setAttribute("data-admin-sub", s ? "1" : "0");
      if (!s) return;
      var body = card.querySelector(".sb-book-card-body");
      var actions = card.querySelector(".sb-book-card-actions");
      var submitted = s.status === "submitted";
      if (submitted) card.classList.add("is-submission");
      var when = s.submitted_at ? new Date(s.submitted_at).toLocaleString("hu-HU") : "—";
      var note = document.createElement("div");
      note.className = "admin-sub-note";
      note.innerHTML =
        '<span class="badge ' +
        (submitted ? "badge-draft" : "badge-done") +
        '">' +
        (submitted ? "Beküldött" : s.status === "published" ? "Felhasználói · publikált" : "Felhasználói piszkozat") +
        "</span>Szerző: <strong>" +
        esc(s.author_name || s.owner_label || "—") +
        "</strong> (" +
        esc(s.owner_email) +
        ")" +
        (submitted ? "<br>Beküldve: " + esc(when) : "") +
        (s.admin_note ? "<br>Üzenet a szerzőnek: " + esc(s.admin_note) : "");
      if (body) body.insertBefore(note, actions);
      if (submitted && actions) {
        var back = document.createElement("button");
        back.type = "button";
        back.className = "btn btn-ghost btn-sm";
        back.textContent = "Visszaküldés javításra";
        back.addEventListener("click", async function () {
          var msg = window.prompt("Üzenet a szerzőnek (mit javítson)? Üresen is hagyhatod.", "");
          if (msg === null) return;
          try {
            await auth.api("/admin/storybook-submissions/" + id + "/return", {
              method: "POST",
              body: JSON.stringify({ note: msg }),
            });
            subsAt = 0;
            await fetchCount();
            location.reload();
          } catch (e) {
            window.alert(e && e.message ? e.message : "Nem sikerült.");
          }
        });
        actions.appendChild(back);
      }
    });
    applyFilter();
  }

  var timer = null;
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(function () {
      ensureChip();
      decorate();
      renderBadges();
    }, 120);
  }

  document.addEventListener("DOMContentLoaded", function () {
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    fetchCount();
    setInterval(fetchCount, 60000);
    schedule();
  });
})();
