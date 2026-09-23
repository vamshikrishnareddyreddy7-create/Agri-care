(function () {
  "use strict";
  var prefs = window.PROFILE_PREFS || {};
  var notifPrefs = window.NOTIF_PREFS || {};
  var profile = window.PROFILE || {};

  function setField(id, ok) { document.getElementById(id).classList.toggle("error", !ok); }

  // ---------------------------------------------------------------- //
  //  Account info (now includes farm name / location)
  // ---------------------------------------------------------------- //
  document.getElementById("profileForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var form = e.target;
    var btn = document.getElementById("profileSave");
    var data = {
      name: form.name.value.trim(),
      email: form.email.value.trim(),
      phone: form.phone.value.trim(),
      farm_name: form.farm_name.value.trim(),
      location: form.location.value.trim(),
    };
    var ok = data.name.length >= 2;
    var emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(data.email);
    var phoneOk = data.phone === "" || /^[+0-9 ()-]{7,20}$/.test(data.phone);
    setField("pf-name", !ok);
    setField("pf-email", !emailOk);
    if (!ok || !emailOk || !phoneOk) return;
    setBtnLoading(btn, true);
    API.updateProfile(data).then(function (d) {
      setBtnLoading(btn, false, "Save Changes");
      if (d.phone_changed) {
        toast(d.message || "Profile updated. Phone must be re-verified.", "info");
        setTimeout(function () { window.location.reload(); }, 1200);
      } else {
        toast("Profile updated.");
      }
    }).catch(function (err) {
      setBtnLoading(btn, false, "Save Changes");
      handleApiError(err);
    });
  });

  // ---------------------------------------------------------------- //
  //  Email verification (resend)
  // ---------------------------------------------------------------- //
  var resendBtn = document.getElementById("resendVerifyBtn");
  if (resendBtn) resendBtn.addEventListener("click", function () {
    setBtnLoading(resendBtn, true);
    API.resendVerification().then(function (d) {
      setBtnLoading(resendBtn, false, "Resend verification email");
      var box = document.getElementById("resendDemo");
      if (d.demo_mode && d.demo_verify_url && box) {
        box.style.display = "block";
        box.innerHTML = 'Demo mode — verification link: <a href="' + d.demo_verify_url + '">open verification page</a>';
      }
      toast(d.message || "Verification email sent.");
    }).catch(function (err) {
      setBtnLoading(resendBtn, false, "Resend verification email");
      handleApiError(err);
    });
  });

  // ---------------------------------------------------------------- //
  //  Phone OTP verification
  // ---------------------------------------------------------------- //
  var sendOtpBtn = document.getElementById("sendOtpBtn");
  if (sendOtpBtn) sendOtpBtn.addEventListener("click", function () {
    var phone = document.getElementById("otpPhone").value.trim();
    if (!/^[+0-9 ()-]{7,20}$/.test(phone)) {
      toast("Enter a valid phone number first.", "error");
      return;
    }
    setBtnLoading(sendOtpBtn, true);
    API.sendOtp(phone).then(function (d) {
      setBtnLoading(sendOtpBtn, false, "Send verification code");
      document.getElementById("otpStep2").style.display = "block";
      if (d.demo_mode && d.demo_otp) {
        var hint = document.getElementById("otpDemoHint");
        hint.style.display = "block";
        hint.innerHTML = "Demo SMS mode — your code is: <b>" + d.demo_otp + "</b> (also printed in the server log)";
      }
      toast(d.message || "Verification code sent.");
    }).catch(function (err) {
      setBtnLoading(sendOtpBtn, false, "Send verification code");
      handleApiError(err);
    });
  });

  var verifyOtpBtn = document.getElementById("verifyOtpBtn");
  if (verifyOtpBtn) verifyOtpBtn.addEventListener("click", function () {
    var phone = document.getElementById("otpPhone").value.trim();
    var code = document.getElementById("otpCode").value.trim();
    if (!/^\d{6}$/.test(code)) {
      toast("Enter the 6-digit code.", "error");
      return;
    }
    setBtnLoading(verifyOtpBtn, true);
    API.verifyOtp(phone, code).then(function (d) {
      setBtnLoading(verifyOtpBtn, false, "Verify phone");
      toast(d.message || "Phone verified.");
      setTimeout(function () { window.location.reload(); }, 1000);
      return null;
    }).catch(function (err) {
      setBtnLoading(verifyOtpBtn, false, "Verify phone");
      handleApiError(err);
    });
  });

  // ---------------------------------------------------------------- //
  //  Password
  // ---------------------------------------------------------------- //
  document.getElementById("passwordForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var form = e.target;
    var btn = document.getElementById("pwdSave");
    var cur = form.current_password.value;
    var nw = form.new_password.value;
    var cf = form.confirm_password.value;
    setField("pf-cur", !cur);
    setField("pf-new", nw.length < 6);
    setField("pf-conf", nw === "" || nw !== cf);
    if (!cur || nw.length < 6 || nw !== cf) return;
    setBtnLoading(btn, true);
    API.changePassword({ current_password: cur, new_password: nw, confirm_password: cf })
      .then(function () {
        setBtnLoading(btn, false, "Update Password");
        form.reset();
        toast("Password updated successfully.");
      }).catch(function (err) {
        setBtnLoading(btn, false, "Update Password");
        handleApiError(err);
      });
  });

  // ---------------------------------------------------------------- //
  //  Notification preferences (server-side, per requirement)
  // ---------------------------------------------------------------- //
  function renderNotifPrefs() {
    ["email_notifications", "sms_notifications", "maintenance_alerts",
     "prediction_alerts"].forEach(function (k) {
      var el = document.getElementById("npref-" + k);
      if (el) el.checked = notifPrefs[k] !== false && notifPrefs[k] !== 0;
    });
    var pm = document.getElementById("npref-preferred_method");
    if (pm) pm.value = notifPrefs.preferred_method || "email";
  }

  function saveNotifPrefs(change) {
    Object.assign(notifPrefs, change);
    API.updateNotificationPrefs(notifPrefs).then(function (d) {
      notifPrefs = d.preferences || notifPrefs;
      toast("Notification preferences saved.");
    }).catch(handleApiError);
  }

  ["email_notifications", "sms_notifications", "maintenance_alerts",
   "prediction_alerts"].forEach(function (k) {
    var el = document.getElementById("npref-" + k);
    if (el) el.addEventListener("change", function () {
      var change = {}; change[k] = el.checked; saveNotifPrefs(change);
    });
  });
  var pmSel = document.getElementById("npref-preferred_method");
  if (pmSel) pmSel.addEventListener("change", function () {
    saveNotifPrefs({ preferred_method: pmSel.value });
  });

  // ---------------------------------------------------------------- //
  //  Test alert
  // ---------------------------------------------------------------- //
  var testBtn = document.getElementById("testAlertBtn");
  if (testBtn) testBtn.addEventListener("click", function () {
    setBtnLoading(testBtn, true);
    API.sendTestAlert().then(function (d) {
      setBtnLoading(testBtn, false, "Send test alert");
      var box = document.getElementById("testAlertResult");
      if (box) {
        box.style.display = "block";
        var parts = [];
        parts.push("In-app: " + (d.delivery.in_app ? "created" : "skipped"));
        parts.push("Email: " + d.delivery.email_status +
          (d.email_simulated && d.delivery.email_status === "sent" ? " (demo — printed to server log)" : ""));
        parts.push("SMS: " + d.delivery.sms_status +
          (d.sms_simulated && d.delivery.sms_status === "sent" ? " (demo — printed to server log)" : ""));
        box.textContent = "Test alert result — " + parts.join(" · ");
      }
      toast("Test alert dispatched. Check the bell and the notification history.", "info");
    }).catch(function (err) {
      setBtnLoading(testBtn, false, "Send test alert");
      handleApiError(err);
    });
  });

  // ---------------------------------------------------------------- //
  //  Theme / language (unchanged behavior)
  // ---------------------------------------------------------------- //
  function renderPrefs() {
    var theme = document.getElementById("pref-theme");
    var lang = document.getElementById("pref-language");
    if (theme) theme.value = prefs.theme || "light";
    if (lang) lang.value = prefs.language || "en";
  }

  function savePrefs(change) {
    Object.assign(prefs, change);
    API.updatePreferences(prefs).then(function (d) {
      prefs = d.preferences || prefs;
      if ("theme" in change) {
        window.applyTheme(change.theme);
        toast("Theme changed to " + (change.theme === "dark" ? "Dark" : "Light") + ".");
      } else if ("language" in change) {
        toast("Language preference saved — additional languages are placeholders in this build.", "info");
      }
    }).catch(handleApiError);
  }

  var themeSel = document.getElementById("pref-theme");
  if (themeSel) themeSel.addEventListener("change", function () { savePrefs({ theme: themeSel.value }); });
  var langSel = document.getElementById("pref-language");
  if (langSel) langSel.addEventListener("change", function () { savePrefs({ language: langSel.value }); });

  renderNotifPrefs();
  renderPrefs();
})();
