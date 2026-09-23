(function () {
  "use strict";
  var equipment = window.PRED_EQUIPMENT || [];
  var history = window.PRED_HISTORY || [];
  var modelStatus = window.PRED_MODEL_STATUS || { connected: false };
  var prefillCache = {};

  var FIELDS = [
    { key: "engine_speed", label: "Engine Speed (RPM)", hint: "Typical 800–2800" },
    { key: "engine_torque", label: "Engine Torque (Nm)", hint: "Typical 100–650" },
    { key: "engine_load", label: "Engine Load (%)", hint: "Typical up to 95" },
    { key: "coolant_temperature", label: "Coolant Temperature (°C)", hint: "Typical 70–100" },
    { key: "oil_temperature", label: "Oil Temperature (°C)", hint: "Typical 75–110" },
    { key: "oil_pressure", label: "Oil Pressure (bar)", hint: "Typical 2.0–4.5" },
    { key: "fuel_rate", label: "Fuel Rate (L/h)", hint: "Typical up to 22" },
    { key: "vehicle_speed", label: "Vehicle Speed (km/h)", hint: "Typical up to 45" },
    { key: "battery_voltage", label: "Battery Voltage (V)", hint: "Typical 12.4–14.6" },
    { key: "transmission", label: "Transmission (gear)", hint: "Typical 1–12" },
  ];

  // ---------------------------------------------------------------- //
  //  Model status banner
  // ---------------------------------------------------------------- //
  function renderModelBanner() {
    var box = document.getElementById("modelBanner");
    if (!box) return;
    if (modelStatus.connected) {
      box.innerHTML =
        '<span class="model-tag">ML model connected</span>' +
        '<span class="text-sm">Predictions on this page are produced by the trained model (model/predictive_model.pkl).</span>';
      box.style.background = "var(--ok-soft)";
      box.style.borderColor = "#bfe6cc";
    } else {
      box.innerHTML =
        '<span class="demo-tag">ML model not connected</span>' +
        '<span class="text-sm">Analyses below are <b>Demo Predictions</b> from a rule-based check. Train and save the model with ' +
        "<code>python model/train_model.py</code> to enable real model predictions.</span>";
      box.style.background = "var(--warn-soft)";
      box.style.borderColor = "#f0e3ae";
    }
  }

  // ---------------------------------------------------------------- //
  //  Equipment select + prefill
  // ---------------------------------------------------------------- //
  var eqSelect = document.getElementById("predEquip");
  var initialEid = window.PRED_EQUIPMENT_ID;

  function setEquipmentOptions() {
    eqSelect.innerHTML = '<option value="">Select equipment…</option>' +
      equipment.map(function (e) {
        return '<option value="' + e.equipment_id + '">' + escapeHtml(e.equipment_name) +
               " (" + escapeHtml(e.equipment_type) + ")</option>";
      }).join("");
    if (initialEid) eqSelect.value = String(initialEid);
  }

  function loadPrefill(eid) {
    if (!eid) return;
    if (prefillCache[eid]) return applyPrefill(prefillCache[eid]);
    API.getOperationalData(eid, 1).then(function (d) {
      var row = (d.records || [])[0];
      if (row) { prefillCache[eid] = row; applyPrefill(row); }
      else toast("No previous reading for this machine — enter values manually.", "info");
    }).catch(function () {});
  }

  function applyPrefill(row) {
    FIELDS.forEach(function (f) {
      var el = document.querySelector('#predictForm [name="' + f.key + '"]');
      if (el && row[f.key] != null) el.value = row[f.key];
    });
    var oh = document.getElementById("predHours");
    if (oh && row.operating_hours != null) oh.textContent = row.operating_hours;
  }

  // ---------------------------------------------------------------- //
  //  Analyze
  // ---------------------------------------------------------------- //
  document.getElementById("predictForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = document.getElementById("analyzeBtn");
    var eid = eqSelect.value;
    var eqEl = document.getElementById("pe-eq");
    if (!eid) { eqEl.classList.add("error"); toast("Select an equipment to analyze.", "error"); return; }

    var payload = { equipment_id: eid };
    var bad = false;
    FIELDS.forEach(function (f) {
      var el = document.querySelector('#predictForm [name="' + f.key + '"]');
      var v = el.value.trim();
      if (v === "") return;
      if (isNaN(Number(v))) {
        toast(f.label + " must be a number.", "error");
        bad = true;
        return;
      }
      payload[f.key] = Number(v);
    });
    if (bad) return;

    var resultBox = document.getElementById("predResult");
    resultBox.classList.remove("show");
    setBtnLoading(btn, true, "");
    API.predict(payload).then(function (r) {
      setBtnLoading(btn, false);
      renderResult(r, equipment.find(function (x) { return x.equipment_id === Number(eid); }));
      history.unshift(r);
    }).catch(function (err) {
      setBtnLoading(btn, false);
      handleApiError(err);
    });
  });
  eqSelect.addEventListener("change", function () {
    document.getElementById("pe-eq").classList.remove("error");
    loadPrefill(this.value);
  });

  // ---------------------------------------------------------------- //
  //  Result card
  // ---------------------------------------------------------------- //
  function renderResult(r, eq) {
    var box = document.getElementById("predResult");
    var anom = r.condition === "Anomalous";
    var color = anom ? "#ef4444" : "#22c55e";
    var riskClass = { "Low": "pill-low", "Medium": "pill-medium", "High": "pill-high" }[r.risk_level] || "pill-muted";
    var demo = r.demo || !r.model_connected;
    var why = r.explanation || "";
    box.className = "pred-result show";
    box.innerHTML =
      '<div class="pred-hero ' + (anom ? "anomalous" : "normal") + '">' +
      '<div class="k">Equipment Condition</div>' +
      "<h2>" + (anom ? "ANOMALOUS" : "NORMAL") + "</h2>" +
      '<div class="badge-row">' +
      '<span class="pill ' + riskClass + '" style="background:rgba(255,255,255,.9)">Maintenance Risk: ' + r.risk_level + "</span>" +
      (demo ? '<span class="demo-tag" style="background:#fff7e0">Demo Prediction — ML model not connected</span>'
            : '<span class="model-tag" style="background:#dcfce7">ML model prediction</span>') +
      "</div>" +
      '<div style="margin-top:10px;font-size:.85rem">' + escapeHtml(eq ? eq.equipment_name : "") + " · " +
      (r.model_connected ? "machine learning model" : "demo analysis") + "</div>" +
      "</div>" +
      '<div class="pred-body">' +
      '<div class="pred-stats">' +
      '<div class="pred-stat"><div class="k">Condition</div><div class="v" style="color:' + color + '">' + r.condition + "</div></div>" +
      '<div class="pred-stat"><div class="k">Maintenance Risk</div><div class="v">' + r.risk_level + "</div></div>" +
      '<div class="pred-stat"><div class="k">Anomaly Probability</div><div class="v">' + r.probability + "%</div>" +
      '<div class="prob-meter"><i style="width:' + Math.min(100, r.probability) + "%;background:" + color + '"></i></div></div>' +
      "</div>" +
      '<div class="pred-rec"><b>Recommendation</b><p>' + escapeHtml(r.recommendation || "") + "</p></div>" +
      (why ? '<div class="pred-why"><b>Why was this prediction generated?</b><br>' + escapeHtml(why).replace(/\n/g, "<br>") + "</div>" : "") +
      '<p class="pred-why" style="margin-top:10px"><b>Note:</b> This is a condition/anomaly indicator used as an early ' +
      "maintenance-risk signal. It does not predict the exact date of a failure and is not a mechanical diagnosis.</p>" +
      "</div>";
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ---------------------------------------------------------------- //
  //  History
  // ---------------------------------------------------------------- //
  function renderHistory() {
    var wrap = document.getElementById("predHistory");
    if (!history.length) {
      wrap.innerHTML = '<div class="empty-state"><b>No analyses yet</b><p>Run an analysis above — results are stored here.</p></div>';
      return;
    }
    wrap.innerHTML =
      '<div class="table-wrap"><table class="data"><thead><tr>' +
      "<th>Date</th><th>Equipment</th><th>Condition</th><th>Risk</th><th>Probability</th><th>Source</th><th>Recommendation</th>" +
      "</tr></thead><tbody>" +
      history.map(function (p) {
        return "<tr><td>" + fmtDateTime(p.prediction_date) + "</td>" +
          "<td><b>" + escapeHtml(p.equipment_name || ("Equipment #" + p.equipment_id)) + "</b></td>" +
          "<td>" + conditionPill(p.condition) + "</td>" +
          "<td>" + riskPill(p.risk_level) + "</td>" +
          "<td>" + p.probability + "%</td>" +
          "<td>" + (p.demo ? '<span class="demo-tag">Demo</span>' : '<span class="model-tag">Model</span>') + "</td>" +
          '<td style="max-width:300px">' + escapeHtml(p.recommendation || "") + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  // ---------------------------------------------------------------- //
  //  Init
  // ---------------------------------------------------------------- //
  renderModelBanner();
  setEquipmentOptions();
  if (initialEid) loadPrefill(initialEid);
  renderHistory();
})();