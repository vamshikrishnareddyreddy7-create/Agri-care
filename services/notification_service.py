"""Notification service — the bridge between app events and delivery channels.

Pipeline (per requirement):

    Event  →  event handler  →  user preferences check
           →  severity thresholds (configurable via env)
           →  in-app alert (always) + email + SMS (per severity/prefs)
           →  delivery status recorded in the alert history

Severity ladder: low < medium < high < critical.
* In-app alerts are always created (unless the category is switched off).
* Email is sent when severity >= ALERT_EMAIL_MIN_SEVERITY and the user has
  email notifications enabled for the category.
* SMS is sent when severity >= ALERT_SMS_MIN_SEVERITY and the user has SMS
  enabled for the category and a (verified) phone number on file.

Duplicate suppression: each event carries a dedup key; an alert with the same
key is never dispatched twice (e.g. re-running a prediction for the same
machine+day does not spam the farmer).

Demo safety: with no EMAIL_HOST / SMS provider configured, both channels run
in simulated mode (printed to the server log) — nothing is ever sent to real
users by accident, and the flow can be tested end-to-end locally.
"""
from datetime import datetime

from config import Config
from services.database_service import db
from services.email_service import email_service
from services.sms_service import sms_service

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_EVENT_CATEGORY = {
    "prediction": "prediction_alerts",
    "maintenance_due": "maintenance_alerts",
    "status_critical": "maintenance_alerts",
    "recommendation": "prediction_alerts",
    "test": None,                      # test alerts ignore category switches
}


def severity_for_prediction(risk_level, probability):
    """Map a prediction result to the alert severity ladder."""
    risk = (risk_level or "Low").lower()
    if risk == "high":
        try:
            if float(probability or 0) >= Config.CRITICAL_PROBABILITY:
                return "critical"
        except (TypeError, ValueError):
            pass
        return "high"
    if risk == "medium":
        return "medium"
    return "low"


def _severity_at_least(severity, minimum):
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(minimum, 99)


def dispatch(user_id, event_type, severity, title, message,
             equipment_id=None, equipment_name=None, equipment_label=None,
             status=None, risk_level=None, predicted_problem=None,
             recommended_action=None, due_date=None, dedup_key=None,
             sms_text=None, force=False):
    """Handle one notification event end-to-end.

    Returns a dict describing what happened:
    ``{"alert_id", "duplicate", "in_app", "email_status", "sms_status"}``
    """
    prefs = db.get_notification_prefs(user_id)
    category = _EVENT_CATEGORY.get(event_type)

    # Category switches (prediction alerts / maintenance alerts) — a "test"
    # event bypasses them so users can always verify the pipeline.
    if category and not force:
        if not prefs.get(category, True):
            return {"alert_id": None, "duplicate": False, "in_app": False,
                    "email_status": "skipped", "sms_status": "skipped"}

    # Severity-class switches: farmers can mute high-risk and/or critical
    # alerts entirely (in-app + email + SMS).
    sev_class = ("high_risk_alerts" if severity == "high"
                 else "critical_alerts" if severity == "critical" else None)
    if sev_class and not force and not prefs.get(sev_class, True):
        return {"alert_id": None, "duplicate": False, "in_app": False,
                "email_status": "skipped", "sms_status": "skipped"}

    # Dedup: never re-dispatch the same event.
    alert_id, is_new = db.create_alert(
        user_id, equipment_id, equipment_name, event_type, severity,
        title, message, dedup_key=dedup_key)
    if not is_new:
        return {"alert_id": alert_id, "duplicate": True, "in_app": False,
                "email_status": "skipped", "sms_status": "skipped"}

    # 1) In-app notification (dashboard bell + notifications page).
    db.create_notification(user_id, title, message,
                           "risk" if severity in ("high", "critical") else
                           ("prediction" if event_type in ("prediction", "recommendation")
                            else "maintenance"))

    profile = db.get_profile(user_id)
    user_name = (profile or {}).get("name", "")
    user_email = (profile or {}).get("email", "")
    user_phone = (profile or {}).get("phone", "")
    dashboard_url = _dashboard_url(equipment_id)

    email_status, sms_status = "not_sent", "not_sent"

    # 2) Email.
    if _severity_at_least(severity, Config.ALERT_EMAIL_MIN_SEVERITY) \
            and prefs.get("email_notifications", True) and user_email:
        ok = email_service.send_alert_email(
            user_email, user_name, equipment_name or "Equipment",
            equipment_label or (f"EQ-{equipment_id}" if equipment_id else "—"),
            severity, status, risk_level, predicted_problem,
            recommended_action, due_date=due_date, dashboard_url=dashboard_url)
        email_status = "sent" if ok else "failed"
    else:
        email_status = "skipped"

    # 3) SMS (high-priority events only).
    if _severity_at_least(severity, Config.ALERT_SMS_MIN_SEVERITY) \
            and prefs.get("sms_notifications", False) and user_phone \
            and (profile or {}).get("phone_verified"):
        ok = sms_service.send_sms(
            user_phone, sms_text or
            f"⚠ Farm Equipment Alert: {equipment_name or 'Equipment'} has a "
            f"{severity.upper()} failure risk. Recommended action: "
            f"{recommended_action or 'Schedule maintenance'}. "
            f"Open your dashboard for details.")
        sms_status = "sent" if ok else "failed"
    else:
        sms_status = "skipped"

    db.update_alert_delivery(alert_id, email_status=email_status,
                             sms_status=sms_status)
    return {"alert_id": alert_id, "duplicate": False, "in_app": True,
            "email_status": email_status, "sms_status": sms_status}


