(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});

  /*
   * Consolidation backlog (deferred): escapeHtml / formatPrice are duplicated in
   * cart.js, products.js, news.js, gallery.js, storybooks.js, discounts-ui.js,
   * news-format.js, app.js, and admin.html. Prefer ns.dom.* once modules are bundled.
   *
   * DO NOT TOUCH in readability pass: checkout.js submit handler, payments_barion.py,
   * user_auth.py login/register dual paths, mounting coupons_admin/comments_admin,
   * removing legacy V1 reader CSS/DOM without full QA.
   */

  function show(el, msg, ok) {
    el.style.display = "block";
    el.className = "status " + (ok ? "ok" : "err");
    el.textContent = msg;
  }

  function hide(el) {
    el.style.display = "none";
    el.textContent = "";
  }

  function formatPrice(n) {
    try {
      return new Intl.NumberFormat("hu-HU").format(n) + " Ft";
    } catch {
      return String(n) + " Ft";
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  ns.dom = {
    show,
    hide,
    formatPrice,
    escapeHtml,
  };
})();
