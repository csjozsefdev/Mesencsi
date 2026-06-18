/**
 * Home news, archive, and per-article comments (Milestone 8c).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const apiClient = ns.api || null;
  const notify = ns.notify || null;

  const newsCommentsSubmitting = new Set();

  /** @type {Record<string, Function>} */
  let deps = {};

  function api(path, opts) {
    if (apiClient && apiClient.api) return apiClient.api(path, opts);
    throw new Error("Most nem érjük el a boltot.");
  }

  async function syncCsrfToken() {
    if (apiClient && apiClient.syncCsrfToken) return apiClient.syncCsrfToken();
    return false;
  }

  function escapeHtml(s) {
    if (deps.escapeHtml) return deps.escapeHtml(s);
    return String(s);
  }

  function setAuthLine(el, text, ok) {
    if (deps.setAuthLine) return deps.setAuthLine(el, text, ok);
  }

  function isLoggedIn() {
    return deps.isShopUserLoggedIn ? !!deps.isShopUserLoggedIn() : false;
  }

  function shopProfile() {
    return deps.shopUserProfile ? deps.shopUserProfile() : null;
  }

  function newsCommentCanPost() {
    if (!isLoggedIn()) return false;
    if (deps.userIsEmailVerified)
      return deps.userIsEmailVerified(shopProfile());
    return false;
  }

  function isHomeNewsVisible() {
    const stack = $("pageStack");
    if (!stack || stack.getAttribute("data-current-view") !== "home")
      return false;
    if (stack.getAttribute("data-user-account-open") === "1") return false;
    return true;
  }

  function renderNewsBodyHtml(news) {
    const nf = window.MesencsiNewsFormat;
    const rawBody = String((news && news.body) || "");
    const rawSummary = String((news && news.summary) || "");
    if (nf && typeof nf.renderNewsHtml === "function") {
      return nf.renderNewsHtml(rawBody || rawSummary);
    }
    const paras = rawBody
      .split(/\n\s*\n/)
      .map(function (x) {
        return x.trim();
      })
      .filter(Boolean);
    return paras.length
      ? paras
          .map(function (p) {
            return "<p>" + escapeHtml(p).replace(/\n/g, "<br/>") + "</p>";
          })
          .join("")
      : "<p>" + escapeHtml(rawSummary) + "</p>";
  }

  function renderNewsImageHtml(imageUrl) {
    const raw = imageUrl != null ? String(imageUrl).trim() : "";
    if (!raw) return "";
    const u = /^https?:\/\//i.test(raw)
      ? raw
      : raw.startsWith("/")
        ? raw
        : "/" + raw;
    return (
      '<div class="hero-news-thumb"><img src="' +
      escapeHtml(u) +
      '" alt="" loading="lazy" decoding="async" /></div>'
    );
  }

  function formatNewsCommentCount(n) {
    const c = Number(n) || 0;
    if (c === 0) return "";
    if (c === 1) return "1 hozzászólás";
    return c + " hozzászólás";
  }

  function createNewsCommentsBlock(news) {
    const tpl = $("newsCommentsBlockTpl");
    if (!tpl || !tpl.content || !news || news.id == null) return null;
    const node = tpl.content.cloneNode(true);
    const block = node.querySelector("[data-news-post-comments]");
    if (!block) return null;
    const newsId = Number(news.id);
    if (!Number.isFinite(newsId)) return null;
    block.setAttribute("data-news-id", String(newsId));
    const title = String(news.title || "Hír").trim() || "Hír";
    const titleEl = block.querySelector("[data-comment-title]");
    if (titleEl) titleEl.textContent = "Hozzászólások — " + title;
    const countEl = block.querySelector("[data-comment-count]");
    const countLabel = formatNewsCommentCount(news.comment_count);
    if (countEl) {
      if (countLabel) {
        countEl.textContent = countLabel;
        countEl.hidden = false;
      } else {
        countEl.textContent = "";
        countEl.hidden = true;
      }
    }
    const label = block.querySelector("[data-comment-label]");
    if (label) label.setAttribute("for", "newsCommentBody-" + newsId);
    const bodyInput = block.querySelector("[data-comment-body]");
    if (bodyInput) bodyInput.id = "newsCommentBody-" + newsId;
    return block;
  }

  function renderNewsCommentsListHtml(items) {
    return items
      .map(function (it) {
        const dateStr = it.created_at
          ? new Date(it.created_at).toLocaleString("hu-HU", {
              dateStyle: "short",
              timeStyle: "short",
            })
          : "";
        const name = escapeHtml(it.author_display_name || "Vásárló");
        const body = escapeHtml(it.content || "");
        let av =
          '<div class="news-comment-card__avatar--ph" aria-hidden="true">💬</div>';
        if (it.author_avatar_url) {
          let u = String(it.author_avatar_url).trim();
          if (u && !/^https?:\/\//i.test(u) && !u.startsWith("/")) u = "/" + u;
          if (/^https?:\/\//i.test(u) || u.startsWith("/")) {
            av =
              '<img class="news-comment-card__avatar" src="' +
              escapeHtml(u) +
              '" alt="" loading="lazy" decoding="async" />';
          }
        }
        return (
          '<article class="news-comment-card">' +
          av +
          '<div><div class="news-comment-card__meta">' +
          name +
          " · " +
          escapeHtml(dateStr) +
          "</div>" +
          '<div class="news-comment-card__body">' +
          body +
          "</div></div></article>"
        );
      })
      .join("");
  }

  function isNewsBlockExpanded(blockEl) {
    const article = blockEl && blockEl.closest
      ? blockEl.closest("[data-news-article], .home-news-card")
      : null;
    if (!article) return true;
    return (
      article.classList.contains("home-news-article--expanded") ||
      article.classList.contains("home-news-card--expanded")
    );
  }

  async function refreshNewsCommentsBlock(blockEl) {
    if (!blockEl || !isHomeNewsVisible()) return;
    if (!isNewsBlockExpanded(blockEl)) {
      blockEl.hidden = true;
      return;
    }
    const newsId = parseInt(blockEl.getAttribute("data-news-id") || "", 10);
    if (!Number.isFinite(newsId)) return;
    blockEl.hidden = false;
    const hint = blockEl.querySelector("[data-login-hint]");
    const publishNote = blockEl.querySelector("[data-publish-note]");
    const form = blockEl.querySelector("[data-news-comment-form]");
    const logged = isLoggedIn();
    const verified = newsCommentCanPost();
    if (hint) {
      if (!logged) {
        hint.hidden = false;
        hint.textContent = "Kommenteléshez kérlek jelentkezz be.";
      } else if (!verified) {
        hint.hidden = false;
        hint.textContent =
          "Kommenteléshez erősítsd meg az e-mail címed — a Fiók → Fiók adatok menüben kérhetsz új megerősítő linket.";
      } else {
        hint.hidden = true;
        hint.textContent = "";
      }
    }
    if (form) form.hidden = !verified;
    if (publishNote) publishNote.hidden = !verified;
    const list = blockEl.querySelector("[data-comment-list]");
    const empty = blockEl.querySelector("[data-comment-empty]");
    const st = blockEl.querySelector("[data-comment-status]");
    if (st) {
      st.hidden = false;
      st.textContent = "Betöltés…";
    }
    if (list) list.innerHTML = "";
    if (empty) empty.hidden = true;
    try {
      const page = await api("/news/" + newsId + "/comments?page=1&page_size=40");
      if (st) st.hidden = true;
      const items = page && Array.isArray(page.items) ? page.items : [];
      const countEl = blockEl.querySelector("[data-comment-count]");
      const total =
        page && page.total != null ? Number(page.total) : items.length;
      const countLabel = formatNewsCommentCount(total);
      if (countEl) {
        if (countLabel) {
          countEl.textContent = countLabel;
          countEl.hidden = false;
        } else {
          countEl.hidden = true;
        }
      }
      if (!items.length) {
        if (empty) empty.hidden = false;
        return;
      }
      if (empty) empty.hidden = true;
      if (list) list.innerHTML = renderNewsCommentsListHtml(items);
    } catch (e) {
      if (st) {
        st.hidden = false;
        st.textContent = (e && e.message) || "A hozzászólások nem tölthetők be.";
      }
    }
  }

  async function refreshAllNewsCommentsOnHome() {
    if (!isHomeNewsVisible()) return;
    document
      .querySelectorAll("[data-news-post-comments]")
      .forEach(function (block) {
        if (isNewsBlockExpanded(block)) void refreshNewsCommentsBlock(block);
      });
  }

  function newsExpandToggleLabel(expanded) {
    return expanded ? "Bezárás" : "Tovább olvasom";
  }

  function setNewsExpandState(articleEl, expanded) {
    if (!articleEl) return;
    articleEl.classList.toggle("home-news-article--expanded", expanded);
    articleEl.classList.toggle("home-news-card--expanded", expanded);
    const btn = articleEl.querySelector("[data-news-expand-toggle]");
    if (btn) {
      btn.setAttribute("aria-expanded", expanded ? "true" : "false");
      btn.textContent = newsExpandToggleLabel(expanded);
    }
    const preview = articleEl.querySelector(".home-news-article__preview");
    const body = articleEl.querySelector(".home-news-article__body");
    if (preview && body) {
      if (expanded) {
        body.hidden = false;
      } else if (preview.textContent && preview.textContent.trim()) {
        body.hidden = true;
      }
    }
    const comments = articleEl.querySelector("[data-news-post-comments]");
    if (comments) comments.hidden = !expanded;
    if (expanded && comments) void refreshNewsCommentsBlock(comments);
  }

  function wireNewsExpandDelegation() {
    if (document.body.dataset.newsExpandDelegated) return;
    document.body.dataset.newsExpandDelegated = "1";
    document.body.addEventListener("click", function (e) {
      const btn =
        e.target && e.target.closest
          ? e.target.closest("[data-news-expand-toggle]")
          : null;
      if (!btn) return;
      const article = btn.closest("[data-news-article], .home-news-card");
      if (!article) return;
      const expanded = article.classList.contains("home-news-article--expanded")
        || article.classList.contains("home-news-card--expanded");
      setNewsExpandState(article, !expanded);
    });
  }

  function mountNewsArticleWithComments(container, news, opts) {
    if (!container || !news) return;
    const title = escapeHtml(String(news.title || ""));
    const bodyHtml = renderNewsBodyHtml(news);
    const img = renderNewsImageHtml(news.image_url);
    const summaryRaw = String(news.summary || "").trim();
    const summaryHtml = summaryRaw
      ? '<div class="home-news-article__preview"><p class="home-news-article__summary">' +
        escapeHtml(summaryRaw) +
        "</p></div>"
      : "";
    const articleClass =
      "home-news-article home-news-article--compact" +
      (opts && opts.featured ? " home-news-article--featured" : "");
    const bodyHidden = summaryRaw ? " hidden" : "";
    container.innerHTML =
      '<article class="' +
      articleClass +
      '" data-news-article data-news-id="' +
      escapeHtml(String(news.id)) +
      '">' +
      img +
      '<h3 class="home-news-article__title">' +
      title +
      "</h3>" +
      summaryHtml +
      '<div class="home-news-article__body hero-body"' +
      bodyHidden +
      ">" +
      bodyHtml +
      "</div>" +
      '<button type="button" class="home-news-article__toggle btn-outline-ghost" data-news-expand-toggle aria-expanded="false">' +
      newsExpandToggleLabel(false) +
      "</button></article>";
    const article = container.querySelector("[data-news-article]");
    const comments = createNewsCommentsBlock(news);
    if (article && comments) {
      comments.hidden = true;
      article.appendChild(comments);
    }
  }

  function renderHomeNewsArchiveItem(news) {
    const wrap = document.createElement("article");
    wrap.className = "home-news-card home-news-card--compact";
    wrap.setAttribute("data-news-id", String(news.id));
    const title = escapeHtml(String(news.title || ""));
    const summary = escapeHtml(String(news.summary || "").trim());
    const img = renderNewsImageHtml(news.image_url);
    wrap.innerHTML =
      img +
      '<h3 class="home-news-card__title">' +
      title +
      "</h3>" +
      (summary ? '<p class="home-news-card__summary">' + summary + "</p>" : "") +
      '<button type="button" class="home-news-card__toggle btn-outline-ghost" data-news-expand-toggle aria-expanded="false">' +
      newsExpandToggleLabel(false) +
      "</button>";
    const comments = createNewsCommentsBlock(news);
    if (comments) {
      comments.hidden = true;
      wrap.appendChild(comments);
    }
    return wrap;
  }

  async function loadHomeNews() {
    const glass = $("heroGlass");
    const archive = $("homeNewsArchive");
    const archiveList = $("homeNewsArchiveList");
    if (!glass) return;
    const fallbackHook = "Hamarosan új hírekkel érkezünk.";
    try {
      const featured = await api("/news/featured");
      if (!featured) {
        glass.innerHTML =
          '<p class="hero-hook">' +
          escapeHtml(fallbackHook) +
          '</p><div class="hero-body"><p>Egyelőre nincs megjeleníthető hír.</p></div>';
        if (archive) archive.hidden = true;
        if (archiveList) archiveList.innerHTML = "";
        syncHomeNewsChrome("home");
        return;
      }
      mountNewsArticleWithComments(glass, featured, { featured: true });
      const featuredId = Number(featured.id);
      let others = [];
      try {
        const page = await api("/news?page=1&page_size=20");
        others = page && Array.isArray(page.items) ? page.items : [];
      } catch (_) {
        others = [];
      }
      if (archive && archiveList) {
        archiveList.innerHTML = "";
        const more = others.filter(function (n) {
          return Number(n.id) !== featuredId;
        });
        if (more.length) {
          more.forEach(function (n) {
            archiveList.appendChild(renderHomeNewsArchiveItem(n));
          });
          archive.hidden = !isHomeNewsVisible();
        } else {
          archive.hidden = true;
        }
      }
      syncHomeNewsChrome("home");
      void refreshAllNewsCommentsOnHome();
    } catch (_) {
      glass.innerHTML =
        '<p class="hero-hook">' +
        escapeHtml(fallbackHook) +
        '</p><div class="hero-body"><p>A hírek betöltése nem sikerült.</p></div>';
      if (archive) archive.hidden = true;
    }
  }

  function syncHomeNewsChrome(viewName) {
    const heroBand = $("heroBand");
    const archive = $("homeNewsArchive");
    const onHome = viewName === "home";
    const stack = $("pageStack");
    const accountOpen =
      stack && stack.getAttribute("data-user-account-open") === "1";
    const showNews = onHome && !accountOpen;
    if (heroBand) heroBand.hidden = !showNews;
    if (archive) {
      const archiveList = $("homeNewsArchiveList");
      const hasItems = !!(
        archiveList &&
        archiveList.children &&
        archiveList.children.length
      );
      archive.hidden = !showNews || !hasItems;
    }
    document
      .querySelectorAll("[data-news-post-comments]")
      .forEach(function (block) {
        block.hidden = !showNews || !isNewsBlockExpanded(block);
      });
    if (showNews) void refreshAllNewsCommentsOnHome();
  }

  function wireNewsCommentSubmitDelegation() {
    if (document.body.dataset.newsCommentsDelegated) return;
    document.body.dataset.newsCommentsDelegated = "1";
    document.body.addEventListener("submit", async function (e) {
      const form =
        e.target && e.target.closest
          ? e.target.closest("[data-news-comment-form]")
          : null;
      if (!form) return;
      e.preventDefault();
      const block = form.closest("[data-news-post-comments]");
      if (!block) return;
      const newsId = parseInt(block.getAttribute("data-news-id") || "", 10);
      if (!Number.isFinite(newsId)) return;
      if (newsCommentsSubmitting.has(newsId)) return;
      const msgEl = form.querySelector("[data-comment-form-msg]");
      if (!isLoggedIn()) {
        setAuthLine(msgEl, "Kommenteléshez kérlek jelentkezz be.", false);
        return;
      }
      if (!newsCommentCanPost()) {
        setAuthLine(
          msgEl,
          "Kommenteléshez erősítsd meg az e-mail címed — a Fiók → Fiók adatok menüben.",
          false,
        );
        void refreshNewsCommentsBlock(block);
        return;
      }
      const bodyEl = form.querySelector("[data-comment-body]");
      const content = (bodyEl && bodyEl.value.trim()) || "";
      if (content.length < 2) {
        setAuthLine(msgEl, "A hozzászólás legalább 2 karakter legyen.", false);
        return;
      }
      const submitBtn = form.querySelector('button[type="submit"]');
      newsCommentsSubmitting.add(newsId);
      setAuthLine(msgEl, "", null);
      try {
        if (submitBtn) submitBtn.disabled = true;
        if (bodyEl) bodyEl.disabled = true;
        form.setAttribute("aria-busy", "true");
        setAuthLine(msgEl, "Küldés…", null);
        await syncCsrfToken();
        await api("/news/" + newsId + "/comments", {
          method: "POST",
          body: JSON.stringify({ content: content }),
        });
        if (bodyEl) bodyEl.value = "";
        const okText =
          "Közzétettük a hozzászólásod — azonnal látható ennél a hírnél.";
        setAuthLine(msgEl, okText, true);
        if (notify) notify.success(okText);
        await refreshNewsCommentsBlock(block);
        const list = block.querySelector("[data-comment-list]");
        if (list && list.lastElementChild) {
          list.lastElementChild.scrollIntoView({
            behavior: "smooth",
            block: "nearest",
          });
        }
      } catch (err) {
        const errText =
          (notify && notify.messageFromError
            ? notify.messageFromError(err, "A hozzászólás küldése sikertelen.")
            : (err && err.message) || "A hozzászólás küldése sikertelen.");
        setAuthLine(msgEl, errText, false);
        if (notify) notify.error(errText);
      } finally {
        newsCommentsSubmitting.delete(newsId);
        form.removeAttribute("aria-busy");
        if (submitBtn) submitBtn.disabled = false;
        if (bodyEl) bodyEl.disabled = false;
      }
    });
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
    wireNewsCommentSubmitDelegation();
    wireNewsExpandDelegation();
  }

  ns.news = {
    loadHomeNews,
    syncHomeNewsChrome,
    refreshAllNewsCommentsOnHome,
    refreshNewsCommentsBlock,
    init,
  };
})();
