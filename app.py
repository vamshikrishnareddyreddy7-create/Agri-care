"""AgriCare — AI-Based Farm Equipment Management and Predictive Maintenance.

Flask application entry point. Runs in Demo Mode (bundled sample data) until a
MySQL database is configured via environment variables, and uses the trained
ML model when ``model/predictive_model.pkl`` exists.

Run locally:        python app.py          (http://127.0.0.1:5000)
Run in production:  gunicorn app:app
"""
import csv
import hashlib
import io
import re
import secrets
import uuid
from datetime import datetime, date, timedelta
from collections import defaultdict
from functools import wraps

import time

from flask import (Flask, render_template, request, redirect, url_for, session,
                   jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from services.database_service import db
from services import ml_service, chatbot_service
from services import notification_service
from services import google_auth
from services.email_service import email_service
from services.sms_service import sms_service

app = Flask(__name__)
app.config.from_object(Config)

# ---------------------------------------------------------------------- #
#  Template filters
# ---------------------------------------------------------------------- #
def _pill(text, cls):
    from markupsafe import Markup, escape
    return Markup(f'<span class="pill {cls}">{escape(text)}</span>')


@app.template_filter("status_pill")
def status_pill(status):
    cls = {"Healthy": "pill-healthy", "Maintenance Due": "pill-due",
           "Warning": "pill-warning", "High Risk": "pill-risk"}.get(status, "pill-muted")
    return _pill(status or "-", cls)


@app.template_filter("risk_pill")
def risk_pill(risk):
    cls = {"Low": "pill-low", "Medium": "pill-medium", "High": "pill-high"}.get(risk, "pill-muted")
    return _pill(risk or "-", cls)


@app.template_filter("condition_pill")
def condition_pill(cond):
    cls = {"Normal": "pill-normal", "Anomalous": "pill-anomalous"}.get(cond, "pill-muted")
    return _pill(cond or "-", cls)


@app.template_filter("fmt_date")
def fmt_date(value):
    if not value:
        return "—"
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return str(value)


@app.template_filter("fmt_datetime")
def fmt_datetime(value):
    if not value:
        return "—"
    try:
        return datetime.strptime(str(value)[:16], "%Y-%m-%d %H:%M").strftime("%d %b, %H:%M")
    except ValueError:
        return fmt_date(value)


@app.template_filter("money")
def money_filter(value):
    try:
        return f"{float(value or 0):,.0f} ₺"
    except (TypeError, ValueError):
        return "—"


# ---------------------------------------------------------------------- #
#  Auth helpers
# ---------------------------------------------------------------------- #
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required. Please log in."}), 401
        return view(*args, **kwargs)
    return wrapped


def verification_required(view):
    """APIs that matter require a verified email. Returns 403 with a clear
    message so the UI can point the user at the verification page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required. Please log in."}), 401
        profile = db.get_profile(session["user_id"])
        if not (profile or {}).get("email_verified"):
            return jsonify({"error": "Please verify your email address first. "
                                      "Open the verification link we emailed you."}), 403
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required. Please log in."}), 401
        profile = db.get_profile(session["user_id"])
        if not (profile or {}).get("is_admin"):
            return jsonify({"error": "Administrator access required."}), 403
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------- #
#  CSRF protection (double-submit cookie for JSON API calls)
# ---------------------------------------------------------------------- #
def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(24)
        session["_csrf_token"] = token
    return token


@app.context_processor
def inject_csrf():
    return {"csrf_token": get_csrf_token(), "email_simulated": email_service.simulated,
            "sms_simulated": sms_service.simulated}


# Endpoints that must stay reachable without a CSRF token (no authenticated
# session exists yet, or the token was just cleared by session.clear()).
CSRF_EXEMPT_ENDPOINTS = {
    "api_login", "api_register", "api_forgot_password", "api_reset_password",
    "api_verify_email", "api_logout", "api_send_email_otp",
}


@app.before_request
def csrf_guard():
    """Reject state-changing API calls that do not carry the session's CSRF
    token (header X-CSRF-Token). Page loads and safe endpoints are exempt."""
    if request.method not in ("POST", "PUT", "DELETE"):
        return None
    if not request.path.startswith("/api/"):
        return None
    if request.endpoint in CSRF_EXEMPT_ENDPOINTS:
        return None
    sent = request.headers.get("X-CSRF-Token")
    if not sent and request.is_json:
        sent = (request.get_json(silent=True) or {}).get("_csrf")
    if not sent or sent != session.get("_csrf_token"):
        return jsonify({"error": "Invalid or missing CSRF token. "
                                  "Please refresh the page and try again."}), 403
    return None


# ---------------------------------------------------------------------- #
#  Rate limiting (in-memory, per key; fine for single-process deployments)
# ---------------------------------------------------------------------- #
_rate_buckets = defaultdict(list)


def rate_limit(key, max_events, window_seconds):
    """Record an event and return True when the limit is exceeded."""
    now = time.monotonic()
    bucket = _rate_buckets[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.pop(0)
    if len(bucket) >= max_events:
        return True
    bucket.append(now)
    return False


def _client_ip():
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr or "?")


_login_attempts = defaultdict(list)          # email -> [(monotonic, ok), ...]


def _login_blocked(email):
    """Login attempt protection: after 5 failures within 10 minutes an email
    is locked out for 10 minutes."""
    now = time.monotonic()
    events = [t for t, ok in _login_attempts[email]
              if now - t < 600 and not ok]
    _login_attempts[email] = [(t, ok) for t, ok in _login_attempts[email]
                              if now - t < 600]
    return len(events) >= 5


def _record_login_attempt(email, ok):
    _login_attempts[email].append((time.monotonic(), ok))
    _login_attempts[email] = _login_attempts[email][-20:]


def current_user():
    uid = session.get("user_id")
    return db.get_user(uid) if uid else None


@app.context_processor
def inject_globals():
    user = None
    unread = 0
    if session.get("user_id"):
        user = db.get_user(session["user_id"])
        unread = db.unread_notifications(session["user_id"])
    return {
        "current_user": user,
        "demo_banner": db.demo_banner(),
        "unread_count": unread,
        "today": date.today(),
        "APP_NAME": "AgriCare",
        "active": _active_page(request.path),
    }


def _active_page(path):
    if path.startswith("/equipment") and path != "/equipment":
        return "equipment"
    mapping = {
        "/dashboard": "dashboard", "/equipment": "equipment",
        "/maintenance": "maintenance", "/operational-data": "operational",
        "/prediction": "prediction", "/chatbot": "chatbot",
        "/reports": "reports", "/notifications": "notifications",
        "/profile": "profile", "/admin": "admin",
    }
    return mapping.get(path, "")


def get_prefs():
    return session.get(f"prefs_{session.get('user_id')}", {})


def set_prefs(prefs):
    session[f"prefs_{session.get('user_id')}"] = prefs


def validate_equipment_form(data, partial=False):
    """Returns (clean_dict, error)."""
    errors = []
    name = str(data.get("equipment_name", "")).strip()
    etype = str(data.get("equipment_type", "")).strip()
    if not partial and not name:
        errors.append("Equipment name is required.")
    if not partial and not etype:
        errors.append("Equipment type is required.")
    if etype not in ("Tractor", "Harvester", "Tiller", "Irrigation Pump",
                     "Seeder", "Sprayer", "Other") and etype:
        errors.append("Unknown equipment type.")
    try:
        hours = float(data.get("operating_hours") or 0)
        if hours < 0:
            raise ValueError
    except ValueError:
        errors.append("Operating hours must be a non-negative number.")
    status = str(data.get("status", "Healthy")).strip() or "Healthy"
    return {
        "equipment_name": name or (None if partial else ""),
        "equipment_type": etype or (None if partial else ""),
        "brand": str(data.get("brand", "")).strip(),
        "model": str(data.get("model", "")).strip(),
        "year": int(data["year"]) if str(data.get("year", "")).strip().isdigit() else None,
        "registration_number": str(data.get("registration_number", "")).strip(),
        "purchase_date": str(data.get("purchase_date", "")).strip() or None,
        "operating_hours": hours,
        "status": status,
    }, " ".join(errors)


# ---------------------------------------------------------------------- #
#  Pages
# ---------------------------------------------------------------------- #
@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page. GET renders the form; POST (native form fallback when
    JavaScript is unavailable) logs the user in with email OR phone +
    password and redirects to the dashboard."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        result, status = _authenticate(
            request.form.get("email") or request.form.get("identifier"),
            request.form.get("password", ""))
        if status == 200:
            return redirect(result["redirect"])
        return render_template("login.html", error=result.get("error")), status
    return render_template("login.html",
                           google_enabled=google_auth.configured(),
                           google_error=request.args.get("google_error"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Registration page. POST is the native form fallback — same rules as
    /api/register, roles limited to Farmer/Technician."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        result, status = _register_user({
            "name": request.form.get("name", ""),
            "email": request.form.get("email", ""),
            "phone": request.form.get("phone", ""),
            "password": request.form.get("password", ""),
            "confirm_password": request.form.get("confirm_password", ""),
            "role": request.form.get("role", "Farmer"),
        })
        if status == 200:
            return redirect(result["redirect"])
        return render_template("register.html", error=result.get("error")), status
    return render_template("register.html")


@app.route("/forgot-password")
def forgot_password_page():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("forgot_password.html")


@app.route("/reset-password")
def reset_password_page():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if not request.args.get("token"):
        return redirect(url_for("forgot_password_page"))
    return render_template("reset_password.html", token=request.args.get("token"))


@app.route("/verify-email")
def verify_email_page():
    """Email-verification landing page (linked from the verification email)."""
    return render_template("verify_email.html", token=request.args.get("token", ""))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html",
                           data=db.dashboard(session["user_id"]))


@app.route("/equipment")
@login_required
def equipment_page():
    return render_template("equipment.html",
                           equipment=db.list_equipment(session["user_id"]))


@app.route("/equipment/<int:equipment_id>")
@login_required
def equipment_details(equipment_id):
    equip = db.get_equipment(session["user_id"], equipment_id)
    if not equip:
        abort(404)
    return render_template(
        "equipment_details.html",
        equipment=equip,
        maintenance=db.list_maintenance(session["user_id"], equipment_id),
        predictions=db.list_predictions(session["user_id"], equipment_id),
        latest_prediction=db.latest_prediction(session["user_id"], equipment_id),
        latest_operational=db.latest_operational(session["user_id"], equipment_id),
    )


@app.route("/maintenance")
@login_required
def maintenance_page():
    return render_template(
        "maintenance.html",
        equipment=db.list_equipment(session["user_id"]),
        maintenance=db.list_maintenance(session["user_id"]))


@app.route("/operational-data")
@login_required
def operational_data_page():
    return render_template(
        "operational_data.html",
        equipment=db.list_equipment(session["user_id"]))


@app.route("/prediction")
@login_required
def prediction_page():
    # Protected functionality requires a verified email address.
    if not (db.get_profile(session["user_id"]) or {}).get("email_verified"):
        return redirect(url_for("verify_email_page"))
    return render_template(
        "prediction.html",
        equipment=db.list_equipment(session["user_id"]),
        predictions=db.list_predictions(session["user_id"]),
        model_status=ml_service.model_status(),
        model_info=ml_service.info_text())


@app.route("/chatbot")
@login_required
def chatbot_page():
    conversations = db.list_conversations(session["user_id"])
    active = None
    messages = []
    try:
        active = int(request.args.get("c")) if request.args.get("c") else None
    except (TypeError, ValueError):
        active = None
    if active:
        conv = db.get_conversation(session["user_id"], active)
        if not conv:
            active = None
    if active:
        messages = db.list_messages(active)
    elif conversations:
        active = conversations[0]["conversation_id"]
        messages = db.list_messages(active)
    return render_template(
        "chatbot.html",
        equipment=db.list_equipment(session["user_id"]),
        conversations=conversations,
        active_conversation=active,
        messages=messages,
        quick_prompts=chatbot_service.QUICK_PROMPTS,
        disclaimer=chatbot_service.DISCLAIMER)


@app.route("/reports")
@login_required
def reports_page():
    return render_template(
        "reports.html",
        equipment=db.list_equipment(session["user_id"]))


@app.route("/notifications")
@login_required
def notifications_page():
    return render_template(
        "notifications.html",
        notifications=db.list_notifications(session["user_id"]))


@app.route("/profile")
@login_required
def profile_page():
    profile = db.get_profile(session["user_id"]) or {}
    prefs = db.get_notification_prefs(session["user_id"])
    return render_template("profile.html", profile=profile,
                           notif_prefs=prefs, prefs=get_prefs())


@app.route("/admin")
@login_required
def admin_page():
    profile = db.get_profile(session["user_id"]) or {}
    if not profile.get("is_admin"):
        abort(403)
    return render_template("admin.html")


# ---------------------------------------------------------------------- #
#  Auth API
# ---------------------------------------------------------------------- #
def _normalize_phone(phone):
    """Reduce a phone number to its digits for duplicate-resistant login."""
    return re.sub(r"[^0-9]", "", str(phone or ""))


def _authenticate(identifier, password):
    """Validate email-or-phone + password. Returns ({...}, http_status).
    On success the session is populated. Same failed-attempt throttling as
    before, keyed by the normalized identifier."""
    identifier = str(identifier or "").strip()
    password = str(password or "")
    if not identifier or not password:
        return {"error": "Enter your email or phone and password."}, 400
    if _login_blocked(identifier):
        return {"error": "Too many failed attempts for this account. "
                                  "Please try again in 10 minutes."}, 429
    if rate_limit(f"login-ip:{_client_ip()}", 20, 300):
        return {"error": "Too many attempts from this network. "
                                  "Please wait a few minutes."}, 429

    user = None
    if EMAIL_RE.match(identifier):
        user = db.get_user_by_email(identifier.lower())
    else:
        digits = _normalize_phone(identifier)
        if len(digits) >= 7:
            user = db.get_user_by_phone(identifier)
    if not user or not check_password_hash(user["password_hash"], password):
        _record_login_attempt(identifier, False)
        return {"error": "Invalid email/phone or password."}, 401
    _record_login_attempt(identifier, True)
    session.clear()
    session["user_id"] = user["user_id"]
    profile = db.get_profile(user["user_id"]) or {}
    return {"ok": True, "redirect": url_for("dashboard"),
            "email_verified": bool(profile.get("email_verified"))}, 200


VALID_ROLES = ("Farmer", "Technician")   # Admin is seeded from env only


def _register_user(data):
    """Create a Farmer/Technician account. Returns ({...}, http_status).
    The Admin role is never accepted here — it is seeded from env only."""
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))
    confirm = str(data.get("confirm_password", ""))
    role = str(data.get("role", "Farmer")).strip().title()
    if role not in VALID_ROLES:
        role = "Farmer"

    errors = []
    if len(name) < 2:
        errors.append("Full name is required.")
    if not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if phone and not PHONE_RE.match(phone):
        errors.append("Enter a valid phone number (e.g. +91 9876543210).")
    if not phone:
        errors.append("Phone number is required.")
    if db.get_user_by_email(email):
        errors.append("An account with this email already exists.")
    elif phone and db.get_user_by_phone(phone):
        errors.append("An account with this phone number already exists.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if password != confirm:
        errors.append("Passwords do not match.")
    if errors:
        return {"error": " ".join(errors)}, 400
    if rate_limit(f"register:{_client_ip()}", 5, 3600):
        return {"error": "Too many registrations from this network. "
                                  "Please try again later."}, 429

    uid = db.create_user(name, email, generate_password_hash(password), phone,
                         role=role)
    # Kick off the email-verification flow immediately.
    verify_url = _create_and_send_verification(uid, name, email)

    session.clear()
    session["user_id"] = uid
    resp = {"ok": True, "redirect": url_for("dashboard"), "role": role,
            "message": "Account created. We sent a verification link to "
                       f"{email}. Check your inbox to unlock all features."}
    # Demo email mode: surface the link so the flow is testable without SMTP.
    if verify_url and email_service.simulated:
        resp["demo_mode"] = True
        resp["demo_verify_url"] = verify_url
    return resp, 200


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    result, status = _authenticate(
        data.get("email") or data.get("identifier"), data.get("password", ""))
    return jsonify(result), status


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or request.form
    result, status = _register_user(data)
    return jsonify(result), status


# ---------------------------------------------------------------------- #
#  Email verification
# ---------------------------------------------------------------------- #
def _create_and_send_verification(user_id, name, email):
    """Create a single-use verification token and email it. Returns the
    verification URL (also used by demo mode to surface the link)."""
    raw = secrets.token_urlsafe(32)
    db.create_email_verification(
        user_id, _hash_token(raw),
        datetime.now() + timedelta(hours=Config.VERIFY_TOKEN_TTL_HOURS))
    verify_url = (f"{_base_url()}{url_for('verify_email_page')}?token={raw}")
    email_service.send_verification_email(email, verify_url, name)
    return verify_url


def _base_url():
    """External base URL: APP_BASE_URL env wins; otherwise derive from the
    request, honoring X-Forwarded-Proto behind proxies (Render)."""
    if Config.APP_BASE_URL:
        return Config.APP_BASE_URL
    root = request.url_root.rstrip("/")
    if request.headers.get("X-Forwarded-Proto", request.scheme) == "https" \
            and root.startswith("http://"):
        root = "https://" + root[len("http://"):]
    return root


@app.route("/api/verify-email", methods=["POST"])
def api_verify_email():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", ""))
    if not token:
        return jsonify({"error": "Verification link is invalid or incomplete."}), 400
    uid = db.consume_email_verification(_hash_token(token))
    if not uid:
        return jsonify({"error": "This verification link is invalid, expired or "
                                 "has already been used."}), 400
    return jsonify({"ok": True, "message": "Email verified successfully. "
                                           "All features are now unlocked."})


@app.route("/api/resend-verification", methods=["POST"])
@api_login_required
def api_resend_verification():
    if rate_limit(f"resend:{session['user_id']}", 3, 3600):
        return jsonify({"error": "Verification email already sent. "
                                  "Please wait before requesting another."}), 429
    user = db.get_user(session["user_id"])
    profile = db.get_profile(session["user_id"]) or {}
    if profile.get("email_verified"):
        return jsonify({"error": "Your email is already verified."}), 400
    verify_url = _create_and_send_verification(
        session["user_id"], user.get("name", ""), user.get("email", ""))
    resp = {"ok": True, "message": "Verification email sent. Check your inbox."}
    if email_service.simulated:
        resp["demo_mode"] = True
        resp["demo_verify_url"] = verify_url
    return jsonify(resp)


# ---------------------------------------------------------------------- #
#  Phone OTP verification
# ---------------------------------------------------------------------- #
@app.route("/api/phone/send-otp", methods=["POST"])
@api_login_required
def api_send_otp():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    if not PHONE_RE.match(phone):
        return jsonify({"error": "Enter a valid phone number (e.g. +90 5xx xxx xx xx)."}), 400
    if rate_limit(f"otp-send:{session['user_id']}", 3, 600):
        return jsonify({"error": "Too many OTP requests. Please wait 10 minutes "
                                  "before requesting another code."}), 429

    code = f"{secrets.randbelow(1000000):06d}"
    db.create_phone_otp(
        session["user_id"], phone, _hash_token(code),
        datetime.now() + timedelta(minutes=Config.OTP_TTL_MINUTES))
    sent = sms_service.send_sms(
        phone, f"AgriCare: your verification code is {code}. "
               f"It expires in {Config.OTP_TTL_MINUTES} minutes.")
    if not sent:
        return jsonify({"error": "Could not send the verification SMS. "
                                  "Please try again in a moment."}), 502
    resp = {"ok": True,
            "message": f"Verification code sent to {phone}. "
                       f"It expires in {Config.OTP_TTL_MINUTES} minutes."}
    # Demo SMS mode: surface the code so the flow is testable without a provider.
    if sms_service.simulated:
        resp["demo_mode"] = True
        resp["demo_otp"] = code
    return jsonify(resp)


@app.route("/api/phone/verify-otp", methods=["POST"])
@api_login_required
def api_verify_otp():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()
    code = str(data.get("code", "")).strip()
    if not PHONE_RE.match(phone) or not code.isdigit() or len(code) != 6:
        return jsonify({"error": "Enter the 6-digit code sent to your phone."}), 400
    if rate_limit(f"otp-verify:{session['user_id']}", 10, 600):
        return jsonify({"error": "Too many verification attempts. Please wait "
                                  "before trying again."}), 429

    otp = db.latest_phone_otp(session["user_id"], phone)
    if not otp:
        return jsonify({"error": "No verification code was sent to this number. "
                                 "Request a new code."}), 400
    otp_id = otp.get("otp_id") or otp.get("id")
    ok, reason = db.consume_phone_otp(otp_id, _hash_token(code),
                                      Config.OTP_MAX_ATTEMPTS)
    if ok:
        return jsonify({"ok": True, "message": "Phone number verified."})
    if reason == "expired":
        return jsonify({"error": "This code has expired. Request a new one."}), 400
    if reason == "attempts":
        return jsonify({"error": "Too many incorrect attempts. Request a new code."}), 400
    return jsonify({"error": "Incorrect code. Please try again."}), 400


# ---------------------------------------------------------------------- #
#  Password reset (secure single-use token flow)
# ---------------------------------------------------------------------- #
RESET_TOKEN_TTL = timedelta(minutes=30)


def _hash_token(raw):
    """Tokens are stored hashed — a DB leak cannot be used to reset anything."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _request_base_url():
    """Backwards-compatible alias for _base_url()."""
    return _base_url()


@app.route("/api/forgot-password", methods=["POST"])
def api_forgot_password():
    data = request.get_json(silent=True) or request.form
    email = str(data.get("email", "")).strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    generic = {"ok": True,
               "message": "If an account exists for that email, a reset link "
                          "has been sent. Check your inbox (and spam folder)."}
    user = db.get_user_by_email(email)
    if not user:
        # Do not reveal whether the email is registered.
        return jsonify(generic)

    raw = secrets.token_urlsafe(32)
    db.create_password_reset(user["user_id"], _hash_token(raw),
                             datetime.now() + RESET_TOKEN_TTL)
    reset_url = f"{_request_base_url()}{url_for('reset_password_page')}?token={raw}"
    sent = email_service.send_reset_email(email, reset_url, user.get("name", ""))

    # Demo email mode: also surface the link in the UI so the flow is usable
    # without a mail server (never enabled when real SMTP is configured).
    if sent and email_service.simulated:
        return jsonify({**generic,
                        "demo_mode": True,
                        "demo_reset_url": reset_url})
    return jsonify(generic)


@app.route("/api/reset-password", methods=["POST"])
def api_reset_password():
    data = request.get_json(silent=True) or request.form
    token = str(data.get("token", ""))
    password = str(data.get("password", ""))
    confirm = str(data.get("confirm_password", ""))

    if not token:
        return jsonify({"error": "Reset link is invalid or incomplete."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if password != confirm:
        return jsonify({"error": "Passwords do not match."}), 400

    if not db.consume_password_reset(_hash_token(token),
                                     generate_password_hash(password)):
        return jsonify({"error": "This reset link is invalid, expired or has "
                                 "already been used. Please request a new one."}), 400

    session.clear()          # drop any stale session; user logs in afresh
    return jsonify({"ok": True,
                    "redirect": url_for("login"),
                    "message": "Password updated. You can now log in with your "
                               "new password."})


@app.route("/api/logout", methods=["POST"])
@api_login_required
def api_logout():
    session.clear()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------- #
#  Google OAuth ("Continue with Google")
# ---------------------------------------------------------------------- #
_GOOGLE_ERRORS = {
    "state": "Sign-in could not be verified — please try again.",
    "expired": "Sign-in took too long — please try again.",
    "exchange": "Could not complete Google sign-in — please try again.",
    "verify": "Google sign-in failed verification — please try again.",
    "email_unverified": "Your Google email is not verified — use a verified Google account.",
    "domain_not_allowed": "This Google account's domain is not allowed to sign in.",
    "disabled": "Google sign-in is not configured on this server.",
}


def _google_error_url(code):
    from urllib.parse import quote
    return f"/login?google_error={quote(_GOOGLE_ERRORS.get(code, _GOOGLE_ERRORS['exchange']))}"


@app.route("/api/auth/google", methods=["GET"])
def api_auth_google_start():
    """Kick off the OAuth flow — 302 to Google's consent screen."""
    if not google_auth.configured():
        return redirect(_google_error_url("disabled"))
    next_url = request.args.get("next") or url_for("dashboard")
    if not next_url.startswith("/"):
        next_url = url_for("dashboard")
    session["google_oauth_next"] = next_url
    return redirect(google_auth.build_auth_url(_base_url(), session))


@app.route("/auth/google/callback", methods=["GET"])
def google_oauth_callback():
    """Google redirects here with ?code=...&state=...

    Links the Google identity to an existing AgriCare account with the same
    verified email, or creates a new account (role Farmer, no password — the
    farmer can add one later; no Google password is ever seen or stored).
    """
    if not google_auth.configured():
        return redirect(_google_error_url("disabled"))
    if request.args.get("error"):
        return redirect("/login?google_error=Google+sign-in+was+cancelled.")
    code = request.args.get("code")
    if not code:
        return redirect(_google_error_url("exchange"))

    claims, err = google_auth.exchange_code(code, request.args.get("state"),
                                            _base_url(), session)
    if err:
        return redirect(_google_error_url(err))

    user = db.get_user_by_google_sub(claims["sub"])
    if not user:
        existing = db.get_user_by_email(claims["email"])
        if existing:
            # Same verified email — link the Google identity to that account.
            db.link_google_account(existing["user_id"], claims["sub"])
            user = existing
        else:
            try:
                uid = db.create_user(claims["name"], claims["email"],
                                     password_hash=None, phone="", role="Farmer",
                                     auth_provider="google", google_sub=claims["sub"])
                db.update_profile(uid, {"email_verified": True})
                user = db.get_user(uid)
            except ValueError:
                return redirect(_google_error_url("exchange"))

    session.clear()                      # prevent session fixation
    session["user_id"] = user["user_id"]
    session.permanent = True
    next_url = session.pop("google_oauth_next", None) or url_for("dashboard")
    if not next_url.startswith("/"):
        next_url = url_for("dashboard")
    return redirect(next_url)


@app.route("/logout", methods=["GET", "POST"])
def logout_page():
    """Logout endpoint usable without JavaScript. GET performs the logout
    directly (a CSRF-safe state change is not required for logging out, and
    session cookies expire immediately)."""
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------- #
#  Dashboard API
# ---------------------------------------------------------------------- #
@app.route("/api/dashboard")
@api_login_required
def api_dashboard():
    return jsonify(db.dashboard(session["user_id"]))


# ---------------------------------------------------------------------- #
#  Equipment API
# ---------------------------------------------------------------------- #
@app.route("/api/equipment", methods=["GET"])
@api_login_required
def api_equipment_list():
    return jsonify({"equipment": db.list_equipment(session["user_id"])})


@app.route("/api/equipment", methods=["POST"])
@api_login_required
def api_equipment_create():
    clean, err = validate_equipment_form(request.get_json(silent=True) or {})
    if err:
        return jsonify({"error": err}), 400
    eid = db.create_equipment(session["user_id"], clean)
    return jsonify({"ok": True, "equipment_id": eid}), 201


@app.route("/api/equipment/<int:equipment_id>", methods=["GET"])
@api_login_required
def api_equipment_detail(equipment_id):
    equip = db.get_equipment(session["user_id"], equipment_id)
    if not equip:
        return jsonify({"error": "Equipment not found."}), 404
    equip["maintenance"] = db.list_maintenance(session["user_id"], equipment_id)
    equip["predictions"] = db.list_predictions(session["user_id"], equipment_id)
    equip["operational"] = db.list_operational(session["user_id"], equipment_id, limit=10)
    return jsonify({"equipment": equip})


@app.route("/api/equipment/<int:equipment_id>", methods=["PUT"])
@api_login_required
def api_equipment_update(equipment_id):
    if not db.get_equipment(session["user_id"], equipment_id):
        return jsonify({"error": "Equipment not found."}), 404
    clean, err = validate_equipment_form(request.get_json(silent=True) or {}, partial=True)
    if err:
        return jsonify({"error": err}), 400
    for key, val in list(clean.items()):
        if val is None or val == "":
            clean.pop(key)
    db.update_equipment(session["user_id"], equipment_id, clean)
    return jsonify({"ok": True})


@app.route("/api/equipment/<int:equipment_id>", methods=["DELETE"])
@api_login_required
def api_equipment_delete(equipment_id):
    if not db.get_equipment(session["user_id"], equipment_id):
        return jsonify({"error": "Equipment not found."}), 404
    db.delete_equipment(session["user_id"], equipment_id)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------- #
#  Maintenance API
# ---------------------------------------------------------------------- #
SERVICE_TYPES = ("Regular Service", "Oil Change", "Engine Repair", "Brake Service",
                 "Transmission Service", "Cooling System", "Electrical Repair",
                 "Hydraulic Repair", "Other")


def clean_maintenance(data, partial=False):
    errors = []
    try:
        equipment_id = int(data.get("equipment_id"))
    except (TypeError, ValueError):
        errors.append("Select an equipment.")
        equipment_id = None
    service_date = str(data.get("service_date", "")).strip()
    service_type = str(data.get("service_type", "")).strip()
    if not partial and not service_date:
        errors.append("Service date is required.")
    if service_type not in SERVICE_TYPES and service_type:
        errors.append("Unknown service type.")
    try:
        cost = float(data.get("cost") or 0)
        if cost < 0:
            raise ValueError
    except ValueError:
        errors.append("Cost must be a non-negative number.")
    clean = {
        "equipment_id": equipment_id,
        "service_date": service_date or None,
        "service_type": service_type or (None if partial else ""),
        "problem_description": str(data.get("problem_description", "")).strip(),
        "action_taken": str(data.get("action_taken", "")).strip(),
        "parts_replaced": str(data.get("parts_replaced", "")).strip(),
        "cost": cost,
        "next_service_date": str(data.get("next_service_date", "")).strip() or None,
        "status": str(data.get("status", "Completed")).strip() or "Completed",
    }
    return clean, " ".join(errors)


def own_equipment(equipment_id):
    return equipment_id and db.get_equipment(session["user_id"], equipment_id)


@app.route("/api/maintenance", methods=["GET"])
@api_login_required
def api_maintenance_list():
    eid = request.args.get("equipment_id", type=int)
    return jsonify({"maintenance": db.list_maintenance(session["user_id"], eid)})


@app.route("/api/maintenance", methods=["POST"])
@api_login_required
def api_maintenance_create():
    data = request.get_json(silent=True) or {}
    clean, err = clean_maintenance(data)
    if err:
        return jsonify({"error": err}), 400
    if not own_equipment(clean["equipment_id"]):
        return jsonify({"error": "Select a valid equipment."}), 400
    mid = db.create_maintenance(session["user_id"], clean)
    equip = db.get_equipment(session["user_id"], clean["equipment_id"])
    db.create_notification(session["user_id"],
                           f"Maintenance recorded for {equip['equipment_name']}",
                           f"{clean['service_type']} recorded on {clean['service_date']}.",
                           "maintenance")
    # A scheduled service with a due date feeds the maintenance-due alert.
    if clean.get("status") in ("Scheduled", "In Progress"):
        try:
            notification_service.notify_maintenance_scheduled(
                session["user_id"], equip, clean)
        except Exception as exc:        # noqa: BLE001 — alerts must never break saves
            print(f"[notifications] maintenance alert failed: {exc}")
    return jsonify({"ok": True, "maintenance_id": mid}), 201


@app.route("/api/maintenance/<int:maintenance_id>", methods=["PUT"])
@api_login_required
def api_maintenance_update(maintenance_id):
    clean, err = clean_maintenance(request.get_json(silent=True) or {}, partial=True)
    if err:
        return jsonify({"error": err}), 400
    for key, val in list(clean.items()):
        if val is None or val == "":
            clean.pop(key)
    db.update_maintenance(session["user_id"], maintenance_id, clean)
    return jsonify({"ok": True})


@app.route("/api/maintenance/<int:maintenance_id>", methods=["DELETE"])
@api_login_required
def api_maintenance_delete(maintenance_id):
    db.delete_maintenance(session["user_id"], maintenance_id)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------- #
#  Operational data API
# ---------------------------------------------------------------------- #
CSV_FIELD_MAP = {
    "enginespeed": "engine_speed", "rpm": "engine_speed", "speed": "engine_speed",
    "enginetorque": "engine_torque", "torque": "engine_torque",
    "engineload": "engine_load", "load": "engine_load",
    "coolanttemperature": "coolant_temperature", "coolant": "coolant_temperature",
    "oiltemperature": "oil_temperature", "oil temp": "oil_temperature",
    "oilpressure": "oil_pressure", "oilpressurebar": "oil_pressure",
    "fuelrate": "fuel_rate", "fuel": "fuel_rate",
    "vehiclespeed": "vehicle_speed",
    "batteryvoltage": "battery_voltage", "voltage": "battery_voltage",
    "transmission": "transmission", "gear": "transmission",
    "operatinghours": "operating_hours", "hours": "operating_hours",
    "timestamp": "timestamp", "date": "timestamp", "time": "timestamp",
    "datetime": "timestamp", "recordedat": "timestamp",
}
NUMERIC_FIELDS = {f for f in ml_service.FEATURES} | {"operating_hours"}


def _normalize_header(h):
    return re.sub(r"[^a-z0-9]+", "", (h or "").lower())


def parse_csv_rows(text, equipment_id, source="csv"):
    reader = csv.DictReader(io.StringIO(text))
    mapped = []
    for row in reader:
        out = {}
        for raw, val in row.items():
            key = CSV_FIELD_MAP.get(_normalize_header(raw))
            if key:
                out[key] = val
        if not out:
            continue
        out["recorded_at"] = out.get("timestamp") or datetime.now().isoformat()
        out["source"] = source
        out["equipment_id"] = equipment_id
        mapped.append(out)
    return mapped


@app.route("/api/operational-data", methods=["POST"])
@api_login_required
def api_operational_data():
    data = request.get_json(silent=True) or {}
    try:
        equipment_id = int(data.get("equipment_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Select an equipment."}), 400
    if not own_equipment(equipment_id):
        return jsonify({"error": "Select a valid equipment."}), 400

    rows = [dict(data)]
    for r in rows:
        r.pop("equipment_id", None)
        r["recorded_at"] = r.get("recorded_at") or datetime.now().isoformat()
        r["source"] = "manual"
    # Only keep known fields; drop unknown keys
    known = ml_service.FEATURES + ["recorded_at", "operating_hours", "source"]
    rows = [{k: v for k, v in r.items() if k in known} for r in rows]

    try:
        count = db.insert_operational(session["user_id"], equipment_id, rows)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid numeric value: {exc}"}), 400
    return jsonify({"ok": True, "inserted": count}), 201


@app.route("/api/upload-csv", methods=["POST"])
@api_login_required
def api_upload_csv():
    equipment_id = request.form.get("equipment_id", type=int)
    if not own_equipment(equipment_id):
        return jsonify({"error": "Select a valid equipment."}), 400
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Please upload a .csv file."}), 400
    try:
        text = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "The CSV file must be UTF-8 encoded."}), 400

    rows = parse_csv_rows(text, equipment_id)
    if not rows:
        return jsonify({"error": "No usable columns found. Expected headers such as "
                                 "engine_speed, coolant_temperature, oil_pressure, ..."}), 400
    try:
        count = db.insert_operational(session["user_id"], equipment_id, rows)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid numeric value in CSV: {exc}"}), 400

    dates = [str(r.get("recorded_at", ""))[:10] for r in rows if r.get("recorded_at")]
    summary = {
        "records": count,
        "equipment_id": equipment_id,
        "date_from": min(dates) if dates else None,
        "date_to": max(dates) if dates else None,
        "averages": {},
    }
    for f in ml_service.FEATURES:
        vals = []
        for r in rows:
            try:
                vals.append(float(r.get(f)))
            except (TypeError, ValueError):
                continue
        if vals:
            summary["averages"][f] = round(sum(vals) / len(vals), 2)
    db.create_notification(session["user_id"], "Operational data uploaded",
                           f"{count} records uploaded for equipment #{equipment_id}.",
                           "data")
    return jsonify({"ok": True, "summary": summary}), 201


@app.route("/api/operational-data", methods=["GET"])
@api_login_required
def api_operational_list():
    eid = request.args.get("equipment_id", type=int)
    limit = min(request.args.get("limit", 25, type=int), 200)
    return jsonify({"records": db.list_operational(session["user_id"], eid, limit)})


# ---------------------------------------------------------------------- #
#  Prediction API
# ---------------------------------------------------------------------- #
@app.route("/api/predict", methods=["POST"])
@verification_required
def api_predict():
    data = request.get_json(silent=True) or request.form
    equipment_id = data.get("equipment_id") or data.get("id")
    try:
        equipment_id = int(equipment_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Select an equipment to analyze."}), 400
    if not own_equipment(equipment_id):
        return jsonify({"error": "Select a valid equipment."}), 400

    params = {k: v for k, v in data.items()
              if k in ml_service.FEATURES and str(v).strip() != ""}
    # Capture the pre-prediction status so a flip to High Risk can alert.
    equipment = db.get_equipment(session["user_id"], equipment_id)
    previous_status = equipment.get("status") if equipment else None
    try:
        result = ml_service.analyze(params, save=True, db=db,
                                    user_id=session["user_id"],
                                    equipment_id=equipment_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if result["condition"] == "Anomalous":
        db.create_notification(session["user_id"],
                               f"Prediction generated for equipment #{equipment_id}",
                               f"Condition: {result['condition']} · "
                               f"{result['risk_level']} risk ({result['probability']}%).",
                               "prediction")

    # ---- Alert pipeline: prediction → severity → email/SMS/in-app ------- #
    equipment = db.get_equipment(session["user_id"], equipment_id)
    alert_delivery = None
    try:
        alert_delivery = notification_service.notify_prediction(
            session["user_id"], equipment, result)
        notification_service.notify_recommendation(session["user_id"], equipment, result)
    except Exception as exc:            # noqa: BLE001 — alerts must never break predictions
        print(f"[notifications] prediction alert failed: {exc}")

    # Status flip to High Risk (demo store mutates on insert_prediction).
    if equipment and equipment.get("status") == "High Risk" \
            and previous_status != "High Risk":
        try:
            notification_service.notify_status_critical(
                session["user_id"], equipment, previous_status)
        except Exception as exc:        # noqa: BLE001
            print(f"[notifications] status alert failed: {exc}")

    if alert_delivery:
        result["alert"] = {k: alert_delivery[k] for k in
                           ("duplicate", "email_status", "sms_status")}
    return jsonify(result)


@app.route("/api/predictions", methods=["GET"])
@api_login_required
def api_predictions():
    eid = request.args.get("equipment_id", type=int)
    return jsonify({"predictions": db.list_predictions(session["user_id"], eid)})


@app.route("/api/model-status")
@api_login_required
def api_model_status():
    return jsonify(ml_service.model_status())


# ---------------------------------------------------------------------- #
#  Chatbot API
# ---------------------------------------------------------------------- #
@app.route("/api/chat", methods=["POST"])
@api_login_required
def api_chat():
    """Conversational chat endpoint.

    Accepts {message, conversation_id?, equipment_id?, language?}. Persists
    BOTH turns to MySQL (chat_messages) and passes the last turns of THIS
    conversation to the assistant so follow-ups like "only when I use the
    rotavator" resolve without repeating anything.
    """
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    equipment_id = data.get("equipment_id")
    try:
        equipment_id = int(equipment_id) if equipment_id else None
    except (TypeError, ValueError):
        equipment_id = None
    if not message:
        return jsonify({"error": "Please type a message."}), 400
    if len(message) > 4000:
        return jsonify({"error": "Message is too long."}), 400
    if equipment_id and not own_equipment(equipment_id):
        return jsonify({"error": "Select a valid equipment."}), 400

    user_id = session["user_id"]

    # Resolve or create the conversation (ownership-checked).
    conversation_id = data.get("conversation_id")
    try:
        conversation_id = int(conversation_id) if conversation_id else None
    except (TypeError, ValueError):
        conversation_id = None
    if conversation_id:
        conv = db.get_conversation(user_id, conversation_id)
        if not conv:
            return jsonify({"error": "Conversation not found."}), 404
        if equipment_id:
            db.rename_conversation_equip(user_id, conversation_id, equipment_id)
    else:
        conversation_id = db.create_conversation(
            user_id, title=message[:80], equipment_id=equipment_id)

    history = [{"role": m["role"], "content": m["content"]}
               for m in db.list_messages(conversation_id)[-20:]]

    db.add_message(conversation_id, user_id, "user", message,
                   equipment_id=equipment_id)

    result = chatbot_service.answer(message, equipment_id=equipment_id,
                                    user_id=user_id, db=db, history=history,
                                    language=str(data.get("language") or "en").lower()[:2])
    db.add_message(conversation_id, user_id, "assistant", result["answer"],
                   equipment_id=equipment_id)
    db.add_chat(user_id, message, result["answer"], equipment_id)  # legacy log
    result["conversation_id"] = conversation_id
    return jsonify(result)


@app.route("/api/chat/conversations", methods=["GET"])
@api_login_required
def api_conversations():
    query = (request.args.get("q") or "").strip()[:80]
    return jsonify({"conversations":
                    db.list_conversations(session["user_id"], query=query or None)})


@app.route("/api/chat/conversations/<int:conversation_id>/messages",
           methods=["GET"])
@api_login_required
def api_conversation_messages(conversation_id):
    conv = db.get_conversation(session["user_id"], conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found."}), 404
    return jsonify({"messages": db.list_messages(conversation_id)})


@app.route("/api/chat/conversations/<int:conversation_id>", methods=["DELETE"])
@api_login_required
def api_conversation_delete(conversation_id):
    conv = db.get_conversation(session["user_id"], conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found."}), 404
    db.delete_conversation(session["user_id"], conversation_id)
    return jsonify({"ok": True})


@app.route("/api/chat/history", methods=["GET"])
@api_login_required
def api_chat_history():
    return jsonify({"history": db.list_chat(session["user_id"])})


@app.route("/api/chat/clear", methods=["POST"])
@api_login_required
def api_chat_clear():
    db.clear_chat(session["user_id"])
    return jsonify({"ok": True})


# ---------------------------------------------------------------------- #
#  Reports API
# ---------------------------------------------------------------------- #
@app.route("/api/reports", methods=["GET"])
@api_login_required
def api_reports():
    report_type = request.args.get("type", "equipment")
    if report_type not in ("equipment", "maintenance", "prediction", "risk"):
        return jsonify({"error": "Unknown report type."}), 400
    rows = db.reports(
        session["user_id"],
        report_type=report_type,
        equipment_id=request.args.get("equipment_id", type=int),
        date_from=request.args.get("from"),
        date_to=request.args.get("to"),
        risk=request.args.get("risk"),
    )
    return jsonify({"type": report_type, "rows": rows})


# ---------------------------------------------------------------------- #
#  Notifications API
# ---------------------------------------------------------------------- #
@app.route("/api/notifications", methods=["GET"])
@api_login_required
def api_notifications():
    return jsonify({"notifications": db.list_notifications(session["user_id"])})


@app.route("/api/notifications/read", methods=["POST"])
@api_login_required
def api_notifications_read():
    db.mark_notifications_read(session["user_id"])
    return jsonify({"ok": True})


@app.route("/api/notifications/poll", methods=["GET"])
@api_login_required
def api_notifications_poll():
    """Lightweight polling endpoint for real-time dashboard updates: unread
    count + the newest notifications since ``since_id``."""
    since_id = request.args.get("since_id", 0, type=int)
    notifications = db.list_notifications(session["user_id"])
    fresh = [n for n in notifications if n["notification_id"] > since_id]
    unread = sum(1 for n in notifications if not n["is_read"])
    return jsonify({"unread": unread,
                    "latest_id": max((n["notification_id"] for n in notifications),
                                     default=0),
                    "new": fresh[:10]})


# ---------------------------------------------------------------------- #
#  Notification preferences + alert history
# ---------------------------------------------------------------------- #
@app.route("/api/notification-preferences", methods=["GET", "PUT"])
@api_login_required
def api_notification_prefs():
    if request.method == "GET":
        return jsonify({"preferences": db.get_notification_prefs(session["user_id"])})
    data = request.get_json(silent=True) or {}
    db.update_notification_prefs(session["user_id"], data)
    return jsonify({"ok": True,
                    "preferences": db.get_notification_prefs(session["user_id"])})


@app.route("/api/alerts", methods=["GET"])
@api_login_required
def api_alerts():
    return jsonify({"alerts": db.list_alerts(session["user_id"])})


@app.route("/api/alerts/test", methods=["POST"])
@api_login_required
def api_alert_test():
    """Safe development/test trigger: exercises the full pipeline (in-app +
    email + SMS per prefs/thresholds) with a clearly-labeled test event."""
    if rate_limit(f"test-alert:{session['user_id']}", 3, 300):
        return jsonify({"error": "Please wait a few minutes between test alerts."}), 429
    result = notification_service.send_test_alert(session["user_id"])
    return jsonify({"ok": True, "delivery": result,
                    "email_simulated": email_service.simulated,
                    "sms_simulated": sms_service.simulated})


# ---------------------------------------------------------------------- #
#  Admin API (admin users only)
# ---------------------------------------------------------------------- #
@app.route("/api/admin/overview", methods=["GET"])
@admin_required
def api_admin_overview():
    users = db.admin_list_users()
    alerts = db.list_alerts(None)
    return jsonify({
        "users": users,
        "stats": {
            "total_users": len(users),
            "email_verified": sum(1 for u in users if u.get("email_verified")),
            "phone_verified": sum(1 for u in users if u.get("phone_verified")),
            "alerts_total": len(alerts),
            "email_failed": sum(1 for a in alerts if a.get("email_status") == "failed"),
            "sms_failed": sum(1 for a in alerts if a.get("sms_status") == "failed"),
        },
        "alerts": alerts[:50],
    })


# ---------------------------------------------------------------------- #
#  Profile API
# ---------------------------------------------------------------------- #
@app.route("/api/profile", methods=["GET"])
@api_login_required
def api_profile():
    profile = db.get_profile(session["user_id"]) or {}
    return jsonify({
        "name": profile.get("name"), "email": profile.get("email"),
        "phone": profile.get("phone", ""),
        "farm_name": profile.get("farm_name", ""),
        "location": profile.get("location", ""),
        "email_verified": profile.get("email_verified", False),
        "phone_verified": profile.get("phone_verified", False),
        "preferences": get_prefs(),
        "notification_preferences": db.get_notification_prefs(session["user_id"]),
        "demo_mode": db.mode == "demo",
    })


@app.route("/api/profile", methods=["PUT"])
@api_login_required
def api_profile_update():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    farm_name = str(data.get("farm_name", "")).strip()
    location = str(data.get("location", "")).strip()
    if len(name) < 2:
        return jsonify({"error": "Full name is required."}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if phone and not PHONE_RE.match(phone):
        return jsonify({"error": "Enter a valid phone number (e.g. +90 5xx xxx xx xx)."}), 400
    other = db.get_user_by_email(email)
    if other and other["user_id"] != session["user_id"]:
        return jsonify({"error": "This email is already in use."}), 400

    profile_before = db.get_profile(session["user_id"]) or {}
    phone_changed = phone != (profile_before.get("phone") or "")
    db.update_user(session["user_id"], name, email, phone)
    db.update_profile(session["user_id"], {"farm_name": farm_name,
                                           "location": location, "phone": phone})
    resp = {"ok": True}
    if phone_changed and phone:
        resp["phone_changed"] = True
        resp["message"] = "Profile updated. Your phone number must be re-verified by OTP."
    return jsonify(resp)


@app.route("/api/change-password", methods=["POST"])
@api_login_required
def api_change_password():
    data = request.get_json(silent=True) or {}
    user = current_user()
    old = str(data.get("current_password", ""))
    new = str(data.get("new_password", ""))
    confirm = str(data.get("confirm_password", ""))
    if not check_password_hash(user["password_hash"], old):
        return jsonify({"error": "Current password is incorrect."}), 400
    if len(new) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    if new != confirm:
        return jsonify({"error": "New passwords do not match."}), 400
    db.change_password(session["user_id"], generate_password_hash(new))
    return jsonify({"ok": True})


@app.route("/api/preferences", methods=["PUT"])
@api_login_required
def api_preferences():
    data = request.get_json(silent=True) or {}
    allowed = ("notifications", "email_alerts", "risk_alerts", "theme", "language")
    prefs = {k: v for k, v in data.items() if k in allowed}
    merged = {**get_prefs(), **prefs}
    set_prefs(merged)
    return jsonify({"ok": True, "preferences": merged})


# ---------------------------------------------------------------------- #
#  Error handlers
# ---------------------------------------------------------------------- #
@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found."}), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(err):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error."}), 500
    return render_template("500.html"), 500


# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)