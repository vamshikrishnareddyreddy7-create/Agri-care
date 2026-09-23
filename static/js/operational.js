(function () {
  "use strict";

  // default timestamp = now
  var nowInput = document.getElementById("manualTime");
  if (nowInput) {
    var d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    nowInput.value = d.toISOString().slice(0, 16);
  }

  // ---------------------------------------------------------------- //
  //  Manual entry
  // ---------------------------------------------------------------- //
  var NUMERIC = ["engine_speed", "engine_torque", "engine_load", "coolant_temperature",
                 "oil_temperature", "oil_pressure", "fuel_rate", "vehicle_speed",
                 "battery_voltage", "transmission", "operating_hours"];

  document.getElementById("fillDemo").addEventListener("click", function () {
    var demo = { engine_speed: 2120, engine_torque: 430, engine_load: 80,
                 coolant_temperature: 96, oil_temperature: 108, oil_pressure: 2.4,
                 fuel_rate: 12.0, vehicle_speed: 6.5, battery_voltage: 13.2,
                 transmission: 8, operating_hours: 1245 };
    NUMERIC.forEach(function (f) {
      var el = document.querySelector('#manualForm [name="' + f + '"]');
      if (el) el.value = demo[f];
    });
    toast("Sample values filled — adjust them before saving.", "info");
  });

  document.getElementById("manualForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var form = e.target;
    var btn = document.getElementById("manualSubmit");
    var equip = document.getElementById("manualEquip");
    var eqEl = document.getElementById("fm-eq");
    var data = { equipment_id: equip.value };
    var bad = false;
    NUMERIC.forEach(function (f) {
      var el = form.querySelector('[name="' + f + '"]');
      if (el && el.value !== "") {
        if (isNaN(Number(el.value))) { toast(f.replace(/_/g, " ") + " must be a number.", "error"); bad = true; }
        data[f] = Number(el.value);
      }
    });
    if (!equip.value) { eqEl.classList.add("error"); bad = true; }
    if (bad) return;
    if (nowInput.value) data.recorded_at = nowInput.value.replace("T", " ") + ":00";

    setBtnLoading(btn, true);
    API.postOperationalData(data)
      .then(function () {
        setBtnLoading(btn, false, "Save Reading");
        form.reset();
        if (nowInput) {
          var d2 = new Date();
          d2.setMinutes(d2.getMinutes() - d2.getTimezoneOffset());
          nowInput.value = d2.toISOString().slice(0, 16);
        }
        toast("Reading saved.");
        loadRecent(equip.value || "");
      }).catch(function (err) {
        setBtnLoading(btn, false, "Save Reading");
        handleApiError(err);
      });
  });
  document.getElementById("manualEquip").addEventListener("change", function () {
    document.getElementById("fm-eq").classList.remove("error");
  });

  // ---------------------------------------------------------------- //
  //  CSV upload
  // ---------------------------------------------------------------- //
  document.getElementById("csvForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = document.getElementById("csvSubmit");
    var equip = document.getElementById("csvEquip").value;
    var file = document.getElementById("csvFile").files[0];
    if (!equip) return toast("Select an equipment for the upload.", "error");
    if (!file) return toast("Choose a .csv file to upload.", "error");
    var fd = new FormData();
    fd.append("equipment_id", equip);
    fd.append("file", file);
    setBtnLoading(btn, true);
    API.uploadCsv(fd).then(function (d) {
      setBtnLoading(btn, false, "Upload CSV Data");
      renderSummary(d.summary);
      toast(d.summary.records + " records uploaded.");
      e.target.reset();
      loadRecent(equip);
    }).catch(function (err) {
      setBtnLoading(btn, false, "Upload CSV Data");
      handleApiError(err);
    });
  });

  function renderSummary(s) {
    var box = document.getElementById("csvSummary");
    box.classList.add("show");
    var html =
      '<div class="summary-grid">' +
      '<div class="summary-item"><div class="k">Records</div><div class="v">' + s.records + "</div></div>" +
      '<div class="summary-item"><div class="k">Equipment ID</div><div class="v">#' + s.equipment_id + "</div></div>" +
      '<div class="summary-item"><div class="k">Date range</div><div class="v">' +
      (s.date_from ? String(s.date_from).slice(0, 10) : "—") + " → " +
      (s.date_to ? String(s.date_to).slice(0, 10) : "—") + "</div></div></div>";
    var avgs = s.averages || {};
    var keys = Object.keys(avgs);
    if (keys.length) {
      html += '<p class="text-sm" style="margin:14px 0 8px;font-weight:600">Average parameter values</p>' +
        '<div class="summary-grid">' + keys.map(function (k) {
          return '<div class="summary-item"><div class="k">' + escapeHtml(k.replace(/_/g, " ")) +
            "</div><div class='v'>" + avgs[k] + "</div></div>";
        }).join("") + "</div>";
    }
    document.getElementById("csvSummaryBody").innerHTML = html;
  }

  // ---------------------------------------------------------------- //
  //  Recent readings
  // ---------------------------------------------------------------- //
  function loadRecent(eid) {
    var wrap = document.getElementById("recentWrap");
    wrap.innerHTML = '<div class="skeleton" style="height:120px"></div>';
    API.getOperationalData(eid, 20).then(function (d) {
      var rows = d.records || [];
      if (!rows.length) {
        wrap.innerHTML = '<div class="empty-state"><b>No readings yet</b><p>' +
          "Enter a reading above or upload a CSV file.</p></div>";
        return;
      }
      wrap.innerHTML =
        '<div class="table-wrap"><table class="data"><thead><tr>' +
        "<th>Time</th><th>Engine Speed</th><th>Engine Load</th><th>Coolant</th><th>Oil Temp</th>" +
        "<th>Oil Pressure</th><th>Fuel Rate</th><th>Battery</th><th>Source</th>" +
        "</tr></thead><tbody>" +
        rows.map(function (r) {
          return "<tr><td>" + fmtDateTime(r.recorded_at) + "</td>" +
            "<td>" + fmtNumber(r.engine_speed) + "</td>" +
            "<td>" + fmtNumber(r.engine_load) + "%</td>" +
            '<td>' + fmtNumber(r.coolant_temperature) + "°C</td>" +
            '<td>' + fmtNumber(r.oil_temperature) + "°C</td>" +
            "<td>" + fmtNumber(r.oil_pressure) + "</td>" +
            "<td>" + fmtNumber(r.fuel_rate) + "</td>" +
            "<td>" + fmtNumber(r.battery_voltage) + " V</td>" +
            '<td><span class="pill pill-' + (r.source === "csv" ? "info" : "muted") + '">' +
            escapeHtml(r.source === "csv" ? "CSV" : "Manual") + "</span></td></tr>";
        }).join("") + "</tbody></table></div>";
    }).catch(function (err) {
      wrap.innerHTML = "";
      handleApiError(err);
    });
  }

  document.getElementById("recentEquip").addEventListener("change", function () {
    loadRecent(this.value);
  });
  loadRecent("");
})();