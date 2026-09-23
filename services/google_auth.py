"""Google OAuth 2.0 sign-in for AgriCare.

Implements the authorization-code flow with plain stdlib (urllib) — no new
dependencies, matching the project's style. No Google password is ever
seen or stored: the farmer consents on Google's own page and AgriCare
receives only a verified identity (email, name, sub).

Flow:
  1. GET /api/auth/google        -> 302 to Google's consent screen
                                    (state stored in the Flask session)
  2. Google redirects to
     GET /auth/google/callback?code=...&state=...
  3. The callback verifies state, exchanges the code for tokens at
     https://oauth2.googleapis.com/token and verifies the returned id_token
     against https://oauth2.googleapis.com/tokeninfo (signature, audience,
     issuer, expiry).
  4. The verified claims are returned to app.py which links or creates the
     AgriCare account and logs the farmer in.

Secrets (client id/secret) come from Config (environment variables) and are
only ever sent to Google's token endpoint over HTTPS from the server.
"""
import json
import secrets
import time
import urllib.parse
import urllib.request
import urllib.error

from config import Config

_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"
# Offline access is NOT requested — AgriCare needs identity only, and there
# is no reason to hold a refresh token for the farmer's Google account.
_SCOPES = "openid email profile"


def configured():
    return bool(Config.GOOGLE_CLIENT_ID and Config.GOOGLE_CLIENT_SECRET)


def redirect_uri(base_url):
    """Callback URL — env override wins, else <base>/auth/google/callback."""
    if Config.GOOGLE_REDIRECT_URI:
        return Config.GOOGLE_REDIRECT_URI
    return base_url.rstrip("/") + "/auth/google/callback"


def _domain_allowed(email):
    """Domain allow-list from Config.GOOGLE_ALLOWED_DOMAINS (csv, '' = all)."""
    allowed = [d.strip().lower() for d in (Config.GOOGLE_ALLOWED_DOMAINS or "").split(",")
               if d.strip()]
    if not allowed:
        return True
    domain = (email or "").rsplit("@", 1)[-1].lower()
    return domain in allowed


def build_auth_url(base_url, session):
    """Create the Google consent URL and stash CSRF state in the session."""
    state = secrets.token_urlsafe(24)
    session["google_oauth_state"] = state
    session["google_oauth_at"] = int(time.time())
    params = {
        "client_id": Config.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(base_url),
        "response_type": "code",
        "scope": _SCOPES,
        "state": state,
        # Always show the account chooser — prevents silent wrong-account logins.
        "prompt": "select_account",
        "access_type": "online",
        "include_granted_scopes": "true",
    }
    return _AUTH_ENDPOINT + "?" + urllib.parse.urlencode(params)


def exchange_code(code, state_from_request, base_url, session):
    """Exchange the auth code and verify the identity.

    ``state_from_request`` is the ?state= query parameter Google appended to
    the callback URL — it must match the one stashed in the Flask session
    when the flow started (CSRF protection).

    Returns (claims, error). claims has: sub, email, name, picture. On any
    failure claims is None and error is a short, user-safe string (details
    land in the server log only).
    """
    expected = session.pop("google_oauth_state", None)
    started = session.pop("google_oauth_at", 0)
    if not expected:
        return None, "expired"
    if not secrets.compare_digest(str(state_from_request or ""), str(expected)):
        return None, "state"
    if int(time.time()) - int(started or 0) > 900:
        return None, "expired"

    # 2) Token exchange (server-to-server, HTTPS).
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": Config.GOOGLE_CLIENT_ID,
        "client_secret": Config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri(base_url),
        "grant_type": "authorization_code",
    }).encode("utf-8")
    req = urllib.request.Request(_TOKEN_ENDPOINT, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            tokens = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"[google-oauth] token exchange failed: HTTP {exc.code}")
        return None, "exchange"
    except Exception as exc:                              # noqa: BLE001
        print(f"[google-oauth] token exchange error: {exc}")
        return None, "exchange"

    id_token = tokens.get("id_token")
    if not id_token:
        return None, "exchange"

    # 3) Verify the id_token (signature via Google's tokeninfo endpoint,
    #    plus audience/issuer/expiry checked locally).
    info_url = _TOKENINFO_ENDPOINT + "?" + urllib.parse.urlencode({"id_token": id_token})
    try:
        with urllib.request.urlopen(info_url, timeout=15) as resp:
            claims = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:                              # noqa: BLE001
        print(f"[google-oauth] id_token verification failed: {exc}")
        return None, "verify"

    aud = claims.get("aud", "")
    if not secrets.compare_digest(str(aud), str(Config.GOOGLE_CLIENT_ID)):
        return None, "verify"
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        return None, "verify"
    if int(claims.get("exp", 0)) < int(time.time()):
        return None, "verify"
    if str(claims.get("email_verified", "false")).lower() != "true":
        return None, "email_unverified"
    if not _domain_allowed(claims.get("email", "")):
        return None, "domain_not_allowed"

    return {
        "sub": claims.get("sub"),
        "email": (claims.get("email") or "").lower(),
        "name": claims.get("name") or (claims.get("email") or "").split("@")[0],
        "picture": claims.get("picture") or "",
    }, None
