(function () {
  "use strict";
  var records = (window.MAINTENANCE || []).map(function (r) {
    // join equipment name if the API rows include it
    return r;
  });
  var equipment = window.MAINT_EQUIPMENT || [];

  var SERVICE_TYPES = ["Regular Service", "Oil Change", "Engine Repair", "Brake Service",
                       "Transmission Service", "Cooling System", "Electrical Repair",
                       "Hydraulic Repair", "Other"];

  function equipName(eid) {
    var e = equipment.find(function (x) { return x.equipment_id === eid; });
    return e ? e.equipment_name : ("Equipment #" + eid);
  }

  function filtered() {
    var q = document.getElementById("mtSearch").value.trim().toLowerCase();
    var eid = Number(document.getElementById("mtEquip").value || 0);
    var t = document.getElementById("mtType").value;
    return records.filter(function (r) {
      var hay = [r.equipment_name || equipName(r.equipment_id), r.service_type,
                 r.problem_description, r.action_taken].filter(Boolean).join(" ").toLowerCase();
      return (!q || hay.includes(q)) && (!eid || r.equipment_id === eid) && (!t || r.service_type === t);
    });
  }

  function costCell(c) {
    var n = Number(c || 0);
    return n ? n.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—";
  }

  function render() {
    var box = document.getElementById("maintWrap");
    var list = filtered();
    if (!list.length) {
      box.innerHTML = '<div class="card empty-state"><div class="e-ic">' +
        '<svg viewBox="0 0 24 24"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-3 3-3-3z"/></svg></div>' +
        "<b>No maintenance records</b><p>" + (records.length ? "Try different filters." :
        "Record your first service to build the digital maintenance history.") + "</p>" +
        '<button class="btn btn-primary btn-sm" id="emptyAdd">+ Add Maintenance</button></div>';
      var b = document.getElementById("emptyAdd");
      if (b) b.addEventListener("click", openForm);
      return;
    }
    box.innerHTML =
      '<div class="table-wrap"><table class="data"><thead><tr>' +
      "<th>Equipment</th><th>Date</th><th>Service Type</th><th>Problem</th><th>Action Taken</th>" +
      "<th>Parts Replaced</th><th>Cost</th><th>Next Service</th><th>Status</th><th>Actions</th>" +
      "</tr></thead><tbody>" +
      list.map(function (r) {
        return "<tr>" +
          '<td><b>' + escapeHtml(r.equipment_name || equipName(r.equipment_id)) + "</b></td>" +
          "<td>" + fmtDate(r.service_date) + "</td>" +
          '<td><span class="pill pill-info">' + escapeHtml(r.service_type) + "</span></td>" +
          '<td style="max-width:180px">' + escapeHtml(r.problem_description || "—") + "</td>" +
          '<td style="max-width:200px">' + escapeHtml(r.action_taken || "—") + "</td>" +
          '<td style="max-width:140px">' + escapeHtml(r.parts_replaced || "—") + "</td>" +
          "<td><b>" + costCell(r.cost) + "</b></td>" +
          "<td>" + fmtDate(r.next_service_date) + "</td>" +
          "<td>" + statusPill(r.status || "Completed") + "</td>" +
          '<td><div class="actions-cell">' +
          '<button class="icon-btn" data-edit="' + r.maintenance_id + '" title="Edit"><svg viewBox="0 0 24 24"><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg></button>' +
          '<button class="icon-btn danger" data-del="' + r.maintenance_id + '" title="Delete"><svg viewBox="0 0 24 24"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg></button>' +
          "</div></td></tr>";
      }).join("") + "</tbody></table></div>";

    box.querySelectorAll("[data-edit]").forEach(function (b) {
      b.addEventListener("click", function () {
        var r = records.find(function (x) { return x.maintenance_id === Number(b.dataset.edit); });
        if (r) openForm(r);
      });
    });
    box.querySelectorAll("[data-del]").forEach(function (b) {
      b.addEventListener("click", function () {
        var r = records.find(function (x) { return x.maintenance_id === Number(b.dataset.del); });
        if (!r) return;
        confirmDialog({
          title: "Delete maintenance record?",
          message: "The " + r.service_type + " record for " +
                   (r.equipment_name || equipName(r.equipment_id)) + " on " + r.service_date +
                   " will be removed permanently.",
          onConfirm: function () {
            API.deleteMaintenance(r.maintenance_id).then(function () {
              toast("Maintenance record deleted.");
              records = records.filter(function (x) { return x.maintenance_id !== r.maintenance_id; });
              render();
            }).catch(handleApiError);
          },
        });
      });
    });
  }

  // ---------------------------------------------------------------- //
  //  Add / edit form
  // ---------------------------------------------------------------- //
  function openForm(rec) {
    var r = rec || {};
    var body =
      '<form id="maintForm" novalidate><div class="form-grid">' +
      '<div class="field" id="fm-eq"><label>Equipment <span class="req">*</span></label>' +
      '<select name="equipment_id">' +
      (r.equipment_id ? "" : '<option value="">Select equipment…</option>') +
      equipment.map(function (e) {
        return '<option value="' + e.equipment_id + '" ' + (r.equipment_id === e.equipment_id ? "selected" : "") +
          ">" + escapeHtml(e.equipment_name) + " (" + escapeHtml(e.equipment_type) + ")</option>";
      }).join("") + "</select><span class='err-msg'>Select an equipment.</span></div>" +
      '<div class="field" id="fm-date"><label>Service Date <span class="req">*</span></label>' +
      '<input name="service_date" type="date" value="' + escapeHtml(r.service_date || "") + '"><span class="err-msg">Required.</span></div>' +
      '<div class="field"><label>Service Type</label><select name="service_type">' +
      SERVICE_TYPES.map(function (t) {
        return '<option ' + (r.service_type === t ? "selected" : "") + ">" + t + "</option>";
      }).join("") + "</select></div>" +
      '<div class="field"><label>Status</label><select name="status">' +
      ["Completed", "Scheduled", "In Progress"].map(function (s) {
        return '<option ' + (r.status === s ? "selected" : "") + ">" + s + "</option>";
      }).join("") + "</select></div>" +
      '<div class="field full"><label>Problem Description</label>' +
      '<textarea name="problem_description" placeholder="What did you notice?">' + escapeHtml(r.problem_description || "") + "</textarea></div>" +
      '<div class="field full"><label>Action Taken</label>' +
      '<textarea name="action_taken" placeholder="What was done?">' + escapeHtml(r.action_taken || "") + "</textarea></div>" +
      '<div class="field"><label>Parts Replaced</label>' +
      '<input name="parts_replaced" value="' + escapeHtml(r.parts_replaced || "") + '"></div>' +
      '<div class="field" id="fm-cost"><label>Maintenance Cost</label>' +
      '<input name="cost" type="number" min="0" step="0.01" value="' + escapeHtml(r.cost != null ? r.cost : "") + '"><span class="err-msg">Non-negative number.</span></div>' +
      '<div class="field"><label>Next Service Date</label>' +
      '<input name="next_service_date" type="date" value="' + escapeHtml(r.next_service_date || "") + '"></div>' +
      '<div class="field"><label></label><p class="hint">Leave blank if not scheduled.</p></div>' +
      "</div></form>";

    openModal({
      title: rec ? "Edit Maintenance Record" : "Add Maintenance Record",
      body: body,
      submitText: rec ? "Save Changes" : "Add Record",
      onSubmit: function () {
        var form = document.getElementById("maintForm");
        var data = {};
        new FormData(form).forEach(function (v, k) { data[k] = v; });
        var ok = true;
        if (!data.equipment_id) { document.getElementById("fm-eq").classList.add("error"); ok = false; }
        if (!data.service_date) { document.getElementById("fm-date").classList.add("error"); ok = false; }
        if (data.cost !== "" && (isNaN(Number(data.cost)) || Number(data.cost) < 0)) {
          document.getElementById("fm-cost").classList.add("error"); ok = false;
        }
        if (!ok) return;
        var req = rec
          ? API.updateMaintenance(rec.maintenance_id, data)
          : API.createMaintenance(data);
        req.then(function () {
          closeModal();
          toast(rec ? "Maintenance record updated." : "Maintenance recorded.");
          reload();
        }).catch(handleApiError);
      },
    });
    ["fm-eq", "fm-date", "fm-cost"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.querySelector("input,select").addEventListener("input", function () {
        el.classList.remove("error");
      });
    });
  }

  function reload() {
    var eid = document.getElementById("mtEquip").value || "";
    API.getMaintenance(eid).then(function (d) {
      records = d.maintenance || [];
      render();
    }).catch(handleApiError);
  }

  // Preselect equipment when navigated from another page
  if (window.MAINT_FILTER_EQUIPMENT) {
    document.addEventListener("DOMContentLoaded", function () {
      var sel = document.getElementById("mtEquip");
      if (sel) {
        sel.value = String(window.MAINT_FILTER_EQUIPMENT);
        render();
      }
    });
  }

  document.getElementById("addMaintBtn").addEventListener("click", function () { openForm(null); });
  ["mtSearch", "mtEquip", "mtType"].forEach(function (id) {
    document.getElementById(id).addEventListener("input", render);
    document.getElementById(id).addEventListener("change", render);
  });
  render();
})();