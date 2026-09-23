"""Email sending service.

Two interchangeable modes behind one interface:

* ``smtp``   — real delivery via smtplib. Enabled when ``EMAIL_HOST`` is set
               (see ``.env.example``); supports STARTTLS (587) and implicit
               SSL (465).
* ``simulated`` — demo mode (no SMTP configured): the email is printed to the
               server log in a clearly marked banner so links can be copied
               without running a mail server. Send methods still return True,
               and the UI may surface the link as a demo convenience.

Every message gets a plain-text and a styled HTML part. All failure modes are
caught and reported as False — the notification layer records the failure and
the application keeps running.
"""
import smtplib
import ssl
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Config

_BRAND_GREEN = "#166534"
_MUTED = "#6b7280"


def _wrap_html(title, body_html, footer_note=""):
    return f"""\
<html><body style="font-family:Segoe UI,Arial,sans-serif;color:#1f2937;line-height:1.6;margin:0;background:#f3f4f6">
  <div style="max-width:560px;margin:0 auto;padding:24px">
    <div style="background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="background:{_BRAND_GREEN};padding:18px 24px">
        <span style="color:#ffffff;font-size:1.05rem;font-weight:700">🌿 AgriCare</span>
      </div>
      <div style="padding:24px">
        <h2 style="color:{_BRAND_GREEN};margin:0 0 12px">{title}</h2>
        {body_html}
      </div>
      <div style="padding:14px 24px;background:#f9fafb;border-top:1px solid #e5e7eb">
        <p style="font-size:.8rem;color:{_MUTED};margin:0">{footer_note or
          'AI-generated guidance is for assistance. Always follow the equipment manufacturer’s service instructions and consult a qualified technician for serious problems.'}</p>
      </div>
    </div>
  </div>
</body></html>"""