def _dashboard_url(equipment_id=None):
    base = Config.APP_BASE_URL
    if not base:
        # Outside a request context there is no request URL; fall back to a
        # relative link (email clients need an absolute URL, so production
        # deployments should set APP_BASE_URL).
        base = "http://localhost:5000"
    if equipment_id:
        return f"{base}/equipment/{equipment_id}"
    return f"{base}/dashboard"


# ---------------------------------------------------------------------- #
#  Event handlers used by the app
# ---------------------------------------------------------------------- #
def notify_prediction(user_id, equipment, result):
    """A prediction was generated — alert if the severity threshold is met."""
    severity = severity_for_prediction(result.get("risk_level"),
                                       result.get("probability"))
    if severity == "low":
        return None                     # LOW → dashboard activity only
    condition = result.get("condition", "Anomalous")
    prob = result.get("probability")
    title = (f"{'🚨 Critical' if severity == 'critical' else '⚠️ High'} "
             f"maintenance risk — {equipment['equipment_name']}")
    message = (f"{condition} condition detected ({prob}% anomaly probability). "
               f"{result.get('recommendation', '')}")
    day = datetime.now().strftime("%Y-%m-%d")
    return dispatch(
        user_id, "prediction", severity, title, message,
        equipment_id=equipment["equipment_id"],
        equipment_name=equipment["equipment_name"],
        equipment_label=equipment.get("registration_number") or f"EQ-{equipment['equipment_id']:03d}",
        status=equipment.get("status"), risk_level=result.get("risk_level"),
        predicted_problem=f"{condition} operating condition detected",
        recommended_action=result.get("recommendation"),
        dedup_key=f"prediction:{equipment['equipment_id']}:{day}:{severity}",
        sms_text=(f"⚠ Farm Equipment Alert: {equipment['equipment_name']} has a "
                  f"{result.get('risk_level', 'HIGH')} failure risk "
                  f"({prob}%). Recommended action: schedule maintenance. "
                  f"Open your dashboard for details."))


def notify_recommendation(user_id, equipment, result):
    """A new maintenance recommendation was generated (anomalous condition)."""
    if result.get("condition") != "Anomalous":
        return None
    severity = severity_for_prediction(result.get("risk_level"),
                                       result.get("probability"))
    title = f"New maintenance recommendation — {equipment['equipment_name']}"
    message = result.get("recommendation", "")
    day = datetime.now().strftime("%Y-%m-%d")
    return dispatch(
        user_id, "recommendation", severity, title, message,
        equipment_id=equipment["equipment_id"],
        equipment_name=equipment["equipment_name"],
        equipment_label=equipment.get("registration_number") or f"EQ-{equipment['equipment_id']:03d}",
        status=equipment.get("status"), risk_level=result.get("risk_level"),
        predicted_problem="Abnormal operating pattern detected",
        recommended_action=result.get("recommendation"),
        dedup_key=f"recommendation:{equipment['equipment_id']}:{day}",
        sms_text=(f"⚠ AgriCare: new maintenance recommendation for "
                  f"{equipment['equipment_name']}. {message[:120]}"))


def notify_maintenance_scheduled(user_id, equipment, record):
    """A scheduled/overdue maintenance approach or due date."""
    due = record.get("next_service_date")
    severity = "medium"
    title = f"Maintenance due — {equipment['equipment_name']}"
    message = (f"Service ({record.get('service_type', 'maintenance')}) is "
               f"scheduled{' for ' + str(due) if due else ''}.")
    return dispatch(
        user_id, "maintenance_due", severity, title, message,
        equipment_id=equipment["equipment_id"],
        equipment_name=equipment["equipment_name"],
        equipment_label=equipment.get("registration_number") or f"EQ-{equipment['equipment_id']:03d}",
        status=equipment.get("status"), due_date=due,
        recommended_action=f"Plan the {record.get('service_type', 'service').lower()} "
                           f"and confirm the appointment.",
        dedup_key=f"maintenance_due:{equipment['equipment_id']}:{due or 'none'}")


def notify_status_critical(user_id, equipment, previous_status):
    """Equipment status flipped to High Risk / critical."""
    if equipment.get("status") != "High Risk":
        return None
    day = datetime.now().strftime("%Y-%m-%d")
    return dispatch(
        user_id, "status_critical", "critical",
        f"🚨 Equipment health critical — {equipment['equipment_name']}",
        f"The status changed from {previous_status or 'previous state'} to "
        f"High Risk. Inspect the machine before further use.",
        equipment_id=equipment["equipment_id"],
        equipment_name=equipment["equipment_name"],
        equipment_label=equipment.get("registration_number") or f"EQ-{equipment['equipment_id']:03d}",
        status=equipment.get("status"), risk_level="High",
        predicted_problem="Equipment status changed to critical (High Risk)",
        recommended_action="Inspect the cooling system, engine temperature and "
                           "oil condition; consult a technician before heavy use.",
        dedup_key=f"status_critical:{equipment['equipment_id']}:{day}")


def send_test_alert(user_id):
    """Development/test helper: exercise the full pipeline without real
    equipment. Delivered through the same prefs/threshold logic."""
    profile = db.get_profile(user_id) or {}
    return dispatch(
        user_id, "test", "high", "🔔 Test alert — notification pipeline check",
        "This is a test alert generated from your profile page. If you can "
        "read this, the notification pipeline works.",
        equipment_name="Test Tractor", equipment_label="TEST-001",
        status="High Risk", risk_level="High",
        predicted_problem="Test event (not a real diagnosis)",
        recommended_action="No action needed — this was a test.",
        dedup_key=f"test:{user_id}:{datetime.now().strftime('%Y%m%d%H%M%S')}",
        sms_text="⚠ AgriCare TEST alert: notification pipeline check. No action needed.",
        force=True)
