(function () {
  "use strict";

  function severityPill(s) {
    var map = { low: "pill-low", medium: "pill-medium", high: "pill-high", critical: "pill-risk" };
    return '<span class="pill ' + (map[s] || "pill-muted") + '">' + escapeHtml(s || "-") + "</span>";
  }
  function deliveryPill(s) {
    var map = { sent: "pill-healthy", failed: "pill-risk", skipped: "pill-muted", not_sent: "pill-muted" };
    return '<span class="pill ' + (map[s] || "pill-muted") + '">' + escapeHtml(s || "-") + "</span>";
  }

  function load() {
    API.getAdminOverview().then(function (d) {
      var s = d.stats || {};
      document.getElementById("st-users").textContent = s.total_users ?? "0";
      document.getElementById("st-email").textContent = s.email_verified ?? "0";
      document.getElementById("st-phone").textContent = s.phone_verified ?? "0";
      document.getElementById("st-alerts").textContent = s.alerts_total ?? "0";
      document.getElementById("st-emailfail").textContent = s.email_failed ?? "0";
      document.getElementById("st-smsfail").textContent = s.sms_failed ?? "0";

      var uRows = (d.users || []).map(function (u) {
        return "<tr><td><b>" + escapeHtml(u.name) + "</b>" +
          (u.is_admin ? ' <span class="pill pill-low">admin</span>' : "") + "</td>" +
          "<td>" + escapeHtml(u.email) + "</td>" +
          "<td>" + escapeHtml(u.phone || "—") + "</td>" +
          "<td>" + (u.email_verified ? '<span class="pill pill-healthy">✓</span>' : '<span class="pill pill-warning">—</span>') + "</td>" +
          "<td>" + (u.phone_verified ? '<span class="pill pill-healthy">✓</span>' : '<span class="pill pill-muted">—</span>') + "</td>" +
          "<td>" + fmtDateTime(u.created_at) + "</td></tr>";
      }).join("");
      document.getElementById("userRows").innerHTML =
        uRows || '<tr><td colspan="6" class="text-muted">No users yet.</td></tr>';

      var aRows = (d.alerts || []).map(function (a) {
        return "<tr><td><b>" + escapeHtml(a.title) + "</b>" +
          '<p class="text-sm text-muted" style="margin:2px 0 0">' + escapeHtml((a.message || "").slice(0, 90)) + "</p></td>" +
          "<td>" + severityPill(a.severity) + "</td>" +
          "<td>" + escapeHtml(a.equipment_name || "—") + "</td>" +
          "<td>" + deliveryPill(a.email_status) + "</td>" +
          "<td>" + deliveryPill(a.sms_status) + "</td>" +
          "<td>" + fmtDateTime(a.created_at) + "</td></tr>";
      }).join("");
      document.getElementById("alertRows").innerHTML =
        aRows || '<tr><td colspan="6" class="text-muted">No alerts dispatched yet.</td></tr>';
    }).catch(handleApiError);
  }

  document.getElementById("refreshBtn").addEventListener("click", load);
  load();
})();