class EmailService:
    def __init__(self):
        self.last_simulated_url = None

    @property
    def simulated(self):
        """True when no SMTP server is configured (demo email mode)."""
        return not Config.SMTP_HOST

    # ------------------------------------------------------------------ #
    #  Low-level sender
    # ------------------------------------------------------------------ #
    def _send(self, to_email, subject, plain, html):
        """Deliver one email. Returns True on success (or simulated success),
        False on SMTP failure."""
        if self.simulated:
            def _safe(s):
                return str(s).encode("utf-8", "replace").decode("utf-8") \
                    if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("utf") \
                    else str(s).encode(sys.stdout.encoding or "ascii", "replace").decode(
                        sys.stdout.encoding or "ascii")
            print("\n" + "=" * 72)
            print("  [DEMO EMAIL] (SMTP not configured)")
            print(f"  To:      {_safe(to_email)}")
            print(f"  Subject: {_safe(subject)}")
            print("  " + "-" * 68)
            for line in plain.splitlines():
                print("  " + _safe(line))
            print("=" * 72 + "\n")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = Config.SMTP_FROM
            msg["To"] = to_email
            msg.attach(MIMEText(plain, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))

            ctx = ssl.create_default_context()
            if Config.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, context=ctx) as server:
                    if Config.SMTP_USER:
                        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                    server.sendmail(Config.SMTP_FROM, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                    if Config.SMTP_USE_TLS:
                        server.starttls(context=ctx)
                    if Config.SMTP_USER:
                        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                    server.sendmail(Config.SMTP_FROM, [to_email], msg.as_string())
            return True
        except Exception as exc:    # noqa: BLE001 — never leak SMTP errors to the client
            print(f"[email] SMTP send failed: {exc}")
            return False

    # ------------------------------------------------------------------ #
    #  Transactional: email verification
    # ------------------------------------------------------------------ #
    def send_verification_email(self, to_email, verify_url, user_name=""):
        name = (user_name or "").strip() or "Farmer"
        subject = "AgriCare — Verify your email address"
        plain = (
            f"Hi {name},\n\n"
            "Welcome to AgriCare! Please confirm your email address to unlock\n"
            "your dashboard:\n\n"
            f"{verify_url}\n\n"
            "The link is valid for 24 hours and can be used only once.\n\n"
            "If you did not create this account, you can safely ignore this email.\n\n"
            "— The AgriCare Team\n")
        html = _wrap_html(
            "Verify your email",
            f"""<p>Hi <b>{name}</b>,</p>
            <p>Welcome to AgriCare! Confirm your email address to unlock your
               equipment dashboard, predictions and alerts.</p>
            <p style="margin:22px 0">
              <a href="{verify_url}"
                 style="background:{_BRAND_GREEN};color:#ffffff;padding:12px 22px;border-radius:10px;
                        text-decoration:none;font-weight:600;display:inline-block">
                Verify my email
              </a>
            </p>
            <p style="font-size:.9rem;color:{_MUTED}">Or paste this link into your browser:<br>
               <a href="{verify_url}">{verify_url}</a></p>
            <p style="font-size:.9rem;color:{_MUTED}">The link is valid for <b>24 hours</b> and
               can be used only once. If you did not create this account, you can safely
               ignore this email.</p>""")
        return self._send(to_email, subject, plain, html)

    # ------------------------------------------------------------------ #
    #  Transactional: password reset
    # ------------------------------------------------------------------ #
    def send_reset_email(self, to_email, reset_url, user_name=""):
        name = (user_name or "").strip() or "Farmer"
        subject = "AgriCare — Reset your password"
        plain = (
            f"Hi {name},\n\n"
            "We received a request to reset your AgriCare password.\n"
            "Open the link below to choose a new password:\n\n"
            f"{reset_url}\n\n"
            "The link is valid for 30 minutes and can be used only once.\n\n"
            "If you did not request this, you can safely ignore this email —\n"
            "your current password keeps working.\n\n"
            "— The AgriCare Team\n")
        html = _wrap_html(
            "Reset your password",
            f"""<p>Hi <b>{name}</b>,</p>
            <p>We received a request to reset your AgriCare password.
               Click the button below to choose a new one.</p>
            <p style="margin:24px 0">
              <a href="{reset_url}"
                 style="background:{_BRAND_GREEN};color:#ffffff;padding:12px 22px;border-radius:10px;
                        text-decoration:none;font-weight:600;display:inline-block">
                Reset password
              </a>
            </p>
            <p style="font-size:.9rem;color:{_MUTED}">Or paste this link into your browser:<br>
               <a href="{reset_url}">{reset_url}</a></p>
            <p style="font-size:.9rem;color:{_MUTED}">The link is valid for <b>30 minutes</b>
               and can be used only once. If you did not request a reset, you can safely
               ignore this email — your current password keeps working.</p>""")
        return self._send(to_email, subject, plain, html)

    # ------------------------------------------------------------------ #
    #  Alerts: equipment maintenance / risk notifications
    # ------------------------------------------------------------------ #
    def send_alert_email(self, to_email, user_name, equipment_name, equipment_label,
                         severity, status, risk_level, predicted_problem,
                         recommended_action, due_date=None, dashboard_url=""):
        """Send an equipment alert email. Returns True on success."""
        name = (user_name or "").strip() or "Farmer"
        emoji = {"low": "ℹ️", "medium": "⚠️", "high": "⚠️", "critical": "🚨"}.get(severity, "⚠️")
        subject = f"{emoji} Equipment Alert ({severity.upper()}) — {equipment_name}"
        rows = [
            ("Farmer", name),
            ("Equipment", f"{equipment_name} ({equipment_label})"),
            ("Current status", status or "—"),
            ("Risk level", risk_level or "—"),
            ("Predicted problem", predicted_problem or "—"),
            ("Recommended action", recommended_action or "—"),
        ]
        if due_date:
            rows.append(("Maintenance due", str(due_date)))
        tr = "".join(
            f'<tr><td style="padding:6px 14px 6px 0;color:{_MUTED};white-space:nowrap;vertical-align:top">{k}</td>'
            f'<td style="padding:6px 0;font-weight:600">{v}</td></tr>'
            for k, v in rows)
        color = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444",
                 "critical": "#b91c1c"}.get(severity, "#f59e0b")
        plain = (
            f"{subject}\n\nHi {name},\n\n"
            f"Equipment:      {equipment_name} ({equipment_label})\n"
            f"Current status: {status or '-'}\n"
            f"Risk level:     {risk_level or '-'}\n"
            f"Problem:        {predicted_problem or '-'}\n"
            f"Action:         {recommended_action or '-'}\n"
            + (f"Due date:       {due_date}\n" if due_date else "")
            + f"\nOpen your dashboard: {dashboard_url}\n\n— The AgriCare Team\n")
        html = _wrap_html(
            f'<span style="color:{color}">{severity.upper()} severity alert</span>',
            f"""<p>Hi <b>{name}</b>,</p>
            <table style="border-collapse:collapse;font-size:.95rem;margin:6px 0 18px">{tr}</table>
            <p style="margin:20px 0">
              <a href="{dashboard_url}"
                 style="background:{_BRAND_GREEN};color:#ffffff;padding:12px 22px;border-radius:10px;
                        text-decoration:none;font-weight:600;display:inline-block">
                Open equipment dashboard
              </a>
            </p>""")
        return self._send(to_email, subject, plain, html)


email_service = EmailService()
