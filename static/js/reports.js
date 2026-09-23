(function () {
  "use strict";
  var reportType = "equipment";
  var rows = [];
  var headers = [];

  var TITLES = {
    equipment: "Equipment Report", maintenance: "Maintenance Report",
    prediction: "Prediction Report", risk: "Risk Report",
  };

  function load(autoGenerate) {
    var box = document.getElementById("reportWrap");
    box.innerHTML = '<div class="skeleton" style="height:200px"></div>';
    var params = { type: reportType };
    var eq = document.getElementById("repEquip").value;
    var from = document.getElementById("repFrom").value;
    var to = document.getElementById("repTo").value;
    var risk = document.getElementById("repRisk").value;
    if (eq) params.equipment_id = eq;
    if (from) params.from = from;
    if (to) params.to = to;
    if (risk) params.risk = risk;

    API.getReports(params).then(function (d) {
      rows = d.rows || [];
      headers = rows.length ? Object.keys(rows[0]) : [];
      document.getElementById("reportTitle").textContent = TITLES[reportType];
      document.getElementById("reportMeta").textContent =
        rows.length + " record(s)" +
        (from || to ? " · " + (from || "…") + " → " + (to || "…") : "") +
        (risk ? " · " + risk + " risk" : "");
      renderTable();
    }).catch(function (err) {
      box.innerHTML = "";
      handleApiError(err);
    });
  }

  function renderTable() {
    var box = document.getElementById("reportWrap");
    if (!rows.length) {
      box.innerHTML = '<div class="empty-state"><b>No records match these filters</b>' +
        "<p>Try a different date range, equipment or risk level.</p></div>";
      return;
    }
    box.innerHTML = '<div class="table-wrap"><table class="data"><thead><tr>' +
      headers.map(function (h) { return "<th>" + escapeHtml(h) + "</th>"; }).join("") +
      "</tr></thead><tbody>" +
      rows.map(function (r) {
        return "<tr>" + headers.map(function (h) {
          var v = r[h];
          return "<td>" + escapeHtml(String(v == null ? "" : v)) + "</td>";
        }).join("") + "</tr>";
      }).join("") + "</tbody></table></div>";
  }

  // ---------------------------------------------------------------- //
  //  Export
  // ---------------------------------------------------------------- //
  function toCsv() {
    if (!rows.length) return "";
    var esc = function (s) {
      s = String(s == null ? "" : s);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    var lines = [headers.map(esc).join(",")];
    rows.forEach(function (r) {
      lines.push(headers.map(function (h) { return esc(r[h]); }).join(","));
    });
    return lines.join("\r\n");
  }

  function downloadCsv() {
    if (!rows.length) return toast("Nothing to export — generate a report first.", "info");
    var blob = new Blob(["\ufeff" + toCsv()], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = reportType + "-report.csv";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 300);
    toast("Report exported as CSV.");
  }

  // ---------------------------------------------------------------- //
  //  Init
  // ---------------------------------------------------------------- //
  document.querySelectorAll(".tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      reportType = tab.dataset.type;
      load();
    });
  });
  document.getElementById("generateBtn").addEventListener("click", function () { load(); });
  document.getElementById("csvBtn").addEventListener("click", downloadCsv);
  document.getElementById("printBtn").addEventListener("click", function () { window.print(); });
  document.querySelectorAll("#repEquip, #repRisk").forEach(function (el) {
    el.addEventListener("change", function () { load(); });
  });
  document.querySelectorAll("#repFrom, #repTo").forEach(function (el) {
    el.addEventListener("change", function () { load(); });
  });

  load();
})();