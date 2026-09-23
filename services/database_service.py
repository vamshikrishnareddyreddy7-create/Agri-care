"""Database access layer.

Two interchangeable backends behind one interface:

* ``mysql`` — real MySQL via PyMySQL, parameterized queries (SQL-injection
  safe). Enabled when DATABASE_URL or MYSQL_* env vars are configured and the
  database is reachable. Tables are created automatically from schema.sql.
* ``demo``  — in-memory store seeded with realistic sample data, used when no
  MySQL is configured (or unreachable). Clearly flagged as Demo Mode in the UI.
"""
import os
import copy
import re
from datetime import datetime, timedelta
from collections import defaultdict

try:
    import pymysql
    from pymysql.cursors import DictCursor
    HAVE_MYSQL = True
except ImportError:                      # pragma: no cover
    HAVE_MYSQL = False

from config import Config
from services import demo_data

DEMO_MODE_LABEL = "Demo Mode — using bundled sample data. Configure MySQL to use a real database."


class Database:
    """Single interface used by the whole application."""

    def __init__(self):
        self.mode = "demo"
        self._store = None
        self._conn = None
        self._setup()

    # ------------------------------------------------------------------ #
    #  Setup
    # ------------------------------------------------------------------ #
    def _setup(self):
        if HAVE_MYSQL and self._mysql_env_configured():
            try:
                self._conn = self._connect()
                self.mode = "mysql"
                self.init_db()
                self._seed_admin_from_env()
                return
            except Exception as exc:    # noqa: BLE001 - fall back to demo
                print(f"[database] MySQL unavailable ({exc}); falling back to Demo Mode.")
        self.mode = "demo"
        self._store = demo_data.build_demo_state()

    def _seed_admin_from_env(self):
        """Create the admin account from ADMIN_EMAIL/ADMIN_PASSWORD env vars.

        Runs only in MySQL mode, only when both are set and the account does
        not exist yet. Public registration never grants the Admin role, so
        this is the only supported way to create an administrator.
        """
        admin_email = (Config.ADMIN_EMAIL or "").strip().lower()
        admin_password = (Config.ADMIN_PASSWORD or "").strip()
        if not admin_email or not admin_password or "@" not in admin_email:
            return
        existing = self.get_user_by_email(admin_email)
        if existing:
            return
        from werkzeug.security import generate_password_hash
        name = (Config.ADMIN_NAME or "Administrator").strip() or "Administrator"
        try:
            uid = self.create_user(name, admin_email,
                                   generate_password_hash(admin_password))
            self.update_user_role(uid, "Admin")
            self.update_profile(uid, {"email_verified": True, "is_admin": True})
            print(f"[database] Seeded admin account {admin_email} from env.")
        except Exception as exc:        # noqa: BLE001 - never block startup
            print(f"[database] Admin seeding skipped ({exc}).")

    VALID_ROLES = ("Farmer", "Technician", "Admin")

    def update_user_role(self, user_id, role):
        """Set the user's role (Farmer/Technician/Admin). MySQL mode only
        unless the row exists in the demo store."""
        if role not in self.VALID_ROLES:
            raise ValueError("invalid_role")
        if self.mode == "demo":
            u = self.get_user(user_id)
            if not u:
                return False
            u["role"] = role
            return True
        return self._execute("UPDATE users SET role=%s WHERE user_id=%s",
                             (role, user_id))

    @staticmethod
    def _mysql_env_configured():
        if Config.DATABASE_URL:
            return True
        # The user enabled MySQL explicitly (host changed from the localhost default
        # or a password/database was supplied).
        return (
            Config.MYSQL_HOST not in ("", "localhost")
            or bool(Config.MYSQL_PASSWORD)
            or Config.MYSQL_DATABASE not in ("", "farm_equipment")
        )

    @staticmethod
    def _parse_database_url(url):
        """Parse mysql://user:pass@host:port/dbname — handles URL-encoded
        passwords and an optional ?ssl... suffix (Render-style URLs)."""
        from urllib.parse import urlsplit, unquote
        parts = urlsplit(url)
        return {
            "host": parts.hostname,
            "port": parts.port or 3306,
            "user": unquote(parts.username or ""),
            "password": unquote(parts.password or ""),
            "database": (parts.path or "/").lstrip("/").split("?")[0],
        }

    def _connect(self):
        if Config.DATABASE_URL:
            c = self._parse_database_url(Config.DATABASE_URL)
            return pymysql.connect(
                host=c["host"], port=c["port"], user=c["user"],
                password=c["password"], database=c["database"],
                cursorclass=DictCursor, autocommit=True, charset="utf8mb4")
        return pymysql.connect(
            host=Config.MYSQL_HOST, user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD, database=Config.MYSQL_DATABASE,
            cursorclass=DictCursor, autocommit=True, charset="utf8mb4")

    def init_db(self):
        """Create tables from database/schema.sql if they do not exist."""
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "database", "schema.sql")
        with open(path, "r", encoding="utf-8") as fh:
            sql = fh.read()
        # Strip comment lines FIRST (every CREATE TABLE is preceded by '--'
        # comment blocks; without this the split chunks start with '--' and
        # no statement ever executes), then split on statement boundaries
        # (works for this schema, which contains no ';' inside strings).
        sql = "\n".join(ln for ln in sql.splitlines()
                        if not ln.strip().startswith("--"))
        statements = [s.strip() for s in re.split(r";\s*", sql) if s.strip()]
        with self._conn.cursor() as cur:
            for stmt in statements:
                if stmt.upper().startswith(("CREATE", "USE")):
                    cur.execute(stmt)

    def _query(self, sql, args=()):
        """Execute a query with a fresh cursor, reconnecting once on failure."""
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, args)
                return cur.fetchall()
        except pymysql.OperationalError:
            self._conn = self._connect()
            with self._conn.cursor() as cur:
                cur.execute(sql, args)
                return cur.fetchall()

    def _execute(self, sql, args=()):
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, args)
                return cur.lastrowid
        except pymysql.OperationalError:
            self._conn = self._connect()
            with self._conn.cursor() as cur:
                cur.execute(sql, args)
                return cur.lastrowid

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:            # noqa: BLE001
                pass

    # ------------------------------------------------------------------ #
    #  Users
    # ------------------------------------------------------------------ #
    def get_user_by_email(self, email):
        if self.mode == "demo":
            return next((u for u in self._store["users"]
                         if u["email"].lower() == email.lower()), None)
        rows = self._query("SELECT * FROM users WHERE email = %s", (email,))
        return rows[0] if rows else None

    def get_user_by_phone(self, phone):
        """Find a user by their (normalized) phone number — phone login."""
        digits = re.sub(r"[^0-9]", "", str(phone or ""))
        if len(digits) < 7:
            return None
        if self.mode == "demo":
            return next((u for u in self._store["users"]
                         if re.sub(r"[^0-9]", "", u.get("phone") or "") == digits), None)
        rows = self._query("SELECT * FROM users WHERE phone = %s", (str(phone).strip(),))
        if rows:
            return rows[0]
        # Fall back to digit-normalized comparison (formats vary: +90…, 0…)
        for u in self._query("SELECT * FROM users"):
            if re.sub(r"[^0-9]", "", u.get("phone") or "") == digits:
                return u
        return None

    def get_user(self, user_id):
        if self.mode == "demo":
            return next((u for u in self._store["users"] if u["user_id"] == user_id), None)
        rows = self._query("SELECT * FROM users WHERE user_id = %s", (user_id,))
        return rows[0] if rows else None

    def create_user(self, name, email, password_hash, phone="", role="Farmer"):
        if self.mode == "demo":
            if email and self.get_user_by_email(email):
                raise ValueError("email_exists")
            if phone and self.get_user_by_phone(phone):
                raise ValueError("phone_exists")
            uid = self._store["next_ids"]["user"]
            self._store["next_ids"]["user"] += 1
            self._store["users"].append({
                "user_id": uid, "name": name, "email": email,
                "password_hash": password_hash, "phone": phone, "role": role,
                "email_verified": False, "phone_verified": False,
                "created_at": datetime.now(), "updated_at": datetime.now()})
            return uid
        try:
            return self._execute(
                "INSERT INTO users (name, email, password_hash, phone, role) "
                "VALUES (%s,%s,%s,%s,%s)",
                (name, email, password_hash, phone or None, role))
        except Exception as exc:   # uniqueness violations surface as 1062/1069
            msg = str(exc).lower()
            if "phone" in msg and ("1062" in msg or "unique" in msg or "duplicate" in msg):
                raise ValueError("phone_exists")
            if "1062" in msg or "duplicate" in msg or "unique" in msg:
                raise ValueError("email_exists")
            raise

    def update_user(self, user_id, name, email, phone):
        if self.mode == "demo":
            u = self.get_user(user_id)
            if not u:
                return False
            u["name"], u["email"], u["phone"] = name, email, phone
            return True
        return self._execute(
            "UPDATE users SET name=%s, email=%s, phone=%s WHERE user_id=%s",
            (name, email, phone, user_id))

    def change_password(self, user_id, password_hash):
        if self.mode == "demo":
            u = self.get_user(user_id)
            if not u:
                return False
            u["password_hash"] = password_hash
            return True
        return self._execute(
            "UPDATE users SET password_hash=%s WHERE user_id=%s",
            (password_hash, user_id))

    # ------------------------------------------------------------------ #
    #  User profiles (farm details + verification status + admin flag)
    # ------------------------------------------------------------------ #
    def get_profile(self, user_id):
        """Merged users + user_profiles row (dict or None)."""
        if self.mode == "demo":
            u = self.get_user(user_id)
            if not u:
                return None
            p = self._store["profiles"].get(user_id, {})
            return {"user_id": user_id, "name": u["name"], "email": u["email"],
                    "phone": u.get("phone") or "",
                    "farm_name": p.get("farm_name", ""), "location": p.get("location", ""),
                    "email_verified": p.get("email_verified", False),
                    "phone_verified": p.get("phone_verified", False),
                    "is_admin": p.get("is_admin", False)}
        rows = self._query(
            """SELECT u.user_id, u.name, u.email, u.phone, p.farm_name, p.location,
                      (COALESCE(p.email_verified,0) | COALESCE(u.email_verified,0)) AS email_verified,
                      (COALESCE(p.phone_verified,0) | COALESCE(u.phone_verified,0)) AS phone_verified,
                      p.is_admin
               FROM users u LEFT JOIN user_profiles p ON u.user_id = p.user_id
               WHERE u.user_id = %s""", (user_id,))
        row = rows[0] if rows else None
        if row:
            row["email_verified"] = bool(row.get("email_verified"))
            row["phone_verified"] = bool(row.get("phone_verified"))
            row["is_admin"] = bool(row.get("is_admin"))
        return row

    def update_profile(self, user_id, data):
        """Update farm_name/location (and optionally phone) on the profile.
        Also accepts email_verified / phone_verified / is_admin flags."""
        if self.mode == "demo":
            u = self.get_user(user_id)
            if not u:
                return False
            p = self._store["profiles"].setdefault(user_id, {})
            if "farm_name" in data:
                p["farm_name"] = data["farm_name"]
            if "location" in data:
                p["location"] = data["location"]
            if "phone" in data:
                u["phone"] = data["phone"]
                p["phone_verified"] = False   # new number must be re-verified
            if "email_verified" in data:
                p["email_verified"] = bool(data["email_verified"])
            if "phone_verified" in data:
                p["phone_verified"] = bool(data["phone_verified"])
            if "is_admin" in data:
                p["is_admin"] = bool(data["is_admin"])
            return True
        if "phone" in data:
            self._execute("UPDATE users SET phone=%s WHERE user_id=%s",
                          (data["phone"], user_id))
            # A changed phone number must be re-verified via OTP.
        if any(k in data for k in ("phone", "farm_name", "location",
                                   "email_verified", "phone_verified", "is_admin")):
            self._execute(
                """INSERT INTO user_profiles (user_id, farm_name, location,
                                             email_verified, phone_verified, is_admin)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE farm_name=VALUES(farm_name),
                   location=VALUES(location),
                   email_verified=VALUES(email_verified),
                   phone_verified=VALUES(phone_verified),
                   is_admin=VALUES(is_admin)""",
                (user_id, data.get("farm_name"), data.get("location"),
                 1 if data.get("email_verified") else 0,
                 1 if data.get("phone_verified") else 0,
                 1 if data.get("is_admin") else 0))
        return True

    def set_email_verified(self, user_id, verified=True):
        if self.mode == "demo":
            p = self._store["profiles"].setdefault(user_id, {})
            p["email_verified"] = verified
            u = self.get_user(user_id)
            if u:
                u["email_verified"] = verified
            return True
        self._execute("UPDATE users SET email_verified=%s WHERE user_id=%s",
                      (1 if verified else 0, user_id))
        self._execute(
            """INSERT INTO user_profiles (user_id, email_verified)
               VALUES (%s,%s)
               ON DUPLICATE KEY UPDATE email_verified=VALUES(email_verified)""",
            (user_id, 1 if verified else 0))
        return True

    def set_phone_verified(self, user_id, phone, verified=True):
        if self.mode == "demo":
            p = self._store["profiles"].setdefault(user_id, {})
            if verified:
                p["phone_verified"] = True
                u = self.get_user(user_id)
                if u:
                    u["phone_verified"] = True
            return True
        if verified:
            self._execute("UPDATE users SET phone_verified=1 WHERE user_id=%s",
                          (user_id,))
            self._execute(
                """INSERT INTO user_profiles (user_id, phone_verified)
                   VALUES (%s,1)
                   ON DUPLICATE KEY UPDATE phone_verified=1""", (user_id,))
        return True

    def set_admin(self, user_id, is_admin=True):
        if self.mode == "demo":
            p = self._store["profiles"].setdefault(user_id, {})
            p["is_admin"] = is_admin
            return True
        self._execute(
            """INSERT INTO user_profiles (user_id, is_admin)
               VALUES (%s,%s)
               ON DUPLICATE KEY UPDATE is_admin=VALUES(is_admin)""",
            (user_id, 1 if is_admin else 0))
        return True

    # ------------------------------------------------------------------ #
    #  Email verification tokens (hashed at rest)
    # ------------------------------------------------------------------ #
    def create_email_verification(self, user_id, token_hash, expires_at):
        if self.mode == "demo":
            self._store["email_verifications"].append({
                "user_id": user_id, "token_hash": token_hash,
                "expires_at": expires_at, "used_at": None,
                "created_at": datetime.now()})
            return True
        return self._execute(
            "INSERT INTO email_verifications (user_id, token_hash, expires_at) "
            "VALUES (%s,%s,%s)", (user_id, token_hash, expires_at))

    def consume_email_verification(self, token_hash):
        """Mark the token used and verify the user. Returns user_id or None."""
        now = datetime.now()
        if self.mode == "demo":
            row = next((r for r in self._store["email_verifications"]
                        if r["token_hash"] == token_hash), None)
            if not row or row.get("used_at") or row["expires_at"] < now:
                return None
            row["used_at"] = datetime.now()
            uid = row["user_id"]
        else:
            rows = self._query(
                "SELECT * FROM email_verifications WHERE token_hash=%s", (token_hash,))
            row = rows[0] if rows else None
            if not row or row.get("used_at") or row["expires_at"] < now:
                return None
            self._execute(
                "UPDATE email_verifications SET used_at=NOW() WHERE token_hash=%s",
                (token_hash,))
            uid = row["user_id"]
        self.set_email_verified(uid, True)
        return uid

    # ------------------------------------------------------------------ #
    #  Phone OTP store (codes hashed, attempt-limited, expiring)
    # ------------------------------------------------------------------ #
    def create_phone_otp(self, user_id, phone, code_hash, expires_at):
        if self.mode == "demo":
            otp_id = self._store["next_ids"].setdefault("otp", 1)
            self._store["next_ids"]["otp"] = otp_id + 1
            self._store["phone_otps"].append({
                "otp_id": otp_id, "user_id": user_id, "phone": phone,
                "code_hash": code_hash, "expires_at": expires_at,
                "attempts": 0, "verified": False, "created_at": datetime.now()})
            return True
        return self._execute(
            "INSERT INTO phone_verifications (user_id, phone, code_hash, expires_at) "
            "VALUES (%s,%s,%s,%s)", (user_id, phone, code_hash, expires_at))

    def latest_phone_otp(self, user_id, phone):
        if self.mode == "demo":
            rows = [o for o in self._store["phone_otps"]
                    if o["user_id"] == user_id and o["phone"] == phone]
            rows.sort(key=lambda o: o["created_at"])
            return rows[-1] if rows else None
        rows = self._query(
            """SELECT * FROM phone_verifications WHERE user_id=%s AND phone=%s
               ORDER BY otp_id DESC LIMIT 1""", (user_id, phone))
        return rows[0] if rows else None

    def consume_phone_otp(self, otp_id, code_hash, max_attempts):
        """Verify an OTP. Returns (ok, reason) where reason in
        {None, 'expired', 'attempts'}"""
        now = datetime.now()
        if self.mode == "demo":
            otp = next((o for o in self._store["phone_otps"] if o["otp_id"] == otp_id),
                       None)
            if not otp or otp.get("verified"):
                return False, None
            if otp["expires_at"] < now:
                return False, "expired"
            if otp["attempts"] >= max_attempts:
                return False, "attempts"
            if otp["code_hash"] != code_hash:
                otp["attempts"] += 1
                return False, None
            otp["verified"] = True
        else:
            rows = self._query("SELECT * FROM phone_verifications WHERE otp_id=%s",
                               (otp_id,))
            otp = rows[0] if rows else None
            if not otp or otp.get("verified"):
                return False, None
            if otp["expires_at"] < now:
                return False, "expired"
            if otp["attempts"] >= max_attempts:
                return False, "attempts"
            if otp["code_hash"] != code_hash:
                self._execute("UPDATE phone_verifications SET attempts=attempts+1 "
                              "WHERE otp_id=%s", (otp_id,))
                return False, None
            self._execute("UPDATE phone_verifications SET verified=1 WHERE otp_id=%s",
                          (otp_id,))
        self.set_phone_verified(otp["user_id"], otp["phone"], True)
        return True, None

    # ------------------------------------------------------------------ #
    #  Email OTP verification (6-digit codes hashed at rest)
    # ------------------------------------------------------------------ #
    def create_email_otp(self, user_id, email, code_hash, expires_at):
        if self.mode == "demo":
            otp_id = self._store["next_ids"].setdefault("email_otp", 1)
            self._store["next_ids"]["email_otp"] = otp_id + 1
            self._store.setdefault("email_otps", []).append({
                "otp_id": otp_id, "user_id": user_id, "email": email,
                "code_hash": code_hash, "expires_at": expires_at,
                "attempts": 0, "verified": False, "created_at": datetime.now()})
            return True
        return self._execute(
            "INSERT INTO email_otps (user_id, email, code_hash, expires_at) "
            "VALUES (%s,%s,%s,%s)", (user_id, email, code_hash, expires_at))

    def latest_email_otp(self, user_id, email):
        if self.mode == "demo":
            rows = [o for o in self._store.get("email_otps", [])
                    if o["user_id"] == user_id and o["email"] == (email or "").lower()]
            rows.sort(key=lambda o: o["created_at"])
            return rows[-1] if rows else None
        rows = self._query(
            """SELECT * FROM email_otps WHERE user_id=%s AND email=%s
               ORDER BY otp_id DESC LIMIT 1""", (user_id, (email or "").lower()))
        return rows[0] if rows else None

    def consume_email_otp(self, otp_id, code_hash, max_attempts):
        """Verify an email OTP. Returns (ok, reason) with reason in
        {None, 'expired', 'attempts'} — mirrors consume_phone_otp."""
        now = datetime.now()
        if self.mode == "demo":
            otp = next((o for o in self._store.get("email_otps", [])
                        if o["otp_id"] == otp_id), None)
            if not otp or otp.get("verified"):
                return False, None
            if otp["expires_at"] < now:
                return False, "expired"
            if otp["attempts"] >= max_attempts:
                return False, "attempts"
            if otp["code_hash"] != code_hash:
                otp["attempts"] += 1
                return False, None
            otp["verified"] = True
        else:
            rows = self._query("SELECT * FROM email_otps WHERE otp_id=%s", (otp_id,))
            otp = rows[0] if rows else None
            if not otp or otp.get("verified"):
                return False, None
            if otp["expires_at"] < now:
                return False, "expired"
            if otp["attempts"] >= max_attempts:
                return False, "attempts"
            if otp["code_hash"] != code_hash:
                self._execute("UPDATE email_otps SET attempts=attempts+1 "
                              "WHERE otp_id=%s", (otp_id,))
                return False, None
            self._execute("UPDATE email_otps SET verified=1 WHERE otp_id=%s",
                          (otp_id,))
        self.set_email_verified(otp["user_id"], True)
        return True, None

    # ------------------------------------------------------------------ #
    #  Password-reset tokens (hashed at rest; raw token only in the email)
    # ------------------------------------------------------------------ #
    def create_password_reset(self, user_id, token_hash, expires_at):
        if self.mode == "demo":
            self._store["password_resets"].append({
                "user_id": user_id, "token_hash": token_hash,
                "expires_at": expires_at, "used_at": None,
                "created_at": datetime.now()})
            return True
        return self._execute(
            "INSERT INTO password_reset (user_id, token_hash, expires_at) "
            "VALUES (%s,%s,%s)", (user_id, token_hash, expires_at))

    def find_password_reset(self, token_hash):
        """Return the reset row for a token hash if it is unused and
        unexpired, else None."""
        now = datetime.now()
        if self.mode == "demo":
            row = next((r for r in self._store["password_resets"]
                        if r["token_hash"] == token_hash), None)
        else:
            rows = self._query(
                "SELECT * FROM password_reset WHERE token_hash = %s", (token_hash,))
            row = rows[0] if rows else None
        if not row or row.get("used_at") or row["expires_at"] < now:
            return None
        return row

    def consume_password_reset(self, token_hash, password_hash):
        """Mark the token used and set the user's new password (atomic-ish:
        the token is invalidated even if the password write fails, so it can
        never be replayed)."""
        row = self.find_password_reset(token_hash)
        if not row:
            return False
        if self.mode == "demo":
            row["used_at"] = datetime.now()
        else:
            self._execute(
                "UPDATE password_reset SET used_at = NOW() WHERE token_hash = %s",
                (token_hash,))
        return self.change_password(row["user_id"], password_hash)

    # ------------------------------------------------------------------ #
    #  Equipment
    # ------------------------------------------------------------------ #
    @staticmethod
    def _risk_for(equip, latest_pred):
        """Derive a maintenance-risk label for an equipment row."""
        if latest_pred:
            return latest_pred["risk_level"]
        status = (equip.get("status") or "Healthy")
        return {"High Risk": "High", "Maintenance Due": "Medium",
                "Warning": "Medium", "Healthy": "Low"}.get(status, "Low")

    def list_equipment(self, user_id):
        if self.mode == "demo":
            rows = [dict(e) for e in self._store["equipment"]
                    if e["user_id"] == user_id]
        else:
            rows = self._query(
                "SELECT * FROM equipment WHERE user_id = %s ORDER BY equipment_id",
                (user_id,))
        for row in rows:
            pred = self.latest_prediction(user_id, row["equipment_id"])
            row["risk_level"] = self._risk_for(row, pred)
            row["risk_probability"] = pred["probability"] if pred else None
            maint = self.list_maintenance(user_id, row["equipment_id"])
            row["last_service_date"] = (maint[0]["service_date"] if maint else None)
            row["next_service_date"] = (maint[0]["next_service_date"] if maint else None)
        return rows

    def get_equipment(self, user_id, equipment_id):
        if self.mode == "demo":
            e = next((dict(e) for e in self._store["equipment"]
                      if e["user_id"] == user_id and e["equipment_id"] == equipment_id), None)
        else:
            rows = self._query(
                "SELECT * FROM equipment WHERE user_id=%s AND equipment_id=%s",
                (user_id, equipment_id))
            e = rows[0] if rows else None
        if e:
            pred = self.latest_prediction(user_id, equipment_id)
            e["risk_level"] = self._risk_for(e, pred)
            e["risk_probability"] = pred["probability"] if pred else None
            # Match list_equipment: expose the most recent service dates
            maint = self.list_maintenance(user_id, equipment_id)
            e["last_service_date"] = (maint[0]["service_date"] if maint else None)
            e["next_service_date"] = (maint[0]["next_service_date"] if maint else None)
        return e

    def create_equipment(self, user_id, data):
        if self.mode == "demo":
            eid = self._store["next_ids"]["equipment"]
            self._store["next_ids"]["equipment"] += 1
            row = {"equipment_id": eid, "user_id": user_id, "created_at": datetime.now()}
            row.update(data)
            self._store["equipment"].append(row)
            return eid
        return self._execute(
            """INSERT INTO equipment
               (user_id, equipment_name, equipment_type, brand, model, year,
                registration_number, purchase_date, operating_hours, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (user_id, data["equipment_name"], data["equipment_type"], data.get("brand"),
             data.get("model"), data.get("year"), data.get("registration_number"),
             data.get("purchase_date"), data.get("operating_hours"), data.get("status", "Healthy")))

    def update_equipment(self, user_id, equipment_id, data):
        if self.mode == "demo":
            # Mutate the stored row directly — get_equipment returns a copy
            e = next((x for x in self._store["equipment"]
                      if x["user_id"] == user_id
                      and x["equipment_id"] == equipment_id), None)
            if not e:
                return False
            e.update(data)
            return True
        return self._execute(
            """UPDATE equipment SET equipment_name=%s, equipment_type=%s, brand=%s,
               model=%s, year=%s, registration_number=%s, purchase_date=%s,
               operating_hours=%s, status=%s
               WHERE equipment_id=%s AND user_id=%s""",
            (data["equipment_name"], data["equipment_type"], data.get("brand"),
             data.get("model"), data.get("year"), data.get("registration_number"),
             data.get("purchase_date"), data.get("operating_hours"), data.get("status", "Healthy"),
             equipment_id, user_id))

    def delete_equipment(self, user_id, equipment_id):
        if self.mode == "demo":
            self._store["equipment"] = [e for e in self._store["equipment"]
                                        if not (e["user_id"] == user_id
                                                and e["equipment_id"] == equipment_id)]
            self._store["maintenance"] = [m for m in self._store["maintenance"]
                                          if m["equipment_id"] != equipment_id]
            self._store["operational"] = [o for o in self._store["operational"]
                                          if o["equipment_id"] != equipment_id]
            self._store["predictions"] = [p for p in self._store["predictions"]
                                          if p["equipment_id"] != equipment_id]
            return True
        return self._execute(
            "DELETE FROM equipment WHERE equipment_id=%s AND user_id=%s",
            (equipment_id, user_id))

    # ------------------------------------------------------------------ #
    #  Maintenance
    # ------------------------------------------------------------------ #
    def _demo_equipment_map(self):
        return {e["equipment_id"]: e for e in self._store["equipment"]}

    def list_maintenance(self, user_id, equipment_id=None):
        if self.mode == "demo":
            emap = self._demo_equipment_map()
            rows = [dict(m) for m in self._store["maintenance"]
                    if m["equipment_id"] in
                    [e["equipment_id"] for e in self._store["equipment"]
                     if e["user_id"] == user_id]]
            # Match the MySQL branch: newest service first
            rows.sort(key=lambda m: str(m.get("service_date") or ""), reverse=True)
            for r in rows:
                e = emap.get(r["equipment_id"]) or {}
                r["equipment_name"] = e.get("equipment_name")
                r["equipment_type"] = e.get("equipment_type")
                r["registration_number"] = e.get("registration_number")
        else:
            sql = """SELECT m.*, e.equipment_name, e.equipment_type, e.registration_number
                     FROM maintenance m JOIN equipment e ON m.equipment_id = e.equipment_id
                     WHERE e.user_id = %s"""
            args = [user_id]
            if equipment_id is not None:
                sql += " AND m.equipment_id = %s"
                args.append(equipment_id)
            sql += " ORDER BY m.service_date DESC, m.maintenance_id DESC"
            rows = self._query(sql, tuple(args))
        if equipment_id is not None:
            rows = [r for r in rows if r["equipment_id"] == equipment_id]
        return rows

    def create_maintenance(self, user_id, data):
        if self.mode == "demo":
            mid = self._store["next_ids"]["maintenance"]
            self._store["next_ids"]["maintenance"] += 1
            row = {"maintenance_id": mid, "created_at": datetime.now()}
            row.update(data)
            self._store["maintenance"].append(row)
            # Mark equipment as Maintenance Due when a service is scheduled
            if data.get("status") in ("Scheduled", "In Progress"):
                e = next((x for x in self._store["equipment"]
                          if x["user_id"] == user_id
                          and x["equipment_id"] == data["equipment_id"]), None)
                if e:
                    e["status"] = "Maintenance Due"
            return mid
        return self._execute(
            """INSERT INTO maintenance (equipment_id, service_date, service_type,
               problem_description, action_taken, parts_replaced, cost,
               next_service_date, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data["equipment_id"], data["service_date"], data["service_type"],
             data.get("problem_description"), data.get("action_taken"),
             data.get("parts_replaced"), data.get("cost", 0), data.get("next_service_date"),
             data.get("status", "Completed")))

    def update_maintenance(self, user_id, maintenance_id, data):
        if self.mode == "demo":
            m = next((m for m in self._store["maintenance"] if m["maintenance_id"] == maintenance_id), None)
            if not m:
                return False
            m.update(data)
            return True
        return self._execute(
            """UPDATE maintenance SET equipment_id=%s, service_date=%s, service_type=%s,
               problem_description=%s, action_taken=%s, parts_replaced=%s, cost=%s,
               next_service_date=%s, status=%s WHERE maintenance_id=%s""",
            (data["equipment_id"], data["service_date"], data["service_type"],
             data.get("problem_description"), data.get("action_taken"),
             data.get("parts_replaced"), data.get("cost", 0), data.get("next_service_date"),
             data.get("status", "Completed"), maintenance_id))

    def delete_maintenance(self, user_id, maintenance_id):
        if self.mode == "demo":
            before = len(self._store["maintenance"])
            self._store["maintenance"] = [m for m in self._store["maintenance"]
                                          if m["maintenance_id"] != maintenance_id]
            return len(self._store["maintenance"]) < before
        return self._execute(
            "DELETE m FROM maintenance m JOIN equipment e ON m.equipment_id=e.equipment_id "
            "WHERE e.user_id=%s AND m.maintenance_id=%s",
            (user_id, maintenance_id))

    # ------------------------------------------------------------------ #
    #  Operational data
    # ------------------------------------------------------------------ #
    def insert_operational(self, user_id, equipment_id, rows):
        """Insert one or more operational rows; returns number inserted."""
        if self.mode == "demo":
            for r in rows:
                r = dict(r)
                r["data_id"] = self._store["next_ids"]["operational"]
                self._store["next_ids"]["operational"] += 1
                r["equipment_id"] = equipment_id
                self._store["operational"].append(r)
            return len(rows)
        count = 0
        for r in rows:
            count += self._execute(
                """INSERT INTO operational_data (equipment_id, recorded_at, engine_speed,
                   engine_torque, engine_load, coolant_temperature, oil_temperature,
                   oil_pressure, fuel_rate, vehicle_speed, battery_voltage,
                   transmission, operating_hours, source)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (equipment_id, r["recorded_at"], r.get("engine_speed"), r.get("engine_torque"),
                 r.get("engine_load"), r.get("coolant_temperature"), r.get("oil_temperature"),
                 r.get("oil_pressure"), r.get("fuel_rate"), r.get("vehicle_speed"),
                 r.get("battery_voltage"), r.get("transmission"), r.get("operating_hours"),
                 r.get("source", "manual")))
        return count

    def list_operational(self, user_id, equipment_id=None, limit=25):
        if self.mode == "demo":
            rows = [dict(o) for o in self._store["operational"]
                    if o["equipment_id"] in
                    [e["equipment_id"] for e in self._store["equipment"]
                     if e["user_id"] == user_id]]
        else:
            sql = """SELECT o.* FROM operational_data o
                     JOIN equipment e ON o.equipment_id = e.equipment_id
                     WHERE e.user_id = %s"""
            args = [user_id]
            if equipment_id is not None:
                sql += " AND o.equipment_id = %s"
                args.append(equipment_id)
            sql += " ORDER BY o.recorded_at DESC LIMIT %s"
            args.append(limit)
            rows = self._query(sql, tuple(args))
        if equipment_id is not None:
            rows = [r for r in rows if r["equipment_id"] == equipment_id]
        return rows[:limit]

    def latest_operational(self, user_id, equipment_id):
        rows = self.list_operational(user_id, equipment_id, limit=1)
        return rows[0] if rows else None

    # ------------------------------------------------------------------ #
    #  Predictions
    # ------------------------------------------------------------------ #
    def insert_prediction(self, user_id, equipment_id, pred):
        if self.mode == "demo":
            pid = self._store["next_ids"]["prediction"]
            self._store["next_ids"]["prediction"] += 1
            row = {"prediction_id": pid, "equipment_id": equipment_id}
            row.update(pred)
            self._store["predictions"].append(row)
            # Keep dashboard status in sync with the latest prediction
            if pred["condition"] == "Anomalous" and pred["risk_level"] == "High":
                e = next((x for x in self._store["equipment"]
                          if x["user_id"] == user_id
                          and x["equipment_id"] == equipment_id), None)
                if e:
                    e["status"] = "High Risk"
            return pid
        return self._execute(
            """INSERT INTO predictions (equipment_id, prediction_date, condition,
               risk_level, probability, recommendation, explanation, is_demo)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (equipment_id, pred["prediction_date"], pred["condition"],
             pred["risk_level"], pred["probability"], pred["recommendation"],
             pred.get("explanation"), 1 if pred.get("is_demo") else 0))

    def list_predictions(self, user_id, equipment_id=None, limit=50):
        if self.mode == "demo":
            emap = self._demo_equipment_map()
            rows = [dict(p) for p in self._store["predictions"]
                    if p["equipment_id"] in
                    [e["equipment_id"] for e in self._store["equipment"]
                     if e["user_id"] == user_id]]
            # Match the MySQL branch: newest prediction first
            rows.sort(key=lambda p: str(p.get("prediction_date") or ""), reverse=True)
            for r in rows:
                e = emap.get(r["equipment_id"]) or {}
                r["equipment_name"] = e.get("equipment_name")
        else:
            sql = """SELECT p.*, e.equipment_name FROM predictions p
                     JOIN equipment e ON p.equipment_id = e.equipment_id
                     WHERE e.user_id = %s"""
            args = [user_id]
            if equipment_id is not None:
                sql += " AND p.equipment_id = %s"
                args.append(equipment_id)
            sql += " ORDER BY p.prediction_date DESC LIMIT %s"
            args.append(limit)
            rows = self._query(sql, tuple(args))
        if equipment_id is not None:
            rows = [r for r in rows if r["equipment_id"] == equipment_id]
        return rows[:limit]

    def latest_prediction(self, user_id, equipment_id):
        rows = self.list_predictions(user_id, equipment_id, limit=1)
        return rows[0] if rows else None

    # ------------------------------------------------------------------ #
    #  Chat history
    # ------------------------------------------------------------------ #
    def add_chat(self, user_id, question, answer, equipment_id=None):
        if self.mode == "demo":
            cid = self._store["next_ids"]["chat"]
            self._store["next_ids"]["chat"] += 1
            self._store["chat"].insert(0, {
                "chat_id": cid, "user_id": user_id, "question": question,
                "answer": answer, "equipment_id": equipment_id,
                "created_at": datetime.now()})
            return cid
        return self._execute(
            "INSERT INTO chat_history (user_id, question, answer, equipment_id) "
            "VALUES (%s,%s,%s,%s)",
            (user_id, question, answer, equipment_id))

    def list_chat(self, user_id):
        if self.mode == "demo":
            rows = [dict(c) for c in self._store["chat"] if c["user_id"] == user_id]
        else:
            rows = self._query(
                "SELECT * FROM chat_history WHERE user_id=%s ORDER BY created_at DESC LIMIT 100",
                (user_id,))
        return rows

    def clear_chat(self, user_id):
        if self.mode == "demo":
            self._store["chat"] = [c for c in self._store["chat"] if c["user_id"] != user_id]
            return True
        self._execute("DELETE FROM chat_history WHERE user_id=%s", (user_id,))
        return True

    # ------------------------------------------------------------------ #
    #  Chat conversations (ChatGPT-style threads) + messages
    # ------------------------------------------------------------------ #
    def create_conversation(self, user_id, title="New chat", equipment_id=None):
        if self.mode == "demo":
            cid = self._store["next_ids"].setdefault("conversation", 1)
            self._store["next_ids"]["conversation"] = cid + 1
            conv = {"conversation_id": cid, "user_id": user_id, "title": title,
                    "equipment_id": equipment_id, "created_at": datetime.now(),
                    "updated_at": datetime.now()}
            self._store["conversations"].insert(0, conv)
            return cid
        return self._execute(
            "INSERT INTO chat_conversations (user_id, title, equipment_id) "
            "VALUES (%s,%s,%s)", (user_id, title, equipment_id))

    def list_conversations(self, user_id, query=None, limit=50):
        if self.mode == "demo":
            rows = [dict(c) for c in self._store["conversations"]
                    if c["user_id"] == user_id]
        else:
            if query:
                like = f"%{query}%"
                rows = self._query(
                    """SELECT DISTINCT c.* FROM chat_conversations c
                       LEFT JOIN chat_messages m ON m.conversation_id = c.conversation_id
                       WHERE c.user_id=%s AND (c.title LIKE %s OR m.content LIKE %s)
                       ORDER BY c.updated_at DESC LIMIT %s""",
                    (user_id, like, like, limit))
            else:
                rows = self._query(
                    "SELECT * FROM chat_conversations WHERE user_id=%s "
                    "ORDER BY updated_at DESC LIMIT %s", (user_id, limit))
        if query:                       # demo-mode search over titles + messages
            q = query.lower()
            conv_ids = {m["conversation_id"] for m in self._store["messages"]
                        if m["user_id"] == user_id and q in (m.get("content") or "").lower()}
            rows = [c for c in rows
                    if q in (c.get("title") or "").lower()
                    or c["conversation_id"] in conv_ids]
        return rows[:limit]

    def get_conversation(self, user_id, conversation_id):
        """Ownership-checked conversation fetch."""
        if self.mode == "demo":
            conv = next((c for c in self._store["conversations"]
                         if c["conversation_id"] == conversation_id), None)
            return dict(conv) if conv and conv["user_id"] == user_id else None
        rows = self._query(
            "SELECT * FROM chat_conversations WHERE conversation_id=%s AND user_id=%s",
            (conversation_id, user_id))
        return rows[0] if rows else None

    def rename_conversation_equip(self, user_id, conversation_id, equipment_id):
        """Attach an equipment selection to an existing conversation."""
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            return False
        if self.mode == "demo":
            for c in self._store["conversations"]:
                if c["conversation_id"] == conversation_id:
                    c["equipment_id"] = equipment_id
            return True
        self._execute(
            "UPDATE chat_conversations SET equipment_id=%s "
            "WHERE conversation_id=%s AND user_id=%s",
            (equipment_id, conversation_id, user_id))
        return True

    def rename_conversation(self, user_id, conversation_id, title):
        title = (title or "").strip()[:160] or "New chat"
        if self.mode == "demo":
            conv = self.get_conversation(user_id, conversation_id)
            if not conv:
                return False
            for c in self._store["conversations"]:
                if c["conversation_id"] == conversation_id:
                    c["title"] = title
                    c["updated_at"] = datetime.now()
            return True
        self._execute(
            "UPDATE chat_conversations SET title=%s WHERE conversation_id=%s AND user_id=%s",
            (title, conversation_id, user_id))
        return True

    def delete_conversation(self, user_id, conversation_id):
        if self.mode == "demo":
            before = len(self._store["conversations"])
            self._store["conversations"] = [
                c for c in self._store["conversations"]
                if not (c["conversation_id"] == conversation_id
                        and c["user_id"] == user_id)]
            self._store["messages"] = [
                m for m in self._store["messages"]
                if m["conversation_id"] != conversation_id]
            return len(self._store["conversations"]) < before
        self._execute(
            "DELETE FROM chat_conversations WHERE conversation_id=%s AND user_id=%s",
            (conversation_id, user_id))     # messages cascade
        return True

    def add_message(self, conversation_id, user_id, role, content,
                    equipment_id=None):
        if self.mode == "demo":
            mid = self._store["next_ids"].setdefault("message", 1)
            self._store["next_ids"]["message"] = mid + 1
            self._store["messages"].append({
                "message_id": mid, "conversation_id": conversation_id,
                "user_id": user_id, "role": role, "content": content,
                "equipment_id": equipment_id, "created_at": datetime.now()})
        else:
            self._execute(
                "INSERT INTO chat_messages (conversation_id, user_id, role, content, equipment_id) "
                "VALUES (%s,%s,%s,%s,%s)",
                (conversation_id, user_id, role, content, equipment_id))
        # Touch the conversation's updated_at (demo tracks it via list order).
        if self.mode == "demo":
            for c in self._store["conversations"]:
                if c["conversation_id"] == conversation_id:
                    c["updated_at"] = datetime.now()
        else:
            self._execute(
                "UPDATE chat_conversations SET updated_at=CURRENT_TIMESTAMP "
                "WHERE conversation_id=%s", (conversation_id,))
        return True

    def list_messages(self, conversation_id):
        if self.mode == "demo":
            rows = [dict(m) for m in self._store["messages"]
                    if m["conversation_id"] == conversation_id]
            rows.sort(key=lambda m: m["message_id"])
            return rows
        return self._query(
            "SELECT * FROM chat_messages WHERE conversation_id=%s ORDER BY message_id",
            (conversation_id,))

    def clear_conversation_messages(self, conversation_id):
        if self.mode == "demo":
            self._store["messages"] = [m for m in self._store["messages"]
                                        if m["conversation_id"] != conversation_id]
            return True
        self._execute("DELETE FROM chat_messages WHERE conversation_id=%s",
                      (conversation_id,))
        return True

    # ------------------------------------------------------------------ #
    #  Notifications
    # ------------------------------------------------------------------ #
    def create_notification(self, user_id, title, message, ntype="info"):
        if self.mode == "demo":
            nid = self._store["next_ids"]["notification"]
            self._store["next_ids"]["notification"] += 1
            self._store["notifications"].insert(0, {
                "notification_id": nid, "user_id": user_id, "title": title,
                "message": message, "notification_type": ntype,
                "is_read": 0, "created_at": datetime.now()})
            return nid
        return self._execute(
            "INSERT INTO notifications (user_id, title, message, notification_type) "
            "VALUES (%s,%s,%s,%s)",
            (user_id, title, message, ntype))

    # ------------------------------------------------------------------ #
    #  Notification preferences
    # ------------------------------------------------------------------ #
    DEFAULT_PREFS = {
        "email_notifications": True, "sms_notifications": False,
        "maintenance_alerts": True, "prediction_alerts": True,
        "high_risk_alerts": True, "critical_alerts": True,
        "preferred_method": "email",
    }

    def get_notification_prefs(self, user_id):
        if self.mode == "demo":
            p = self._store["notif_prefs"].get(user_id)
            if p is None:
                return dict(self.DEFAULT_PREFS)
            merged = dict(self.DEFAULT_PREFS)
            merged.update(p)
            return merged
        rows = self._query(
            "SELECT * FROM notification_preferences WHERE user_id=%s", (user_id,))
        if not rows:
            return dict(self.DEFAULT_PREFS)
        row = rows[0]
        return {
            "email_notifications": bool(row.get("email_notifications", 1)),
            "sms_notifications": bool(row.get("sms_notifications", 0)),
            "maintenance_alerts": bool(row.get("maintenance_alerts", 1)),
            "prediction_alerts": bool(row.get("prediction_alerts", 1)),
            "high_risk_alerts": bool(row.get("high_risk_alerts", 1)),
            "critical_alerts": bool(row.get("critical_alerts", 1)),
            "preferred_method": row.get("preferred_method") or "email",
        }

    def update_notification_prefs(self, user_id, data):
        clean = {k: data[k] for k in
                 ("email_notifications", "sms_notifications", "maintenance_alerts",
                  "prediction_alerts", "high_risk_alerts", "critical_alerts")
                 if k in data and data[k] is not None}
        clean = {k: 1 if v else 0 for k, v in clean.items()}
        if "preferred_method" in data:
            pm = str(data["preferred_method"]).strip().lower()
            clean["preferred_method"] = pm if pm in ("email", "sms", "both") else "email"
        if self.mode == "demo":
            p = self._store["notif_prefs"].setdefault(user_id, dict(self.DEFAULT_PREFS))
            p.update({k: bool(v) if k != "preferred_method" else v
                      for k, v in clean.items()})
            return True
        if not clean:
            return True
        cols = ", ".join(f"{k}=%s" for k in clean)
        self._execute(
            f"""INSERT INTO notification_preferences (user_id, {', '.join(clean)})
               VALUES (%s, {', '.join(['%s'] * len(clean))})
               ON DUPLICATE KEY UPDATE {cols}""",
            tuple([user_id] + list(clean.values()) + list(clean.values())))
        return True

    # ------------------------------------------------------------------ #
    #  Maintenance alerts (delivery log with dedup)
    # ------------------------------------------------------------------ #
    def create_alert(self, user_id, equipment_id, equipment_name, event_type,
                     severity, title, message, dedup_key=None):
        """Insert an alert row. Returns (alert_id, is_new) — is_new False when
        the dedup_key already exists (duplicate event)."""
        if self.mode == "demo":
            existing = next((a for a in self._store["alerts"]
                             if a["dedup_key"] and a["dedup_key"] == dedup_key), None)
            if existing:
                return existing["alert_id"], False
            aid = self._store["next_ids"]["alert"]
            self._store["next_ids"]["alert"] += 1
            self._store["alerts"].insert(0, {
                "alert_id": aid, "user_id": user_id,
                "equipment_id": equipment_id, "equipment_name": equipment_name,
                "event_type": event_type, "severity": severity, "title": title,
                "message": message, "dedup_key": dedup_key,
                "email_status": "not_sent", "sms_status": "not_sent",
                "created_at": datetime.now()})
            return aid, True
        try:
            aid = self._execute(
                """INSERT INTO maintenance_alerts (user_id, equipment_id,
                   equipment_name, event_type, severity, title, message, dedup_key)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (user_id, equipment_id, equipment_name, event_type, severity,
                 title, message, dedup_key))
            return aid, True
        except Exception:            # noqa: BLE001 — duplicate dedup_key
            rows = self._query("SELECT alert_id FROM maintenance_alerts "
                               "WHERE dedup_key=%s", (dedup_key,))
            return (rows[0]["alert_id"] if rows else None), False

    def update_alert_delivery(self, alert_id, email_status=None, sms_status=None):
        if self.mode == "demo":
            a = next((a for a in self._store["alerts"] if a["alert_id"] == alert_id), None)
            if not a:
                return False
            if email_status:
                a["email_status"] = email_status
            if sms_status:
                a["sms_status"] = sms_status
            return True
        sets, args = [], []
        if email_status:
            sets.append("email_status=%s"); args.append(email_status)
        if sms_status:
            sets.append("sms_status=%s"); args.append(sms_status)
        if not sets:
            return True
        self._execute(f"UPDATE maintenance_alerts SET {', '.join(sets)} "
                      "WHERE alert_id=%s", tuple(args + [alert_id]))
        return True

    def list_alerts(self, user_id=None, limit=100):
        if self.mode == "demo":
            rows = [dict(a) for a in self._store["alerts"]
                    if user_id is None or a["user_id"] == user_id]
            return rows[:limit]
        if user_id is None:
            return self._query(
                "SELECT * FROM maintenance_alerts ORDER BY created_at DESC LIMIT %s",
                (limit,))
        return self._query(
            "SELECT * FROM maintenance_alerts WHERE user_id=%s "
            "ORDER BY created_at DESC LIMIT %s", (user_id, limit))

    # ------------------------------------------------------------------ #
    #  Admin
    # ------------------------------------------------------------------ #
    def admin_list_users(self):
        """All users with verification status (admin page)."""
        if self.mode == "demo":
            rows = []
            for u in self._store["users"]:
                p = self._store["profiles"].get(u["user_id"], {})
                rows.append({"user_id": u["user_id"], "name": u["name"],
                             "email": u["email"], "phone": u.get("phone") or "",
                             "email_verified": p.get("email_verified", False),
                             "phone_verified": p.get("phone_verified", False),
                             "is_admin": p.get("is_admin", False),
                             "created_at": u.get("created_at")})
            return rows
        rows = self._query(
            """SELECT u.user_id, u.name, u.email, u.phone, u.created_at,
                      p.email_verified, p.phone_verified, p.is_admin
               FROM users u LEFT JOIN user_profiles p ON u.user_id = p.user_id
               ORDER BY u.user_id""")
        for r in rows:
            r["email_verified"] = bool(r.get("email_verified"))
            r["phone_verified"] = bool(r.get("phone_verified"))
            r["is_admin"] = bool(r.get("is_admin"))
        return rows

    def list_notifications(self, user_id):
        if self.mode == "demo":
            rows = [dict(n) for n in self._store["notifications"]
                    if n["user_id"] == user_id]
        else:
            rows = self._query(
                "SELECT * FROM notifications WHERE user_id=%s "
                "ORDER BY created_at DESC LIMIT 50", (user_id,))
        return rows

    def unread_notifications(self, user_id):
        if self.mode == "demo":
            return sum(1 for n in self._store["notifications"]
                       if n["user_id"] == user_id and not n["is_read"])
        rows = self._query(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=0",
            (user_id,))
        return rows[0]["c"] if rows else 0

    def mark_notifications_read(self, user_id):
        if self.mode == "demo":
            for n in self._store["notifications"]:
                if n["user_id"] == user_id:
                    n["is_read"] = 1
            return True
        self._execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (user_id,))
        return True

    # ------------------------------------------------------------------ #
    #  Dashboard
    # ------------------------------------------------------------------ #
    def dashboard(self, user_id):
        equipment = self.list_equipment(user_id)
        maintenance = self.list_maintenance(user_id)
        predictions = self.list_predictions(user_id)
        notifications = self.list_notifications(user_id)

        good = sum(1 for e in equipment if e["status"] == "Healthy")
        due = sum(1 for e in equipment if e["status"] in ("Maintenance Due", "Warning"))
        high_risk = sum(1 for e in equipment if e["status"] == "High Risk")

        # Charts ---------------------------------------------------------
        condition_chart = {
            "labels": ["Healthy", "Maintenance Due", "Warning", "High Risk"],
            "values": [
                sum(1 for e in equipment if e["status"] == "Healthy"),
                sum(1 for e in equipment if e["status"] == "Maintenance Due"),
                sum(1 for e in equipment if e["status"] == "Warning"),
                sum(1 for e in equipment if e["status"] == "High Risk"),
            ],
            "colors": ["#22c55e", "#f59e0b", "#eab308", "#ef4444"],
        }

        risk_chart = {"labels": ["Low", "Medium", "High"], "values": [0, 0, 0],
                      "colors": ["#22c55e", "#f59e0b", "#ef4444"]}
        for e in equipment:
            level = e["risk_level"]
            if level in risk_chart["labels"]:
                risk_chart["values"][risk_chart["labels"].index(level)] += 1

        now = datetime.now()
        months, counts = [], []
        for i in range(5, -1, -1):
            key = (now - timedelta(days=30 * i)).strftime("%Y-%m")
            months.append((now - timedelta(days=30 * i)).strftime("%b"))
            counts.append(sum(1 for m in maintenance
                              if (m["service_date"] or "")[:7] == key))
        maintenance_chart = {"labels": months, "values": counts}

        usage_chart = {"labels": [e["equipment_name"] for e in equipment],
                       "values": [float(e["operating_hours"] or 0) for e in equipment],
                       "colors": "#166534"}

        # Recent activity -------------------------------------------------
        activity = []
        for m in maintenance[:6]:
            activity.append({"type": "maintenance", "text":
                             f"{m.get('equipment_name', 'Equipment')} maintenance recorded",
                             "detail": m["service_type"], "date": m["service_date"]})
        for p in predictions[:5]:
            activity.append({"type": "prediction", "text":
                             f"Prediction generated for {p.get('equipment_name', 'Equipment')}",
                             "detail": f"{p['condition']} · {p['risk_level']} risk",
                             "date": p["prediction_date"]})
        for n in notifications[:4]:
            activity.append({"type": "notification", "text": n["title"],
                             "detail": n["message"], "date": n["created_at"]})
        activity.sort(key=lambda a: str(a["date"]), reverse=True)
        activity = activity[:8]

        return {
            "stats": {"total": len(equipment), "good": good, "due": due,
                      "high_risk": high_risk},
            "health": [{
                "equipment_id": e["equipment_id"], "equipment_name": e["equipment_name"],
                "equipment_type": e["equipment_type"], "status": e["status"],
                "risk_level": e["risk_level"],
                "risk_probability": e["risk_probability"],
                "last_service_date": e["last_service_date"],
                "next_service_date": e["next_service_date"],
            } for e in equipment],
            "charts": {"condition": condition_chart, "risk": risk_chart,
                       "maintenance": maintenance_chart, "usage": usage_chart},
            "activity": activity,
        }

    # ------------------------------------------------------------------ #
    #  Reports
    # ------------------------------------------------------------------ #
    def reports(self, user_id, report_type="equipment", equipment_id=None,
                date_from=None, date_to=None, risk=None):
        equipment = self.list_equipment(user_id)
        maintenance = self.list_maintenance(user_id)
        predictions = self.list_predictions(user_id)

        def in_range(date_val):
            if not date_val:
                return True
            d = str(date_val)[:10]
            if date_from and d < date_from:
                return False
            if date_to and d > date_to:
                return False
            return True

        def risk_ok(level):
            return not risk or (level or "").lower() == risk.lower()

        if report_type == "equipment":
            rows = []
            for e in equipment:
                if equipment_id and e["equipment_id"] != equipment_id:
                    continue
                if not risk_ok(e["risk_level"]):
                    continue
                rows.append({
                    "Equipment ID": e.get("registration_number") or f"EQ-{e['equipment_id']:03d}",
                    "Equipment Name": e["equipment_name"], "Type": e["equipment_type"],
                    "Brand": e.get("brand") or "-", "Model": e.get("model") or "-",
                    "Year": e.get("year") or "-", "Operating Hours": e["operating_hours"],
                    "Status": e["status"], "Risk Level": e["risk_level"]})
        elif report_type == "maintenance":
            rows = []
            for m in maintenance:
                if equipment_id and m["equipment_id"] != equipment_id:
                    continue
                if not in_range(m["service_date"]):
                    continue
                rows.append({
                    "Equipment": m.get("equipment_name", "-"), "Date": m["service_date"],
                    "Service Type": m["service_type"],
                    "Problem": m.get("problem_description") or "-",
                    "Action Taken": m.get("action_taken") or "-",
                    "Parts Replaced": m.get("parts_replaced") or "-",
                    "Cost": float(m.get("cost") or 0),
                    "Next Service": m.get("next_service_date") or "-",
                    "Status": m.get("status", "Completed")})
        elif report_type == "prediction":
            rows = []
            for p in predictions:
                if equipment_id and p["equipment_id"] != equipment_id:
                    continue
                if not in_range(p["prediction_date"]):
                    continue
                if not risk_ok(p["risk_level"]):
                    continue
                rows.append({
                    "Equipment": p.get("equipment_name", "-"),
                    "Date": str(p["prediction_date"])[:16],
                    "Condition": p["condition"], "Risk Level": p["risk_level"],
                    "Probability": f"{p['probability']}%",
                    "Recommendation": p.get("recommendation") or "-",
                    "Source": "Demo" if p.get("is_demo") else "Model"})
        else:  # risk report
            rows = []
            for e in equipment:
                if equipment_id and e["equipment_id"] != equipment_id:
                    continue
                if not risk_ok(e["risk_level"]):
                    continue
                rows.append({
                    "Equipment": e["equipment_name"], "Type": e["equipment_type"],
                    "Status": e["status"], "Risk Level": e["risk_level"],
                    "Risk Probability": f"{e['risk_probability']}%" if e.get("risk_probability") else "-",
                    "Last Service": e.get("last_service_date") or "-",
                    "Next Service": e.get("next_service_date") or "-"})
        return rows

    # ------------------------------------------------------------------ #
    #  Misc
    # ------------------------------------------------------------------ #
    def demo_banner(self):
        return None if self.mode == "mysql" else DEMO_MODE_LABEL


db = Database()