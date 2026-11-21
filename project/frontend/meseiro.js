/* Nyitási akció: a meglévő mesekönyv-szerkesztő felhasználói módban (/meseiro).
 *
 * A szerver az admin.html-t szolgálja ki ezzel a scripttel együtt (az auth.js után, a fő script előtt).
 * A script a szerkesztő minden "/admin/storybooks" hívását a /my/storybooks API-ra irányítja, az admin
 * funkciókat (publikálás, hang, szűrők) elrejti, és beküldés / visszavonás gombokat ad.
 * Biztonság: ez csak felület — a szerver /my/storybooks API-ja kényszeríti a szabályokat
 * (tulajdonjog, állapotgép, publikálás tiltása).
 */
(function () {
  "use strict";
  var auth = window.MesencsiAdminAuth;
  if (!auth || window.__meseiroInstalled) return;
  window.__meseiroInstalled = true;
  document.documentElement.classList.add("meseiro");

  var origApi = auth.api;
  var state = { me: null, status: null, items: {} };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function remap(path) {
    return typeof path === "string" && path.indexOf("/admin/storybooks") === 0
      ? "/my/storybooks" + path.slice("/admin/storybooks".length)
      : path;
  }

  // ---------------------------------------------------------------- toast + blokkoló oldal
  function toast(msg, ok) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "toast is-visible " + (ok ? "toast-ok" : "toast-err");
    el.style.opacity = "1";
    clearTimeout(toast._t);
    toast._t = setTimeout(function () {
      el.className = "toast";
      el.style.opacity = "";
    }, 4200);
  }

  function blockPage(title, text, linkText, href) {
    function render() {
      document.body.innerHTML =
        '<main class="meseiro-block"><h1>' +
        esc(title) +
        "</h1><p>" +
        esc(text) +
        '</p><p><a class="btn" href="' +
        esc(href) +
        '">' +
        esc(linkText) +
        "</a></p></main>";
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
    else render();
    return new Promise(function () {}); // a szerkesztő indítása sosem folytatódik
  }

  // ---------------------------------------------------------------- belépés / állapot
  async function loadMe() {
    var st = null;
    try {
      var r = await fetch("/my/storybooks/status", { credentials: "include" });
      st = r.ok ? await r.json() : null;
    } catch (_) {}
    state.status = st;
    if (!st || !st.enabled) {
      return blockPage(
        "A mesekönyv-írás jelenleg nem elérhető",
        "Ez a funkció csak a nyitási akció idejére volt nyitva.",
        "Vissza a bolthoz",
        "/"
      );
    }
    var res;
    try {
      res = await fetch("/auth/me", { credentials: "include", headers: { Accept: "application/json" } });
    } catch (_) {
      return blockPage("Nincs kapcsolat", "Ellenőrizd az internetkapcsolatot, és töltsd újra az oldalt.", "Vissza a bolthoz", "/");
    }
    if (res.status === 401 || res.status === 403) {
      return blockPage(
        "Jelentkezz be",
        "A mesekönyv íráshoz be kell jelentkezned a boltban (regisztráció ingyenes). Belépés után térj vissza ide.",
        "Belépés a boltban",
        "/"
      );
    }
    var u = await res.json();
    if (!u.is_verified) {
      return blockPage(
        "Erősítsd meg az e-mail címed",
        "A mesekönyv íráshoz meg kell erősítened az e-mail címed a regisztrációkor kapott linkkel.",
        "Vissza a bolthoz",
        "/"
      );
    }
    state.me = u;
    return {
      username: (u.nickname || "").trim() || "Szerző",
      role: "owner", // csak kliensoldali jelző a szerkesztő vezérlőihez; a szerver a /my/ API-n kényszerít
      is_user_mode: true,
    };
  }

  var mePromise = null;
  function getMe() {
    if (!mePromise) mePromise = loadMe();
    return mePromise;
  }

  // ---------------------------------------------------------------- api átirányítás
  function sanitizeOpts(path, opts) {
    // A felhasználói PATCH nem fogad animation_settings / is_published mezőt.
    if (!opts || String(opts.method || "").toUpperCase() !== "PATCH") return opts;
    if (!/^\/admin\/storybooks\/\d+$/.test(path.split("?")[0])) return opts;
    try {
      var b = JSON.parse(opts.body || "{}");
      delete b.animation_settings;
      delete b.is_published;
      return Object.assign({}, opts, { body: JSON.stringify(b) });
    } catch (_) {
      return opts;
    }
  }

  function remember(path, res) {
    var p = String(path).split("?")[0];
    if (p === "/my/storybooks" && Array.isArray(res)) {
      state.items = {};
      res.forEach(function (b) {
        state.items[b.id] = b;
      });
      // a lista adata a kártyák kirajzolása után is érkezhet: utólag is díszítjük őket
      if (typeof decorateList === "function") setTimeout(decorateList, 0);
    } else if (/^\/my\/storybooks\/\d+/.test(p) && res && typeof res === "object" && res.id && res.submission_status) {
      state.items[res.id] = Object.assign({}, state.items[res.id] || {}, res);
    }
  }

  auth.api = async function (path, opts) {
    if (typeof path === "string") {
      if (path === "/admin/me") return getMe();
      if (path.indexOf("/admin/storybooks") === 0) {
        var o = sanitizeOpts(path, opts);
        var p = remap(path);
        var res = await origApi.call(auth, p, o);
        remember(p, res);
        return res;
      }
      if (path.indexOf("/admin/") === 0) {
        // az admin többi része felhasználói módban nem létezik
        return path.split("?")[0].split("/").length > 3 ? {} : [];
      }
    }
    return origApi.apply(auth, arguments);
  };
  ["uploadForm", "uploadFormWithProgress"].forEach(function (name) {
    var orig = auth[name];
    if (typeof orig !== "function") return;
    auth[name] = function (path) {
      var args = Array.prototype.slice.call(arguments);
      args[0] = remap(path);
      return orig.apply(auth, args);
    };
  });
  auth.clearToken = function () {};

  // A szerkesztő néhány helyen közvetlenül a fetch-et hívja (pl. a lista betöltése): azt is átirányítjuk.
  var origFetch = window.fetch;
  window.fetch = function (input, init) {
    try {
      var url = typeof input === "string" ? input : input && input.url;
      if (url) {
        var u = new URL(url, location.href);
        if (u.origin === location.origin && u.pathname.indexOf("/admin/storybooks") === 0) {
          var np = remap(u.pathname) + u.search;
          var isList = u.pathname === "/admin/storybooks" && String((init && init.method) || "GET").toUpperCase() === "GET";
          var nextInput = typeof input === "string" ? np : new Request(np, input);
          return origFetch.call(this, nextInput, init).then(function (res) {
            if (isList) {
              res
                .clone()
                .json()
                .then(function (d) {
                  remember("/my/storybooks", d);
                })
                .catch(function () {});
            }
            return res;
          });
        }
      }
    } catch (_) {}
    return origFetch.apply(this, arguments);
  };

  // A szerkesztő az URL-t "/admin#..."-ra írja át; felhasználói módban maradjon /meseiro.
  ["replaceState", "pushState"].forEach(function (name) {
    var orig = history[name];
    history[name] = function (st, title, url) {
      if (typeof url === "string") url = url.replace(/^\/admin(?=[#?\/]|$)/, "/meseiro");
      return orig.call(this, st, title, url);
    };
  });

  try {
    if (location.hash !== "#storybooks") history.replaceState(null, "", "/meseiro#storybooks");
  } catch (_) {}

  // ---------------------------------------------------------------- beküldés párbeszédablak
  function consentText() {
    return (
      "Kijelentem, hogy a mese saját alkotásom, és a benne szereplő képek és szövegek felett rendelkezem a szükséges jogokkal " +
      "(nem sértek mások szerzői jogát, és nem szerepelnek benne mások személyes adatai, például gyerekek neve vagy fotója a szülő hozzájárulása nélkül). " +
      "Hozzájárulok, hogy a Mesencsi a művet átnézze, szükség esetén szerkessze, és a döntése szerint a weboldalon a megadott szerzői névvel közzétegye. " +
      "A beküldés nem jelent közzétételi garanciát, a mesét az admin bármikor visszaküldheti vagy elutasíthatja."
    );
  }

  function openSubmitDialog(bookId, title, beforeSubmit) {
    var old = document.getElementById("meseiroSubmitDlg");
    if (old) old.remove();
    var wrap = document.createElement("div");
    wrap.id = "meseiroSubmitDlg";
    wrap.className = "meseiro-dlg-backdrop";
    var prefill = (state.me && state.me.nickname) || "";
    wrap.innerHTML =
      '<div class="meseiro-dlg glass-panel" role="dialog" aria-modal="true" aria-labelledby="meseiroDlgTitle">' +
      '<h3 id="meseiroDlgTitle">Mese beküldése: ' +
      esc(title || "") +
      "</h3>" +
      "<p>Beküldés után a mesét az admin átnézi, és ő dönt a közzétételről. Beküldés után nem szerkesztheted, de visszavonhatod.</p>" +
      '<label class="admin-field">Szerzői név (ez jelenik meg a mese alatt)' +
      '<input type="text" id="meseiroAuthor" maxlength="60" autocomplete="off" value="' +
      esc(prefill) +
      '" placeholder="Pl. Kis Anna" /></label>' +
      '<label class="meseiro-consent"><input type="checkbox" id="meseiroConsent" /> <span>' +
      esc(consentText()) +
      "</span></label>" +
      '<p id="meseiroDlgErr" class="meseiro-err" hidden></p>' +
      '<div class="form-actions"><button type="button" class="btn" id="meseiroDlgOk">Beküldés az adminnak</button>' +
      '<button type="button" class="btn btn-ghost" id="meseiroDlgCancel">Mégse</button></div></div>';
    document.body.appendChild(wrap);
    var err = wrap.querySelector("#meseiroDlgErr");
    function fail(m) {
      err.textContent = m;
      err.hidden = false;
    }
    wrap.querySelector("#meseiroDlgCancel").addEventListener("click", function () {
      wrap.remove();
    });
    wrap.querySelector("#meseiroDlgOk").addEventListener("click", async function (ev) {
      var btn = ev.currentTarget;
      var author = wrap.querySelector("#meseiroAuthor").value.trim();
      if (author.length < 2) return fail("Adj meg szerzői nevet (legalább 2 karakter).");
      if (!wrap.querySelector("#meseiroConsent").checked) return fail("A beküldéshez el kell fogadnod a nyilatkozatot.");
      btn.disabled = true;
      err.hidden = true;
      try {
        if (beforeSubmit) await beforeSubmit();
        await origApi.call(auth, "/my/storybooks/" + bookId + "/submit", {
          method: "POST",
          body: JSON.stringify({ author_name: author, consent: true }),
        });
        wrap.remove();
        toast("A mese beküldve. Az admin hamarosan átnézi.", true);
        setTimeout(function () {
          location.href = "/meseiro#storybooks";
          location.reload();
        }, 900);
      } catch (e) {
        btn.disabled = false;
        fail(e && e.message ? e.message : "A beküldés nem sikerült.");
      }
    });
  }

  function waitSaveDone() {
    // A szerkesztő Mentés gombja elmenti az aktuális oldalt és a könyvet is.
    var btn = document.getElementById("btnSbSaveBook");
    if (!btn) return Promise.resolve();
    btn.click();
    return new Promise(function (resolve) {
      var tries = 0;
      (function poll() {
        tries++;
        if (!btn.disabled || tries > 150) return resolve();
        setTimeout(poll, 100);
      })();
    });
  }

  // ---------------------------------------------------------------- DOM kiegészítések
  var STATUS_LABEL = { draft: "Piszkozat", submitted: "Beküldve — az admin átnézi", published: "Publikálva" };

  function decorateList() {
    var mount = document.getElementById("storybooksAdminMount");
    if (!mount) return;
    mount.querySelectorAll(".sb-book-card[data-sb-card-id]").forEach(function (card) {
      if (card.dataset.meseiro) return;
      var id = parseInt(card.getAttribute("data-sb-card-id"), 10);
      var it = state.items[id];
      if (!it) return;
      card.dataset.meseiro = "1";
      var badge = card.querySelector(".badge");
      if (badge) {
        badge.textContent = STATUS_LABEL[it.submission_status] || it.submission_status;
        badge.className = "badge " + (it.submission_status === "published" ? "badge-done" : "badge-draft");
      }
      var actions = card.querySelector(".sb-book-card-actions");
      var body = card.querySelector(".sb-book-card-body");
      if (!it.can_edit) {
        card.querySelectorAll("[data-sb-open],[data-sb-del]").forEach(function (x) {
          x.disabled = true;
          x.title = "Beküldött vagy publikált mese nem szerkeszthető";
        });
      }
      if (body && it.admin_note && it.submission_status === "draft") {
        var note = document.createElement("p");
        note.className = "meseiro-note";
        note.innerHTML = "<strong>Az admin üzenete:</strong> " + esc(it.admin_note);
        body.insertBefore(note, actions);
      }
      if (body && it.author_name && it.submission_status !== "draft") {
        var au = document.createElement("p");
        au.className = "meseiro-note";
        au.textContent = "Szerzői név: " + it.author_name;
        body.insertBefore(au, actions);
      }
      if (!actions) return;
      if (it.submission_status === "draft") {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "btn btn-sm";
        b.textContent = "Beküldés";
        b.addEventListener("click", function () {
          openSubmitDialog(id, it.title);
        });
        actions.appendChild(b);
      } else if (it.submission_status === "submitted") {
        var w = document.createElement("button");
        w.type = "button";
        w.className = "btn btn-ghost btn-sm";
        w.textContent = "Beküldés visszavonása";
        w.addEventListener("click", async function () {
          if (!confirm("Visszavonod a beküldést? Utána újra szerkesztheted a mesét.")) return;
          try {
            await origApi.call(auth, "/my/storybooks/" + id + "/withdraw", { method: "POST", body: "{}" });
            toast("A beküldés visszavonva.", true);
            setTimeout(function () {
              location.reload();
            }, 600);
          } catch (e) {
            toast(e && e.message ? e.message : "Nem sikerült.", false);
          }
        });
        actions.appendChild(w);
      }
    });
  }

  function addEditorSubmitButton() {
    var save = document.getElementById("btnSbSaveBook");
    if (!save || document.getElementById("btnMeseiroSubmit")) return;
    var b = document.createElement("button");
    b.type = "button";
    b.id = "btnMeseiroSubmit";
    b.className = "btn btn-sm";
    b.textContent = "Beküldés az adminnak";
    b.addEventListener("click", function () {
      var id = parseInt((document.getElementById("sbBookId") || {}).value, 10);
      if (!Number.isFinite(id)) return;
      var title = (document.getElementById("sbTitle") || {}).value || "";
      openSubmitDialog(id, title, waitSaveDone);
    });
    save.parentNode.insertBefore(b, save.nextSibling);
  }

  function relabel() {
    document.title = "Saját meséim — Mesencsi";
    function setText(el, text) {
      if (el && el.textContent !== text) el.textContent = text;
    }
    var t = document.querySelector("#view-storybooks-admin .page-title");
    setText(t, "Saját meséim");
    var d = document.querySelector("#view-storybooks-admin .page-desc");
    if (d && !d.dataset.meseiro) {
      d.dataset.meseiro = "1";
      var max = (state.status && state.status.max_pages) || 20;
      var books = (state.status && state.status.max_books) || 3;
      d.innerHTML =
        "Írd meg a saját mesédet a szerkesztővel! Egyszerre legfeljebb <strong>" +
        books +
        "</strong> be nem fejezett mesét tarthatsz, egy mese legfeljebb <strong>" +
        max +
        " oldalas</strong> lehet, egy kép legfeljebb 3 MB. " +
        "Ha elkészültél, <strong>küldd be az adminnak</strong>: ő átnézi, szükség esetén javít rajta, és ő dönt a közzétételről. " +
        "Beküldés után nem szerkesztheted, de visszavonhatod.";
    }
    var nav = document.querySelector('.admin-nav-item[data-nav="storybooks"]');
    setText(nav, "Saját meséim");
    setText(document.getElementById("headerLead"), "Saját meséim");
    setText(document.getElementById("logoutBtn"), "Vissza a bolthoz");
    var hu = document.getElementById("headerUser");
    if (hu && hu.textContent.indexOf("Tulajdonos") !== -1) setText(hu, hu.textContent.replace("Tulajdonos", "Szerző"));
    var aud = document.getElementById("btnSbCurPageAud");
    if (aud) {
      var box = aud.closest(".sb-editor-acc") || aud.parentElement;
      if (box) box.setAttribute("data-meseiro-hide", "1");
    }
  }

  // A kilépés gomb a boltba visz (a felhasználói munkamenet marad).
  document.addEventListener(
    "click",
    function (ev) {
      var t = ev.target;
      if (!(t instanceof Element)) return;
      if (t.closest("#logoutBtn")) {
        ev.stopImmediatePropagation();
        ev.preventDefault();
        location.href = "/";
        return;
      }
      // beküldött / publikált mese nem szerkeszthető
      var open = t.closest("[data-sb-open]");
      var del = t.closest("[data-sb-del]");
      var btn = open || del;
      if (btn) {
        var id = parseInt(btn.getAttribute(open ? "data-sb-open" : "data-sb-del"), 10);
        var it = state.items[id];
        if (it && !it.can_edit) {
          ev.stopImmediatePropagation();
          ev.preventDefault();
          toast(
            it.submission_status === "published"
              ? "A publikált mese már nem szerkeszthető."
              : "A beküldött mesét nem szerkesztheted. Vond vissza a beküldést, ha módosítanál rajta.",
            false
          );
        }
      }
    },
    true
  );

  document.addEventListener("DOMContentLoaded", function () {
    relabel();
    var mo = new MutationObserver(function () {
      decorateList();
      addEditorSubmitButton();
      relabel();
    });
    mo.observe(document.body, { childList: true, subtree: true });
    decorateList();
    addEditorSubmitButton();
  });
})();
