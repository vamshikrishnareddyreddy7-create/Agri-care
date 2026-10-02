(function () {
  "use strict";
  var items = window.EQUIPMENT || [];
  var listView = false;

  var TYPES = [
    "Tractor", "Harvester", "Cultivator", "Seed drill", "Sprayer",
    "Rotavator", "Water pump", "Tiller", "Irrigation Pump", "Other farm machinery"
  ];
  var STATUSES = ["Healthy", "Maintenance Due", "Warning", "High Risk"];
  var FREQUENCIES = ["Daily", "Weekly", "Seasonal", "Occasional"];

  // ---------------------------------------------------------------- //
  //  Helpers
  // ---------------------------------------------------------------- //
  function typeIcon(type) {
    return '<svg viewBox="0 0 24 24"><path d="M3 21h18"/><path d="M5 21V10l7-6 7 6v11"/><path d="M9 21v-6h6v6"/></svg>';
  }

  function riskColor(risk) {
    return { "Low": "#22c55e", "Medium": "#f59e0b", "High": "#ef4444" }[risk] || "#94a3b8";
  }

  function filtered() {
    var q = document.getElementById("eqSearch").value.trim().toLowerCase();
    var t = document.getElementById("typeFilter").value;
    var s = document.getElementById("statusFilter").value;
    var r = document.getElementById("riskFilter").value;
    return items.filter(function (e) {
      var hay = [e.equipment_name, e.equipment_type, e.brand, e.model, e.year,
                 e.registration_number, e.location].filter(Boolean).join(" ").toLowerCase();
      return (!q || hay.includes(q)) && (!t || e.equipment_type === t) &&
             (!s || e.status === s) && (!r || e.risk_level === r);
    });
  }

  // ---------------------------------------------------------------- //
  //  Rendering
  // ---------------------------------------------------------------- //
  function emptyState(container) {
    container.innerHTML =
      '<div class="card empty-state" style="grid-column:1/-1">' +
      '<div class="e-ic"><svg viewBox="0 0 24 24"><path d="M20 7h-8l-2-3H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"/></svg></div>' +
      "<b>No equipment found</b><p>" + (items.length ? "Try changing your search or filters." :
        "Add your first machine to start tracking its health.") + "</p>" +
      '<button class="btn btn-primary btn-sm" id="emptyAdd">+ Add Equipment</button></div>';
    var b = document.getElementById("emptyAdd");
    if (b) b.addEventListener("click", function() { openForm(null); });
  }

  function renderCards() {
    var box = document.getElementById("cardView");
    var list = filtered();
    box.classList.remove("hidden");
    document.getElementById("tableView").classList.add("hidden");
    if (!list.length) return emptyState(box);
    box.innerHTML = list.map(function (e) {
      var lastSvc = e.last_service_date ? fmtDate(e.last_service_date) : "—";
      var nextSvc = e.next_service_date ? fmtDate(e.next_service_date) : "—";
      var pct = e.risk_probability != null ? e.risk_probability : 0;
      var currentYear = new Date().getFullYear();
      var age = e.year ? Math.max(0, currentYear - e.year) + " yrs" : "—";

      return (
        '<div class="equip-card">' +
        '  <div class="e-top">' +
        '    <div style="display:flex;gap:12px;min-width:0">' +
        '      <span class="e-avatar">' + typeIcon(e.equipment_type) + '</span>' +
        '      <div style="min-width:0">' +
        '        <a class="e-name" href="/equipment/' + e.equipment_id + '">' + escapeHtml(e.equipment_name) + '</a>' +
        '        <div class="e-type">' + escapeHtml(e.equipment_type) + " · " +
                    escapeHtml(e.registration_number || ("EQ-" + String(e.equipment_id).padStart(3, "0"))) + '</div>' +
        '      </div></div>' +
        '    <span>' + statusPill(e.status) + '</span>' +
        '  </div>' +
        '  <div class="equip-meta">' +
        '    <div>Brand<b>' + escapeHtml(e.brand || "—") + '</b></div>' +
        '    <div>Model<b>' + escapeHtml(e.model || "—") + '</b></div>' +
        '    <div>Age<b>' + age + '</b></div>' +
        '    <div>Hours<b>' + fmtNumber(e.operating_hours) + ' h</b></div>' +
        '    <div>Fuel Rate<b>' + (e.fuel_consumption ? e.fuel_consumption + ' L/h' : '—') + '</b></div>' +
        '    <div>Risk<b>' + riskPill(e.risk_level) + '</b></div>' +
        '    <div>Location<b>' + escapeHtml(e.location || "Farm Yard") + '</b></div>' +
        '    <div>Next Service<b>' + escapeHtml(nextSvc) + '</b></div>' +
        '  </div>' +
        '  <div class="risk-bar"><i style="width:' + Math.min(100, pct) + '%;background:' + riskColor(e.risk_level) + '"></i></div>' +
        '  <div class="e-actions">' +
        '    <a class="btn btn-outline btn-sm" href="/equipment/' + e.equipment_id + '">Details</a>' +
        '    <a class="btn btn-outline btn-sm" href="/prediction?equipment_id=' + e.equipment_id + '">AI Predict</a>' +
        '    <button class="icon-btn text" data-edit="' + e.equipment_id + '">Edit</button>' +
        '    <button class="icon-btn danger" data-del="' + e.equipment_id + '" style="margin-left:auto" title="Delete">' +
        '      <svg viewBox="0 0 24 24"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></button>' +
        '  </div>' +
        '</div>');
    }).join("");
    bindActions(box);
  }

  function renderTable() {
    var box = document.getElementById("tableView");
    var list = filtered();
    document.getElementById("cardView").classList.add("hidden");
    box.classList.remove("hidden");
    if (!list.length) return emptyState(box);
    box.innerHTML =
      '<table class="data"><thead><tr>' +
      "<th>Reg / ID</th><th>Equipment Name</th><th>Type</th><th>Brand &amp; Model</th><th>Hours</th>" +
      "<th>Condition</th><th>Maintenance Risk</th><th>Location</th><th>Next Service</th><th>Actions</th>" +
      "</tr></thead><tbody>" +
      list.map(function (e) {
        var nextSvc = e.next_service_date ? fmtDate(e.next_service_date) : "—";
        return (
          "<tr>" +
          "<td><code>" + escapeHtml(e.registration_number || ("EQ-" + String(e.equipment_id).padStart(3, "0"))) + "</code></td>" +
          '<td><a class="eq-name" href="/equipment/' + e.equipment_id + '">' + escapeHtml(e.equipment_name) + "</a></td>" +
          "<td>" + escapeHtml(e.equipment_type) + "</td>" +
          "<td>" + escapeHtml([e.brand, e.model].filter(Boolean).join(" ") || "—") + "</td>" +
          "<td>" + fmtNumber(e.operating_hours) + " h</td>" +
          "<td>" + statusPill(e.status) + "</td>" +
          "<td>" + riskPill(e.risk_level) + "</td>" +
          "<td>" + escapeHtml(e.location || "Farm Yard") + "</td>" +
          "<td>" + escapeHtml(nextSvc) + "</td>" +
          "<td>" +
          '  <a class="btn btn-outline btn-sm" href="/equipment/' + e.equipment_id + '" style="margin-right:4px">View</a>' +
          '  <button class="icon-btn text" data-edit="' + e.equipment_id + '">Edit</button>' +
          '  <button class="icon-btn danger" data-del="' + e.equipment_id + '" title="Delete">×</button>' +
          "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table>";
    bindActions(box);
  }

  function bindActions(root) {
    root.querySelectorAll("[data-edit]").forEach(function (b) {
      b.addEventListener("click", function () {
        var e = items.find(function (x) { return x.equipment_id === Number(b.dataset.edit); });
        if (e) openForm(e);
      });
    });
    root.querySelectorAll("[data-del]").forEach(function (b) {
      b.addEventListener("click", function () {
        var e = items.find(function (x) { return x.equipment_id === Number(b.dataset.del); });
        if (!e) return;
        confirmDialog({
          title: "Delete " + e.equipment_name + "?",
          message: "This will permanently remove the equipment, its maintenance records and predictions.",
          onConfirm: function () {
            API.deleteEquipment(e.equipment_id)
              .then(function () {
                toast("Equipment deleted.");
                items = items.filter(function (x) { return x.equipment_id !== e.equipment_id; });
                render();
              }).catch(handleApiError);
          },
        });
      });
    });
  }

  function render() {
    if (listView) renderTable();
    else renderCards();
  }

  // ---------------------------------------------------------------- //
  //  Add / edit form
  // ---------------------------------------------------------------- //
  function openForm(equip) {
    var e = equip || {};
    var body =
      '<form id="equipForm" novalidate><div class="form-grid">' +
      '<div class="field" id="fe-name"><label>Equipment Name <span class="req">*</span></label>' +
      '<input name="equipment_name" value="' + escapeHtml(e.equipment_name || "") + '" placeholder="e.g. Tractor TR001"><span class="err-msg">Required.</span></div>' +
      '<div class="field" id="fe-type"><label>Equipment Type <span class="req">*</span></label>' +
      '<select name="equipment_type">' + TYPES.map(function (t) {
        return '<option ' + (e.equipment_type === t ? "selected" : "") + ">" + t + "</option>"; }).join("") +
      "</select><span class='err-msg'>Required.</span></div>" +
      '<div class="field"><label>Brand</label><input name="brand" value="' + escapeHtml(e.brand || "") + '" placeholder="e.g. John Deere, New Holland"></div>' +
      '<div class="field"><label>Model</label><input name="model" value="' + escapeHtml(e.model || "") + '" placeholder="e.g. 5055E"></div>' +
      '<div class="field"><label>Manufacturing Year</label><input name="year" type="number" min="1950" max="2035" value="' + escapeHtml(e.year || new Date().getFullYear()) + '"></div>' +
      '<div class="field"><label>Registration / Serial Number</label><input name="registration_number" value="' + escapeHtml(e.registration_number || "") + '" placeholder="e.g. TR-2024-001"></div>' +
      '<div class="field"><label>Purchase Date</label><input name="purchase_date" type="date" value="' + escapeHtml(e.purchase_date || "") + '"></div>' +
      '<div class="field" id="fe-hours"><label>Operating Hours</label>' +
      '<input name="operating_hours" type="number" min="0" step="0.5" value="' + escapeHtml(e.operating_hours != null ? e.operating_hours : 0) + '"><span class="err-msg">Non-negative number.</span></div>' +
      '<div class="field"><label>Fuel Consumption (L/h)</label>' +
      '<input name="fuel_consumption" type="number" min="0" step="0.1" value="' + escapeHtml(e.fuel_consumption != null ? e.fuel_consumption : 10.0) + '"></div>' +
      '<div class="field"><label>Usage Frequency</label>' +
      '<select name="usage_frequency">' + FREQUENCIES.map(function (f) {
        return '<option ' + (e.usage_frequency === f ? "selected" : "") + ">" + f + "</option>"; }).join("") +
      "</select></div>" +
      '<div class="field"><label>Current Condition / Status</label>' +
      '<select name="status">' + STATUSES.map(function (s) {
        return '<option ' + (e.status === s ? "selected" : "") + ">" + s + "</option>"; }).join("") +
      "</select></div>" +
      '<div class="field"><label>Storage / Field Location</label>' +
      '<input name="location" value="' + escapeHtml(e.location || "Main Shed") + '" placeholder="e.g. Main Shed A, Field 4 Depot"></div>' +
      "</div></form>";

    openModal({
      title: equip ? "Edit Equipment" : "Add Equipment",
      body: body,
      submitText: equip ? "Save Changes" : "Add Equipment",
      onSubmit: function () {
        var form = document.getElementById("equipForm");
        var data = {};
        new FormData(form).forEach(function (v, k) { data[k] = v; });
        var ok = true;
        if (!data.equipment_name.trim()) { document.getElementById("fe-name").classList.add("error"); ok = false; }
        if (!data.equipment_type) { document.getElementById("fe-type").classList.add("error"); ok = false; }
        var hrs = Number(data.operating_hours);
        if (isNaN(hrs) || hrs < 0) { document.getElementById("fe-hours").classList.add("error"); ok = false; }
        if (!ok) return;

        var req = equip ? API.updateEquipment(equip.equipment_id, data) : API.createEquipment(data);
        req.then(function () {
          closeModal();
          toast(equip ? "Equipment updated." : "Equipment added.");
          reload();
        }).catch(handleApiError);
      },
    });

    ["fe-name", "fe-type", "fe-hours"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.querySelector("input,select").addEventListener("input", function () {
        el.classList.remove("error");
      });
    });
  }

  function reload() {
    API.getEquipment().then(function (d) {
      items = Array.isArray(d) ? d : (d.equipment || []);
      render();
    }).catch(handleApiError);
  }

  // ---------------------------------------------------------------- //
  //  Init & Filter Listeners
  // ---------------------------------------------------------------- //
  document.getElementById("addEquipBtn").addEventListener("click", function () { openForm(null); });
  document.getElementById("eqSearch").addEventListener("input", render);
  document.getElementById("typeFilter").addEventListener("change", render);
  document.getElementById("statusFilter").addEventListener("change", render);
  document.getElementById("riskFilter").addEventListener("change", render);

  var viewToggle = document.getElementById("viewToggle");
  if (viewToggle) {
    viewToggle.addEventListener("click", function () {
      listView = !listView;
      document.getElementById("viewLabel").textContent = listView ? "Card view" : "Table view";
      render();
    });
  }

  render();
})();
