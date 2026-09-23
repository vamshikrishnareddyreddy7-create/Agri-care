/* AgriCare — shared UI helpers (loaded on every authenticated page). */
(function () {
  "use strict";

  // ---------------------------------------------------------------- //
  //  Toasts
  // ---------------------------------------------------------------- //
  const toastRoot = (() => {
    let el = document.querySelector(".toast-root");
    if (!el) {
      el = document.createElement("div");
      el.className = "toast-root";
      document.body.appendChild(el);
    }
    return el;
  })();

  const TOAST_ICONS = {
    success: '<svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>',
    error: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v5"/><path d="M12 16h.01"/></svg>',
    info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 16v-5"/><path d="M12 8h.01"/></svg>',
  };

  window.toast = function (message, type = "success") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `${TOAST_ICONS[type] || TOAST_ICONS.info}<span>${escapeHtml(message)}</span>`;
    toastRoot.appendChild(el);
    requestAnimationFrame(() => el.classList.add("show"));
    setTimeout(() => {
      el.classList.remove("show");
      setTimeout(() => el.remove(), 300);
    }, 3800);
  };

  window.handleApiError = function (err) {
    toast(err && err.message ? err.message : "Something went wrong. Please try again.", "error");
    console.error(err);
  };

  // ---------------------------------------------------------------- //
  //  Modals
  // ---------------------------------------------------------------- //
  const modalRoot = document.createElement("div");
  modalRoot.className = "modal-root";
  modalRoot.innerHTML =
    '<div class="modal-backdrop" data-close></div>' +
    '<div class="modal" role="dialog" aria-modal="true">' +
    '  <div class="modal-head"><h3></h3><button class="modal-x" data-close aria-label="Close">×</button></div>' +
    '  <div class="modal-body"></div>' +
    '  <div class="modal-foot"><button class="btn btn-outline" data-close>Cancel</button>' +
    '    <button class="btn btn-primary" data-submit>Save Changes</button></div>' +
    "</div>";
  document.body.appendChild(modalRoot);

  window.openModal = function ({ title = "", body = "", submitText = "Save Changes",
                                 size = "", onSubmit = null, submitClass = "" }) {
    const box = modalRoot.querySelector(".modal");
    box.className = `modal ${size}`;
    modalRoot.querySelector(".modal-head h3").textContent = title;
    modalRoot.querySelector(".modal-body").innerHTML = body;
    const submit = modalRoot.querySelector("[data-submit]");
    submit.textContent = submitText;
    submit.className = `btn ${submitClass || "btn-primary"}`;
    submit.onclick = () => {
      if (onSubmit) onSubmit();
    };
    modalRoot.classList.add("open");
    const first = modalRoot.querySelector("input,select,textarea");
    if (first) setTimeout(() => first.focus(), 60);
  };

  window.closeModal = function () {
    modalRoot.classList.remove("open");
    modalRoot.querySelector("[data-submit]").onclick = null;
  };

  modalRoot.querySelectorAll("[data-close]").forEach((el) =>
    el.addEventListener("click", closeModal));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  // ---------------------------------------------------------------- //
  //  Confirm dialog
  // ---------------------------------------------------------------- //
  window.confirmDialog = function ({ title = "Are you sure?", message = "",
                                     confirmText = "Delete", danger = true, onConfirm }) {
    const body = `<p style="color:var(--muted);font-size:.92rem">${escapeHtml(message)}</p>`;
    openModal({
      title, body, size: "sm",
      submitText: confirmText,
      submitClass: danger ? "btn-danger" : "btn-primary",
      onSubmit: () => {
        closeModal();
        onConfirm();
      },
    });
  };

  // ---------------------------------------------------------------- //
  //  Dropdowns (profile / notifications)
  // ---------------------------------------------------------------- //
  document.addEventListener("click", (e) => {
    const dd = e.target.closest(".dropdown");
    document.querySelectorAll(".dropdown.open").forEach((d) => {
      if (!dd || d !== dd) d.classList.remove("open");
    });
    if (dd) dd.classList.toggle("open");
  });

  // ---------------------------------------------------------------- //
  //  Sidebar + mobile nav
  // ---------------------------------------------------------------- //
  const sidebar = document.querySelector(".sidebar");
  const overlay = document.querySelector(".overlay");
  const menuBtn = document.querySelector(".menu-btn");
  if (menuBtn && sidebar && overlay) {
    const close = () => { sidebar.classList.remove("open"); overlay.classList.remove("show"); };
    menuBtn.addEventListener("click", () => {
      sidebar.classList.toggle("open");
      overlay.classList.toggle("show");
    });
    overlay.addEventListener("click", close);
    sidebar.querySelectorAll(".nav-item").forEach((a) => a.addEventListener("click", close));
  }

  // ---------------------------------------------------------------- //
  //  Header search
  // ---------------------------------------------------------------- //
  window.setupHeaderSearch = function (equipmentList) {
    const input = document.getElementById("headerSearch");
    const box = document.getElementById("searchResults");
    if (!input || !box || !Array.isArray(equipmentList)) return;
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      box.innerHTML = "";
      if (!q) { box.style.display = "none"; return; }
      const matches = equipmentList.filter((e) =>
        [e.equipment_name, e.equipment_type, e.brand, e.model, e.registration_number]
          .filter(Boolean).join(" ").toLowerCase().includes(q)).slice(0, 8);
      if (!matches.length) {
        box.innerHTML = '<div class="no-result">No equipment matches “' + escapeHtml(input.value) + '”</div>';
      } else {
        matches.forEach((e) => {
          const a = document.createElement("a");
          a.href = `/equipment/${e.equipment_id}`;
          a.innerHTML = `<span>${escapeHtml(e.equipment_name)}</span>` +
            `<small>${escapeHtml(e.equipment_type)} · ${escapeHtml(e.brand || "—")} ${escapeHtml(e.model || "")} · ${escapeHtml(e.registration_number || "—")}</small>`;
          box.appendChild(a);
        });
      }
      box.style.display = "block";
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".search-wrap")) box.style.display = "none";
    });
  };

  // ---------------------------------------------------------------- //
  //  Theme
  // ---------------------------------------------------------------- //
  window.applyTheme = function (theme) {
    document.documentElement.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
    try { localStorage.setItem("agri-theme", theme); } catch (_) { /* ignore */ }
  };
  (() => {
    const saved = (() => { try { return localStorage.getItem("agri-theme"); } catch (_) { return null; } })();
    applyTheme(saved || "light");
  })();

  // ---------------------------------------------------------------- //
  //  Header notification bell
  // ---------------------------------------------------------------- //
  window.refreshNotifBadge = function () {
    API.getNotifications().then((d) => {
      const unread = (d.notifications || []).filter((n) => !n.is_read).length;
      document.querySelectorAll("[data-notif-badge]").forEach((el) => {
        el.textContent = unread || "";
        el.style.display = unread ? "block" : "none";
      });
    }).catch(() => {});
  };

  // ---------------------------------------------------------------- //
  //  Formatting helpers
  // ---------------------------------------------------------------- //
  window.escapeHtml = function (s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  };

  window.fmtDate = function (v) {
    if (!v) return "—";
    const d = new Date(v.length === 10 ? v + "T00:00:00" : v);
    if (isNaN(d)) return String(v);
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  };

  window.fmtDateTime = function (v) {
    if (!v) return "—";
    const d = new Date(v);
    if (isNaN(d)) return String(v);
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short" }) +
      ", " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  };

  window.fmtNumber = function (v) {
    const n = Number(v);
    return isNaN(n) ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: 1 });
  };

  window.fmtMoney = function (v) {
    const n = Number(v || 0);
    return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  };

  // Status pill helpers
  window.statusPill = function (status) {
    const map = {
      "Healthy": "pill-healthy", "Maintenance Due": "pill-due",
      "Warning": "pill-warning", "High Risk": "pill-risk",
    };
    return `<span class="pill ${map[status] || "pill-muted"}">${escapeHtml(status)}</span>`;
  };
  window.riskPill = function (risk) {
    const map = { "Low": "pill-low", "Medium": "pill-medium", "High": "pill-high" };
    return `<span class="pill ${map[risk] || "pill-muted"}">${escapeHtml(risk)}</span>`;
  };
  window.conditionPill = function (cond) {
    const map = { "Normal": "pill-normal", "Anomalous": "pill-anomalous" };
    return `<span class="pill ${map[cond] || "pill-muted"}">${escapeHtml(cond)}</span>`;
  };

  // ---------------------------------------------------------------- //
  //  Form loading state
  // ---------------------------------------------------------------- //
  window.setBtnLoading = function (btn, loading, label) {
    if (!btn) return;
    if (loading) {
      btn.dataset.label = btn.textContent;
      btn.classList.add("loading");
      btn.disabled = true;
    } else {
      btn.classList.remove("loading");
      btn.disabled = false;
      if (label !== undefined) btn.textContent = label;
    }
  };

  // ---------------------------------------------------------------- //
  //  Skeleton loader for charts
  // ---------------------------------------------------------------- //
  window.showChartSkeleton = function (box, lines = 4) {
    if (!box) return;
    box.innerHTML = "";
    for (let i = 0; i < lines; i++) {
      const s = document.createElement("div");
      s.className = "skeleton";
      s.style.height = "12px";
      s.style.marginBottom = "14px";
      s.style.width = `${85 - i * 8}%`;
      box.appendChild(s);
    }
  };
})();