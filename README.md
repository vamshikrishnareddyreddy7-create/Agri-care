# AgriCare — AI-Based Farm Equipment Management and Predictive Maintenance

A farmer-friendly web application that manages agricultural equipment, keeps digital
maintenance records, ingests operational data (manual entry or CSV), identifies
abnormal equipment conditions with a machine-learning model, estimates maintenance
risk, gives maintenance recommendations and answers questions through an AI chatbot.

> **Capstone scope note:** the current ML task is **condition / anomaly prediction**
> converted into a **maintenance-risk indicator**. The system does **not** predict the
> exact date of a failure, and no fabricated accuracy figures are presented as
> real-world performance.

---

## Quick start (Demo Mode — no database required)

```bash
# 1. Create a virtual environment (PyCharm can do this for you)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install the runtime dependencies
pip install -r requirements.txt

# 3. Run
python app.py
```

Open **http://127.0.0.1:5000** and sign in with the demo account:

| Field    | Value              |
|----------|--------------------|
| Email    | `farmer@demo.com`  |
| Password | `demo1234`         |

Without a MySQL database the app runs in **Demo Mode**: it seeds realistic sample
data (Tümosan 81.110 tractor, John Deere 5055E, Claas harvester, KSB pump, Hardi
sprayer, maintenance records, operational readings and predictions). Every demo
artefact is clearly labeled in the UI, and predictions made without the trained ML
model are labeled **"Demo Prediction — ML model not connected"**.

---

## Project structure

```
├── app.py                      # Flask app: pages, session auth, REST API
├── config.py                   # env-based configuration
├── requirements.txt
├── .env.example                # copy to .env and fill in secrets (never commit .env)
├── Procfile / render.yaml      # Render deployment
├── database/
│   └── schema.sql              # USERS, EQUIPMENT, MAINTENANCE, OPERATIONAL_DATA,
│                               # PREDICTIONS, CHAT_HISTORY, NOTIFICATIONS
├── model/
│   ├── train_model.py          # dataset generation + model training (XGBoost / sklearn)
│   └── predictive_model.pkl    # generated artifact (gitignored)
├── services/
│   ├── database_service.py     # one interface: MySQL or in-memory demo store
│   ├── demo_data.py            # bundled realistic sample dataset
│   ├── ml_service.py           # model loading + transparent rule-based demo fallback
│   ├── chatbot_service.py      # RAG-style retrieval + optional LLM call
│   └── knowledge_base.json     # maintenance Q&A content for the chatbot
├── static/
│   ├── css/style.css           # design system (green agri-tech theme, responsive)
│   └── js/                     # api.js, app.js, charts.js + one script per page
└── templates/                  # Jinja2 pages (landing, auth + app pages)
```

---

## Features

| Module                | What it does |
|-----------------------|--------------|
| Landing page          | Hero, features, 5-step "How It Works", benefits, footer |
| Auth                  | Register / login / logout, hashed passwords (werkzeug), session cookies |
| Dashboard             | Summary cards, equipment health overview, condition/risk/usage charts, activity feed |
| Equipment             | Card + table views, add/edit modal, delete confirmation, search, filters, per-equipment risk |
| Equipment details     | Full info, health & risk panel, quick actions (Predict / Maintenance / AI), histories |
| Maintenance records   | Digital service history with costs, parts, next service; full CRUD |
| Operational data      | Manual parameter entry **or** CSV upload with parsed summary (records, date range, averages) |
| Predictive maintenance| `POST /api/predict` — Normal/Anomalous condition, Low/Med/High risk, probability, recommendation + explanation |
| AI Assistant          | Chat UI with quick questions, mic placeholder, clear chat, per-equipment context, disclaimer |
| Reports               | Equipment / maintenance / prediction / risk reports with filters, CSV export, print |
| Notifications         | Maintenance due, high-risk alerts, prediction-ready reminders, upload confirmations |
| Profile               | Account details, password change, notification prefs, theme (light/dark), language placeholder |

---

## Connecting MySQL

1. Create the database and tables:

   ```bash
   mysql -u root -p < database/schema.sql
   ```

2. Configure `.env` (copy from `.env.example`):

   ```ini
   MYSQL_HOST=localhost
   MYSQL_USER=root
   MYSQL_PASSWORD=yourpassword
   MYSQL_DATABASE=farm_equipment
   # or a full URL: DATABASE_URL=mysql+pymysql://user:pass@host/dbname
   ```

3. Restart the app. The banner switches from *Demo Mode* to real MySQL. If the DB is
   unreachable the app falls back to Demo Mode automatically, so it never crashes on
   startup.

All queries use **parameterized statements** (SQL-injection safe). Table creation runs
automatically on startup from `database/schema.sql`.

---

## Training the ML model

```bash
pip install -r requirements.txt   # includes scikit-learn, xgboost, pandas, joblib
python model/train_model.py
```

