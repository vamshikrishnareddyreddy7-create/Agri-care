(function () {
  "use strict";
  var equipment = window.PRED_EQUIPMENT || [];
  var history = window.PRED_HISTORY || [];
  var modelStatus = window.PRED_MODEL_STATUS || { connected: true };
  var prefillCache = {};

  var FIELDS = [
    { key: "vibration", label: "Vibration Level", isSelect: true },
    { key: "noise", label: "Engine Noise", isSelect: true },
    { key: "smoke", label: "Exhaust Smoke", isSelect: true },
    { key: "temperature_condition", label: "Temperature Condition", isSelect: true },
    { key: "oil_condition", label: "Oil Condition", isSelect: true },
    { key: "usage_frequency", label: "Usage Frequency", isSelect: true },
    { key: "operating_hours", label: "Operating Hours" },
    { key: "days_since_service", label: "Days Since Last Service" },
    { key: "fuel_consumption", label: "Fuel Consumption" },
    { key: "previous_failures", label: "Previous Failure Count" },
    { key: "coolant_temperature", label: "Coolant Temperature" },
    { key: "oil_pressure", label: "Oil Pressure" },
  ];

  // ---------------------------------------------------------------- //
  //  Equipment select + prefill
  // ---------------------------------------------------------------- //
  var eqSelect = document.getElementById("predEquip");
  var initialEid = window.PRED_EQUIPMENT_ID;

  function setEquipmentOptions() {
    if (!eqSelect) return;
    eqSelect.innerHTML = '<option value="">Select equipment…</option>' +
      equipment.map(function (e) {
        return '<option value="' + e.equipment_id + '">' + escapeHtml(e.equipment_name) +
               " (" + escapeHtml(e.equipment_type) + ")</option>";
      }).join("");
    if (initialEid) eqSelect.value = String(initialEid);
  }

  function loadPrefill(eid) {
    if (!eid) return;
    var eq = equipment.find(function(x) { return x.equipment_id === Number(eid); });
    if (eq) {
      var ohEl = document.querySelector('#predictForm [name="operating_hours"]');
      if (ohEl && eq.operating_hours != null) ohEl.value = eq.operating_hours;
      var fcEl = document.querySelector('#predictForm [name="fuel_consumption"]');
      if (fcEl && eq.fuel_consumption != null) fcEl.value = eq.fuel_consumption;
      var ufEl = document.querySelector('#predictForm [name="usage_frequency"]');
      if (ufEl && eq.usage_frequency) ufEl.value = eq.usage_frequency;
      var hSpan = document.getElementById("predHours");
      if (hSpan && eq.operating_hours != null) hSpan.textContent = eq.operating_hours + " h";
    }

    if (prefillCache[eid]) return applyPrefill(prefillCache[eid]);
    API.getOperationalData(eid, 1).then(function (d) {
      var row = (d.records || d || [])[0];
      if (row) { prefillCache[eid] = row; applyPrefill(row); }
    }).catch(function () {});
  }

  function applyPrefill(row) {
    if (!row) return;
    if (row.coolant_temperature) {
      var ct = document.querySelector('#predictForm [name="coolant_temperature"]');
      if (ct) ct.value = row.coolant_temperature;
    }
    if (row.oil_pressure) {
      var op = document.querySelector('#predictForm [name="oil_pressure"]');
      if (op) op.value = row.oil_pressure;
    }
  }

  // ---------------------------------------------------------------- //
  //  Analyze
  // ---------------------------------------------------------------- //
  var form = document.getElementById("predictForm");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = document.getElementById("analyzeBtn");
      var eid = eqSelect.value;
      var eqEl = document.getElementById("pe-eq");
      if (!eid) { eqEl.classList.add("error"); toast("Select an equipment to analyze.", "error"); return; }

      var payload = { equipment_id: eid };
      FIELDS.forEach(function (f) {
        var el = document.querySelector('#predictForm [name="' + f.key + '"]');
        if (!el) return;
        var v = el.value.trim();
        if (v === "") return;
        if (!f.isSelect && !isNaN(Number(v))) {
          payload[f.key] = Number(v);
        } else {
          payload[f.key] = v;
        }
      });

      var resultBox = document.getElementById("predResult");
      resultBox.classList.remove("show");
      setBtnLoading(btn, true, "Running AI Model…");

      API.predict(payload).then(function (r) {
        setBtnLoading(btn, false, "Run Predictive Maintenance Analysis");
        renderResult(r, equipment.find(function (x) { return x.equipment_id === Number(eid); }));
        history.unshift(r);
        renderHistory();
      }).catch(function (err) {
        setBtnLoading(btn, false, "Run Predictive Maintenance Analysis");
        handleApiError(err);
      }).finally(function() {
        setBtnLoading(btn, false, "Run Predictive Maintenance Analysis");
      });
    });
  }

  if (eqSelect) {
    eqSelect.addEventListener("change", function () {
      document.getElementById("pe-eq").classList.remove("error");
      loadPrefill(this.value);
    });
  }

  // ---------------------------------------------------------------- //
  //  Result card
  // ---------------------------------------------------------------- //
  function renderResult(r, eq) {
    var box = document.getElementById("predResult");
    if (!box) return;

    var isHigh = r.result === "HIGH RISK OF BREAKDOWN" || r.risk_level === "High";
    var isWarning = r.result === "SERVICE REQUIRED" || r.risk_level === "Medium";
    var color = isHigh ? "#ef4444" : (isWarning ? "#f59e0b" : "#22c55e");
    var riskClass = isHigh ? "pill-high" : (isWarning ? "pill-medium" : "pill-low");
    var riskPct = r.risk_percentage != null ? r.risk_percentage : (r.probability != null ? r.probability : 25);
    var resultTitle = r.result || (isHigh ? "HIGH RISK OF BREAKDOWN" : (isWarning ? "SERVICE REQUIRED" : "GOOD CONDITION"));

    var factorsHtml = (r.important_factors || []).map(function(f) {
      return '<li style="margin-bottom:6px"><b>' + escapeHtml(f.factor) + ':</b> ' + escapeHtml(f.impact) + '</li>';
    }).join("");

    var metrics = r.evaluation_metrics || {};

    box.className = "pred-result show";
    box.innerHTML =
      '<div class="pred-hero ' + (isHigh ? "anomalous" : (isWarning ? "warning" : "normal")) + '" style="background:' + (isHigh ? '#fee2e2' : (isWarning ? '#fef3c7' : '#dcfce7')) + ';border:1px solid ' + color + ';padding:20px;border-radius:12px">' +
        '<div class="k" style="font-size:.78rem;font-weight:700;text-transform:uppercase;color:' + color + '">AI Prediction Result</div>' +
        '<h2 style="color:' + color + ';margin:6px 0 10px;font-size:1.6rem;letter-spacing:-.01em">' + escapeHtml(resultTitle) + '</h2>' +
        '<div class="badge-row" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">' +
          '<span class="pill ' + riskClass + '" style="font-weight:700">Failure Risk: ' + riskPct + '%</span>' +
          '<span class="model-tag" style="background:#166534;color:#fff">Random Forest Classifier</span>' +
          (eq ? '<span style="font-size:.85rem;color:var(--text)"><b>' + escapeHtml(eq.equipment_name) + '</b></span>' : '') +
        '</div>' +
      '</div>' +

      '<div class="pred-body" style="margin-top:16px">' +
        '<div class="pred-stats" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">' +
          '<div class="card" style="padding:14px;box-shadow:none;border:1px solid var(--border)">' +
            '<div class="k" style="font-size:.75rem;color:var(--muted);text-transform:uppercase">Risk Percentage</div>' +
            '<div class="v" style="font-size:1.8rem;font-weight:800;color:' + color + '">' + riskPct + '%</div>' +
            '<div class="risk-bar" style="height:8px;background:#e2e8f0;border-radius:99px;margin-top:6px;overflow:hidden">' +
              '<i style="display:block;height:100%;width:' + Math.min(100, riskPct) + '%;background:' + color + '"></i>' +
            '</div>' +
          '</div>' +

          '<div class="card" style="padding:14px;box-shadow:none;border:1px solid var(--border)">' +
            '<div class="k" style="font-size:.75rem;color:var(--muted);text-transform:uppercase">Maintenance Urgency</div>' +
            '<div class="v" style="font-size:1.4rem;font-weight:700;margin-top:4px">' +
              (isHigh ? '<span style="color:#dc2626">Immediate Action</span>' : (isWarning ? '<span style="color:#d97706">Schedule Soon</span>' : '<span style="color:#16a34a">Routine Upkeep</span>')) +
            '</div>' +
          '</div>' +
        '</div>' +

        '<div class="card" style="margin-top:14px;padding:16px;box-shadow:none;border:1px solid var(--border)">' +
          '<h4 style="margin-bottom:8px;display:flex;align-items:center;gap:6px">' +
            '<svg viewBox="0 0 24 24" style="width:18px;height:18px;stroke:var(--primary);fill:none;stroke-width:2"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-3 3-3-3z"/></svg>' +
            'Recommended Maintenance Action' +
          '</h4>' +
          '<p style="font-size:.9rem;line-height:1.5">' + escapeHtml(r.recommendations || r.recommendation || "") + '</p>' +
        '</div>' +

        (factorsHtml ? (
          '<div class="card" style="margin-top:14px;padding:16px;box-shadow:none;border:1px solid var(--border)">' +
            '<h4 style="margin-bottom:8px">Important Input Factors &amp; Symptoms</h4>' +
            '<ul style="padding-left:18px;font-size:.88rem;color:var(--text);line-height:1.5">' + factorsHtml + '</ul>' +
          '</div>'
        ) : '') +

        (metrics && metrics.accuracy ? (
          '<div style="margin-top:14px;padding:10px 14px;background:var(--bg);border-radius:8px;border:1px solid var(--border);font-size:.78rem;color:var(--muted)">' +
            '<b>Validated ML Metrics:</b> Accuracy: ' + metrics.accuracy + '% · Precision: ' + metrics.precision + '% · Recall: ' + metrics.recall + '% · F1-Score: ' + metrics.f1_score + '%' +
          '</div>'
        ) : '') +

        '<div style="margin-top:14px;padding:10px 12px;background:#fef9c3;border-radius:8px;border:1px solid #fde047;font-size:.78rem;color:#854d0e">' +
          '<b>Disclaimer:</b> AI prediction is a decision-support tool and does not replace inspection or advice from a qualified technician.' +
        '</div>' +
      '</div>';

    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ---------------------------------------------------------------- //
  //  History
  // ---------------------------------------------------------------- //
  function renderHistory() {
    var wrap = document.getElementById("predHistory");
    if (!wrap) return;
    if (!history.length) {
      wrap.innerHTML = '<div class="empty-state"><b>No analyses yet</b><p>Run an analysis above — results are stored here.</p></div>';
      return;
    }
    wrap.innerHTML =
      '<div class="table-wrap"><table class="data"><thead><tr>' +
      "<th>Date</th><th>Equipment</th><th>AI Result</th><th>Risk Level</th><th>Risk %</th><th>Recommendation</th>" +
      "</tr></thead><tbody>" +
      history.map(function (p) {
        var res = p.result || (p.risk_level === "High" ? "HIGH RISK OF BREAKDOWN" : (p.risk_level === "Medium" ? "SERVICE REQUIRED" : "GOOD CONDITION"));
        var badgeCls = p.risk_level === "High" ? "pill-risk" : (p.risk_level === "Medium" ? "pill-warning" : "pill-healthy");
        return "<tr><td>" + fmtDateTime(p.prediction_date) + "</td>" +
          "<td><b>" + escapeHtml(p.equipment_name || ("Equipment #" + p.equipment_id)) + "</b></td>" +
          '<td><span class="pill ' + badgeCls + '">' + escapeHtml(res) + '</span></td>' +
          "<td>" + riskPill(p.risk_level) + "</td>" +
          "<td><b>" + (p.risk_percentage || p.probability || 0) + "%</b></td>" +
          '<td style="max-width:320px;font-size:.84rem">' + escapeHtml(p.recommendation || p.recommendations || "") + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  // ---------------------------------------------------------------- //
  //  Init
  // ---------------------------------------------------------------- //
  setEquipmentOptions();
  if (initialEid) loadPrefill(initialEid);
  renderHistory();
})();
