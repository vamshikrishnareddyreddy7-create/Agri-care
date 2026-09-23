"""SMS sending service.

Two interchangeable providers behind one interface:

* ``twilio``  — real delivery via the Twilio REST API using only the standard
                library (urllib + base64). Enabled when SMS_PROVIDER=twilio and
                SMS_API_KEY (Account SID) / SMS_API_SECRET (Auth Token) /
                SMS_FROM_NUMBER are configured.
* ``console`` — demo mode (default): the SMS is printed to the server log in a
                clearly marked banner. send_sms still returns True so the
                notification pipeline can be tested without a provider.

All failures are caught and reported as False — the notification layer records
the failure and the application keeps running.
"""
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from config import Config


class SmsService:
    @property
    def simulated(self):
        """True when no real provider is configured (demo SMS mode)."""
        return Config.SMS_PROVIDER != "twilio"

    def send_sms(self, to_number, text):
        """Send one SMS. Returns True on success (or simulated success in demo
        mode), False when the provider rejects or errors."""
        if not to_number:
            return False
        text = (text or "").strip()
        if len(text) > 320:                 # keep messages short and clear
            text = text[:317] + "..."

        if self.simulated:
            def _safe(s):
                enc = sys.stdout.encoding or "ascii"
                return str(s).encode(enc, "replace").decode(enc)
            print("\n" + "=" * 72)
            print("  [DEMO SMS] (no SMS provider configured)")
            print(f"  To:   {_safe(to_number)}")
            print(f"  Text: {_safe(text)}")
            print("=" * 72 + "\n")
            return True

        # ---- Twilio REST API (no SDK dependency) ------------------------- #
        try:
            url = (f"https://api.twilio.com/2010-04-01/Accounts/"
                   f"{Config.SMS_API_KEY}/Messages.json")
            auth = base64.b64encode(
                f"{Config.SMS_API_KEY}:{Config.SMS_API_SECRET}".encode()).decode()
            payload = urllib.parse.urlencode({
                "To": to_number, "From": Config.SMS_FROM_NUMBER, "Body": text,
            }).encode()
            req = urllib.request.Request(url, data=payload, method="POST", headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("sid") is not None
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:200]
            except Exception:            # noqa: BLE001
                pass
            print(f"[sms] Twilio HTTP {exc.code}: {detail}")
            return False
        except Exception as exc:     # noqa: BLE001 — never leak provider errors
            print(f"[sms] send failed: {exc}")
            return False


sms_service = SmsService()
