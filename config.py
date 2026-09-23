"""Application configuration loaded from environment variables (.env)."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """All secrets and connection settings come from environment variables only."""

    # AUTH_SECRET is the canonical name; SECRET_KEY kept as a fallback alias.
    SECRET_KEY = (os.environ.get("AUTH_SECRET") or os.environ.get("SECRET_KEY")
                  or "dev-only-change-me-in-production")

    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    # External base URL (used for links inside emails). Falls back to the
    # request's own origin, so it only needs setting behind a proxy (Render).
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "").rstrip("/")

    # MySQL (optional) — when missing/unreachable the app runs in Demo Mode
    DATABASE_URL = os.environ.get("DATABASE_URL")
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "farm_equipment")

    # ML model
    MODEL_PATH = os.environ.get("MODEL_PATH", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "model", "predictive_model.pkl"))

    # Email / SMTP (optional) — used for verification, password-reset and
    # alert emails. EMAIL_* names are the canonical ones; SMTP_* kept as
    # fallback aliases. With no host configured, emails are printed to the
    # server log (safe demo mode).
    EMAIL_HOST = os.environ.get("EMAIL_HOST") or os.environ.get("SMTP_HOST", "")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT") or os.environ.get("SMTP_PORT", "587"))
    EMAIL_USER = os.environ.get("EMAIL_USER") or os.environ.get("SMTP_USER", "")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD") or os.environ.get("SMTP_PASSWORD", "")
    EMAIL_FROM = (os.environ.get("EMAIL_FROM") or os.environ.get("SMTP_FROM")
                  or "AgriCare <noreply@agricare.local>")
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
    # Backwards-compatible aliases used by email_service
    SMTP_HOST = EMAIL_HOST
    SMTP_PORT = EMAIL_PORT
    SMTP_USER = EMAIL_USER
    SMTP_PASSWORD = EMAIL_PASSWORD
    SMTP_FROM = EMAIL_FROM
    SMTP_USE_TLS = EMAIL_USE_TLS

    # SMS (optional) — SMS_PROVIDER=twilio uses the Twilio REST API;
    # anything else (or unset) prints to the server log (safe demo mode).
    SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "console")
    SMS_API_KEY = os.environ.get("SMS_API_KEY", "")          # Twilio Account SID
    SMS_API_SECRET = os.environ.get("SMS_API_SECRET", "")    # Twilio Auth Token
    SMS_FROM_NUMBER = os.environ.get("SMS_FROM_NUMBER", "")  # Twilio sender number

    # Alert thresholds (severity: low < medium < high < critical).
    # In-app notifications are always created; email/SMS are sent only when
    # the event severity reaches these minimums AND the user's preferences
    # allow it.
    ALERT_EMAIL_MIN_SEVERITY = os.environ.get("ALERT_EMAIL_MIN_SEVERITY", "medium").lower()
    ALERT_SMS_MIN_SEVERITY = os.environ.get("ALERT_SMS_MIN_SEVERITY", "high").lower()
    # A prediction with risk High and anomaly probability >= this is Critical.
    CRITICAL_PROBABILITY = float(os.environ.get("CRITICAL_PROBABILITY", "97"))

    # Verification / OTP security
    VERIFY_TOKEN_TTL_HOURS = int(os.environ.get("VERIFY_TOKEN_TTL_HOURS", "24"))
    OTP_TTL_MINUTES = int(os.environ.get("OTP_TTL_MINUTES", "10"))
    OTP_MAX_ATTEMPTS = int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))

    # LLM (optional) — used by the chatbot when provided
    LLM_API_KEY = os.environ.get("LLM_API_KEY")
    LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    # Seeded admin account (public registration never grants the Admin
    # role; the first administrator is created from these env vars at
    # startup when the account does not exist yet).
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    ADMIN_NAME = os.environ.get("ADMIN_NAME", "Administrator")

    # Server
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"