The script:
1. generates a realistic tractor-operational dataset (normal + injected abnormal
   readings) → `model/tractor_operational_dataset.csv`,
2. trains an anomaly/condition classifier (XGBoost, falling back to scikit-learn
   GradientBoosting),
3. prints honest test metrics (accuracy, ROC AUC) — these describe the **demo
   dataset**, not real-world failure prediction,
4. saves `model/predictive_model.pkl`.

Restart the app afterwards: the prediction page shows **"ML model connected"** and
`/api/predict` responses no longer carry the demo flag.

**Without the model file**, `ml_service.py` uses a transparent rule-based check over
typical operating ranges and marks every result as a **Demo Prediction**, so the demo
works on a machine without the scientific stack.

---

## AI chatbot

- Without any configuration the assistant answers from the bundled
  `services/knowledge_base.json` using keyword retrieval.
- Set `LLM_API_KEY` (and optionally `LLM_API_URL` / `LLM_MODEL`) in `.env` to enable
  the RAG path: relevant knowledge-base context (+ the selected machine's latest
  prediction) is sent to the LLM and its answer is returned.
- Every answer includes the required disclaimer: *"AI-generated guidance is for
  assistance. Always follow the equipment manufacturer's service instructions and
  consult a qualified technician for serious problems."*

---

## API reference (all JSON, session-protected)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/login` · `/api/register` · `/api/logout` | Auth |
| POST | `/api/forgot-password` · `/api/reset-password` | Password reset (single-use, 30-min token) |
| GET | `/api/dashboard` | Dashboard stats, health, charts, activity |
| GET/POST | `/api/equipment` | List / create equipment |
| GET/PUT/DELETE | `/api/equipment/<id>` | Detail / update / delete |
| GET/POST | `/api/maintenance` | List / create maintenance |
| PUT/DELETE | `/api/maintenance/<id>` | Update / delete maintenance |
| POST | `/api/operational-data` | Manual reading |
| POST | `/api/upload-csv` | CSV upload (`multipart/form-data`) |
| GET | `/api/operational-data` | Recent readings |
| POST | `/api/predict` | ML condition analysis |
| GET | `/api/predictions` | Prediction history |
| POST | `/api/chat` · GET `/api/chat/history` · POST `/api/chat/clear` | Chatbot |
| GET | `/api/reports` | Filtered report rows (`type`, `equipment_id`, `from`, `to`, `risk`) |
| GET/POST | `/api/notifications` · `/api/notifications/read` | Notifications |
| GET/PUT | `/api/profile` · POST `/api/change-password` · PUT `/api/preferences` | Profile |

Frontend code talks to the backend exclusively through `static/js/api.js`, so the
endpoints can be pointed at a separate Flask service by editing that one file.

---

## Security notes

- Passwords hashed with `werkzeug.security` (PBKDF2), never stored in plain text.
- Session-based auth with `HttpOnly` + `SameSite=Lax` cookies and a `SECRET_KEY`.
- **CSRF protection**: every state-changing `/api/*` call must carry the session
  token (header `X-CSRF-Token`, rendered into a `<meta>` tag on each page).
- **Rate limiting** on sensitive endpoints: login (5 attempts / 5 min per email,
  then 429), registration, OTP send/verify, password reset, test alerts.
- All secrets via environment variables (`SECRET_KEY`, `DATABASE_URL`/`MYSQL_*`,
  `LLM_API_KEY`, `EMAIL_*`, `SMS_*`, `AUTH_SECRET`) — never hard-coded, `.env`
  is gitignored.
- Email verification and password reset use single-use, expiring tokens: only a
  SHA-256 hash is stored, links are sent by SMTP (or simulated to the server log
  in demo mode), and the forgot-password response never reveals whether an email
  is registered.
- Phone OTP codes are hashed, expire in 10 minutes, allow max 5 attempts and are
  rate-limited; changing the phone number resets verification.
- Input validation on the client *and* the server for every form/API.
- API routes are protected; unauthenticated calls return `401`, cross-account
  access returns `404`, non-admin access to admin APIs returns `403`.

---

## Authentication & notifications

### How authentication works

1. **Register** → account created (PBKDF2 password hash) + verification email.
2. **Verify email** → `/verify-email?token=…` (single-use, 24 h token). Key
   functionality is gated until verified; a banner offers a resend link.
3. **Login** → session cookie (`HttpOnly`, `SameSite=Lax`) + CSRF token.
4. **Forgot password** → emailed token (`/reset-password?token=…`), single-use,
   30-minute expiry.
5. **Change password / profile** from the Profile page; phone numbers are
   verified by OTP before SMS alerts are sent.

### How notifications work

```
Event (prediction / maintenance / status change)
  → notification_service (dedup key)
  → user preferences check (email/sms/category toggles)
  → severity thresholds (ALERT_EMAIL_MIN_SEVERITY / ALERT_SMS_MIN_SEVERITY)
  → in-app alert (always)  +  email  +  SMS
  → delivery status recorded in maintenance_alerts (Notification history page)
```

