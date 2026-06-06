/**
 * User orders panel: list, grouping, payment retry UI (Milestone 8a).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const apiClient = ns.api || null;
  const notify = ns.notify || null;

  /** @type {Record<string, Function>} */
  let deps = {};

  function api(path, opts) {
    if (apiClient && apiClient.api) return apiClient.api(path, opts);
    throw new Error("Most nem érjük el a boltot.");
  }

  function isLoggedIn() {
    return deps.isShopUserLoggedIn ? !!deps.isShopUserLoggedIn() : false;
  }

  function initPaymentRetryListener() {
    if (deps.initUserOrdersPaymentRetryListener)
      return deps.initUserOrdersPaymentRetryListener();
  }

  function shopOrderStatusHu(s) {
    const m = {
      new: "Új",
      processing: "Feldolgozás alatt",
      completed: "Teljesítve",
      cancelled: "Lemondva",
    };
    return m[s] || s || "—";
  }

  function shopPaymentStatusHu(s) {
    const m = {
      pending: "Fizetés függőben",
      paid: "Fizetve",
      failed: "Fizetés sikertelen",
      cancelled: "Fizetés lemondva",
    };
    return m[s] || s || "—";
  }

  function normalizeShopPaymentStatus(raw) {
    const s = (raw || "pending").trim().toLowerCase();
    return s === "paid" || s === "failed" || s === "cancelled" || s === "pending"
      ? s
      : "pending";
  }

  function orderGroupAllowsPaymentRetry(paymentStatus) {
    const ps = normalizeShopPaymentStatus(paymentStatus);
    return ps === "pending" || ps === "failed" || ps === "cancelled";
  }

  function groupShopOrderLines(lines) {
    if (!lines || !lines.length) return [];
    const map = new Map();
    for (let i = 0; i < lines.length; i++) {
      const row = lines[i];
      const ts = row.placed_at || "";
      const key = row.checkout_group_id
        ? String(row.checkout_group_id)
        : ts +
          "\0" +
          String(row.customer_name || "") +
          "\0" +
          String(row.shipping_address || "") +
          "\0" +
          String(row.notes || "");
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(row);
    }
    const groups = Array.from(map.values());
    groups.sort(function (a, b) {
      const ta = new Date(a[0].placed_at).getTime() || 0;
      const tb = new Date(b[0].placed_at).getTime() || 0;
      return tb - ta;
    });
    return groups.map(function (rows) {
      const ids = rows.map(function (r) {
        return r.id;
      });
      return {
        rows: rows,
        orderIds: ids,
        minId: Math.min.apply(null, ids),
        placed_at: rows[0].placed_at,
        status: rows[0].status,
        payment_status: normalizeShopPaymentStatus(rows[0].payment_status),
        checkout_group_id: rows[0].checkout_group_id || null,
        barion_payment_id: rows[0].barion_payment_id || null,
        shipping_address: rows[0].shipping_address || "",
        notes: rows[0].notes || "",
        total: rows.reduce(function (sum, r) {
          return sum + (Number(r.total_price) || 0);
        }, 0),
      };
    });
  }

  function formatOrderShippingForDisplay(raw) {
    if (deps.formatShippingAddressPlainFromRaw)
      return deps.formatShippingAddressPlainFromRaw(raw);
    const s = raw != null ? String(raw).trim() : "";
    if (!s) return "";
    try {
      const o = JSON.parse(s);
      if (o && typeof o === "object" && o.v === 2) {
        const parts = [
          o.recipient_name,
          [o.postal_code, o.city].filter(Boolean).join(" "),
          [o.street, o.house_number].filter(Boolean).join(" "),
          o.line2,
          o.country,
        ].filter(Boolean);
        return parts.join("\n");
      }
    } catch (_) {}
    return s;
  }

  function renderUserOrders(groups) {
    const list = $("userOrdersList");
    const st = $("userOrdersStatus");
    if (!list || !st) return;
    list.innerHTML = "";
    if (!groups.length) {
      st.textContent = "Még nincs rendelésed.";
      return;
    }
    st.textContent =
      groups.length === 1 ? "1 rendelés." : groups.length + " rendelés.";
    for (let i = 0; i < groups.length; i++) {
      const g = groups[i];
      const card = document.createElement("div");
      card.className = "user-order-card";
      const d = g.placed_at ? new Date(g.placed_at) : null;
      const dateStr =
        d && !isNaN(d.getTime())
          ? d.toLocaleString("hu-HU", { dateStyle: "short", timeStyle: "short" })
          : "—";
      const head = document.createElement("div");
      head.className = "user-order-card__head";
      head.textContent =
        "#" +
        g.minId +
        " · " +
        shopOrderStatusHu(g.status) +
        " · " +
        shopPaymentStatusHu(g.payment_status);
      const meta = document.createElement("div");
      meta.className = "user-order-card__meta";
      meta.textContent =
        dateStr + " · összesen " + (g.total || 0).toLocaleString("hu-HU") + " Ft";
      const linesEl = document.createElement("div");
      linesEl.className = "user-order-card__lines";
      linesEl.textContent = g.rows
        .map(function (r) {
          return (r.product_name || "Tétel") + " ×" + (r.quantity || 0);
        })
        .join(", ");
      card.appendChild(head);
      card.appendChild(meta);
      card.appendChild(linesEl);
      const shipText = formatOrderShippingForDisplay(g.shipping_address);
      if (shipText) {
        const shipEl = document.createElement("div");
        shipEl.className = "user-order-card__ship";
        shipEl.textContent = "Szállítás: " + shipText.replace(/\n/g, ", ");
        card.appendChild(shipEl);
      }
      const notesRaw = g.notes != null ? String(g.notes).trim() : "";
      if (notesRaw) {
        const notesEl = document.createElement("div");
        notesEl.className = "user-order-card__notes";
        notesEl.textContent = "Megjegyzés: " + notesRaw;
        card.appendChild(notesEl);
      }
      if (orderGroupAllowsPaymentRetry(g.payment_status)) {
        const actions = document.createElement("div");
        actions.className = "user-order-card__actions";
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.className = "btn-outline-ghost user-order-card__retry-btn";
        retryBtn.setAttribute("data-order-payment-retry", "1");
        retryBtn.setAttribute("data-order-ids", g.orderIds.join(","));
        retryBtn.setAttribute("data-order-min-id", String(g.minId));
        const retryLabel = g.rows
          .map(function (r) {
            return (r.product_name || "termék") + " ×" + (r.quantity || 0);
          })
          .join(", ");
        retryBtn.setAttribute("data-order-retry-label", retryLabel);
        retryBtn.textContent = "Fizetés újrapróbálása";
        actions.appendChild(retryBtn);
        card.appendChild(actions);
      }
      list.appendChild(card);
    }
    initPaymentRetryListener();
  }

  async function loadUserOrdersIntoPanel() {
    const st = $("userOrdersStatus");
    const list = $("userOrdersList");
    if (!isLoggedIn() || !st || !list) return;
    st.textContent = "Betöltés…";
    list.innerHTML = "";
    try {
      const lines = await api("/orders", { method: "GET" });
      const arr = Array.isArray(lines) ? lines : [];
      renderUserOrders(groupShopOrderLines(arr));
    } catch (e) {
      const msg =
        (notify && notify.messageFromError
          ? notify.messageFromError(e, "Nem sikerült betölteni a rendeléseket.")
          : (e && e.message) || "Nem sikerült betölteni a rendeléseket.");
      let shown = msg;
      if (/megerősít|verified|403/i.test(msg)) {
        shown =
          "A rendelések megtekintéséhez erősítsd meg az e-mail címed („Fiók adatok” → „Új megerősítő e-mail”).";
      }
      st.textContent = shown;
      if (notify) notify.error(shown);
    }
  }

  function resetPanel() {
    const list = $("userOrdersList");
    const st = $("userOrdersStatus");
    if (list) list.innerHTML = "";
    if (st) st.textContent = "";
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
  }

  ns.ordersUi = {
    shopOrderStatusHu,
    shopPaymentStatusHu,
    normalizeShopPaymentStatus,
    groupShopOrderLines,
    renderUserOrders,
    loadUserOrdersIntoPanel,
    resetPanel,
    init,
  };
})();