* Severity ladder: `low < medium < high < critical`. Defaults: email from
  `medium`, SMS from `high` — configurable via env vars.
* Duplicate suppression: one alert per (event, equipment, day) — re-running the
  same prediction never spams the farmer.
* Failures are recorded in the alert history (status `failed`) and never crash
  the app; the admin page lists failed deliveries.
* Real-time dashboard updates: the notification bell polls
  `/api/notifications/poll` every 30 s (lightweight, secure, no fake WebSockets).
* Safe test mode: **Profile → Send test alert** exercises the whole pipeline
  with a clearly-labeled test event (rate-limited to 3 per 5 minutes).

### Admin

Users with `is_admin` (set via `user_profiles.is_admin` in MySQL, or the seeded
demo profile) get a **Admin** sidebar entry: registered users, verification
status, delivery health, failed email/SMS. Normal users get 403.

### Email provider setup

Demo mode (default): no config needed — emails are printed to the server log
and the UI reveals the verification link. For real delivery set:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your@gmail.com
EMAIL_PASSWORD=your-app-password     # Gmail: create an App Password
EMAIL_FROM="AgriCare <your@gmail.com>"
```

Any SMTP provider works (Gmail, Outlook, SendGrid, Mailgun, Brevo…).

### SMS provider setup

Demo mode (default): OTPs and alerts are printed to the server log. For real
delivery (Twilio):

```env
SMS_PROVIDER=twilio
SMS_API_KEY=ACxxxxxxxxxxxxxxxx      # Twilio Account SID
SMS_API_SECRET=your-auth-token
SMS_FROM_NUMBER=+15551234567
```

SMS is only sent to **verified** phone numbers (OTP-verified on the Profile
page) and only for events at/above `ALERT_SMS_MIN_SEVERITY`.

---

## Deployment (Render)

The repo ships with `render.yaml` (blueprint), `Procfile` (gunicorn start), and
the **trained ML model committed** (`model/predictive_model.pkl` — the dataset
and other artifacts stay gitignored and can be regenerated with
`python model/train_model.py` at any time).

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "AgriCare — farm equipment management + predictive maintenance"
```

Verify the model is tracked (it must be — the model does not exist on Render
otherwise):

```bash
git check-ignore -v model/predictive_model.pkl   # should print nothing = tracked
```

Create the repository on GitHub and push (GitHub → New repository → copy URL):

```bash
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

> The project is not yet a git repository — the commands above initialize it.
> `.gitignore` already excludes `.env`, `__pycache__`, the venv, logs and the
> generated dataset CSV, so no secrets or junk get pushed.

### 2. Create the Web Service on Render

1. Render dashboard → **New + → Blueprint** and select the repo (uses
   `render.yaml`), or **New + → Web Service** manually.
2. Runtime **Python 3**, build & start commands come from `render.yaml`
   (build installs deps **and verifies the ML model loads**; start runs gunicorn).
3. Add environment variables (from `.env.example`):
   - `SECRET_KEY` — auto-generated by the blueprint.
   - `FLASK_DEBUG=0`.
   - Leave `MYSQL_*` / `DATABASE_URL` empty to run in **Demo Mode**
     (fully functional with sample data), or fill them in for a real database.
   - Optional: `LLM_API_KEY` (AI chatbot RAG), `SMTP_*` (real reset emails).
4. Deploy. First boot creates all MySQL tables automatically when MySQL is
   configured (`CREATE TABLE IF NOT EXISTS`).

### 3. Add a MySQL database (optional but recommended)

1. Render dashboard → **New + → MySQL**, name it, choose a plan, create.
2. Open the database → **Connections** → copy the *MySQL Connection String*.
3. Web service → **Environment** → set `DATABASE_URL` to that string
   (format `mysql://user:pass@host:3306/dbname`; special characters in the
   password are URL-encoded already). If the database was created **after**
   the web service, link them or paste the URL manually, then redeploy.

### 4. Free-plan notes

- Free services sleep after ~15 min idle; the first request after sleeping
  takes ~30–60 s to answer (the ML model reloads on boot — that is normal).
- The model (≈200 KB) loads in well under a second; gunicorn starts 2 workers,
  so the model lives once per worker (≈2 MB RAM total).
- Render's free MySQL is limited; the External Connection String works too if
  you use a managed provider elsewhere.

### Updating the model later

After retraining locally (`python model/train_model.py`), just
`git add model/predictive_model.pkl && git commit && git push` — Render
redeploys and the new model is picked up automatically.

---

## Development tips (PyCharm)

- Open the project folder, mark `static`/`templates` as resource roots.
- Use the bundled venv: `File → Settings → Project → Python Interpreter → Add → Existing`.
- Set a Flask run configuration: module `app`, or simply run `python app.py`.
- `FLASK_DEBUG=1` in `.env` enables the debugger / auto-reload for development.
