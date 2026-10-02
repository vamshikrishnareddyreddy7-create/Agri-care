import express from 'express';
import session from 'express-session';
import cookieParser from 'cookie-parser';
import nunjucks from 'nunjucks';
import path from 'path';
import { fileURLToPath } from 'url';
import multer from 'multer';
import bcrypt from 'bcryptjs';

import db from './data/store.js';
import { initMySQL, isMySQLConnected } from './data/mysql.js';
import * as mlService from './services/mlService.js';
import * as chatbotService from './services/chatbotService.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;
const upload = multer({ storage: multer.memoryStorage() });

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use('/static', express.static(path.join(__dirname, 'static')));

app.use(session({
  secret: process.env.SECRET_KEY || 'agricare-secret-key-1234',
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false }
}));

// Configure Nunjucks
const env = nunjucks.configure('templates', {
  autoescape: true,
  express: app,
  watch: false
});

// Nunjucks filters
env.addFilter('tojson', (obj) => nunjucks.runtime.markSafe(JSON.stringify(obj ?? null)));

env.addFilter('status_pill', (status) => {
  const cls = {
    'Healthy': 'pill-healthy',
    'Maintenance Due': 'pill-due',
    'Warning': 'pill-warning',
    'High Risk': 'pill-risk'
  }[status] || 'pill-muted';
  return nunjucks.runtime.markSafe(`<span class="pill ${cls}">${status || '-'}</span>`);
});

env.addFilter('risk_pill', (risk) => {
  const cls = {
    'Low': 'pill-low',
    'Medium': 'pill-medium',
    'High': 'pill-high'
  }[risk] || 'pill-muted';
  return nunjucks.runtime.markSafe(`<span class="pill ${cls}">${risk || '-'}</span>`);
});

env.addFilter('condition_pill', (cond) => {
  const cls = {
    'Normal': 'pill-normal',
    'Anomalous': 'pill-anomalous'
  }[cond] || 'pill-muted';
  return nunjucks.runtime.markSafe(`<span class="pill ${cls}">${cond || '-'}</span>`);
});

env.addFilter('fmt_date', (value) => {
  if (!value) return '—';
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return String(value);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${String(d.getDate()).padStart(2, '0')} ${months[d.getMonth()]} ${d.getFullYear()}`;
  } catch {
    return String(value);
  }
});

env.addFilter('fmt_datetime', (value) => {
  if (!value) return '—';
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return String(value);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const hrs = String(d.getHours()).padStart(2, '0');
    const mins = String(d.getMinutes()).padStart(2, '0');
    return `${String(d.getDate()).padStart(2, '0')} ${months[d.getMonth()]}, ${hrs}:${mins}`;
  } catch {
    return String(value);
  }
});

env.addFilter('money', (val) => {
  try {
    return `${Number(val || 0).toLocaleString()} ₺`;
  } catch {
    return '—';
  }
});

env.addFilter('round', (val, decimals = 0) => {
  try {
    const factor = Math.pow(10, decimals);
    return Math.round(Number(val) * factor) / factor;
  } catch {
    return val;
  }
});

env.addFilter('format', (str, ...args) => {
  if (typeof str !== 'string') return String(str);
  let i = 0;
  return str.replace(/%([0-9]+)?([sdif%])/g, (m, width, type) => {
    if (type === '%') return '%';
    const val = args[i++];
    if (type === 'd' || type === 'i') {
      const num = parseInt(val, 10) || 0;
      return width ? String(num).padStart(parseInt(width, 10), '0') : String(num);
    }
    return String(val ?? '');
  });
});

// Helper for Flask url_for compatibility in templates
function urlFor(endpoint, params = {}) {
  if (endpoint === 'static') {
    return `/static/${params.filename || ''}`;
  }
  const routes = {
    'index': '/',
    'login': '/login',
    'register': '/register',
    'forgot_password_page': '/forgot-password',
    'reset_password_page': '/reset-password',
    'verify_email_page': '/verify-email',
    'dashboard': '/dashboard',
    'equipment_page': '/equipment',
    'maintenance_page': '/maintenance',
    'operational_data_page': '/operational-data',
    'prediction_page': '/prediction',
    'chatbot_page': '/chatbot',
    'reports_page': '/reports',
    'notifications_page': '/notifications',
    'profile_page': '/profile',
    'admin_page': '/admin',
    'fuel_page': '/fuel',
    'bookings_page': '/bookings',
    'api_auth_google_start': '/auth/google'
  };

  if (endpoint === 'equipment_details' && params.equipment_id) {
    return `/equipment/${params.equipment_id}`;
  }

  let base = routes[endpoint] || `/${endpoint}`;
  const queryKeys = Object.keys(params).filter(k => k !== 'filename' && k !== 'equipment_id');
  if (queryKeys.length > 0) {
    const qs = new URLSearchParams();
    for (const k of queryKeys) qs.set(k, params[k]);
    base += `?${qs.toString()}`;
  }
  return base;
}

function getActivePage(pathname) {
  if (pathname.startsWith('/equipment')) return 'equipment';
  if (pathname.startsWith('/dashboard')) return 'dashboard';
  if (pathname.startsWith('/maintenance')) return 'maintenance';
  if (pathname.startsWith('/operational-data')) return 'operational';
  if (pathname.startsWith('/prediction')) return 'prediction';
  if (pathname.startsWith('/chatbot')) return 'chatbot';
  if (pathname.startsWith('/reports')) return 'reports';
  if (pathname.startsWith('/notifications')) return 'notifications';
  if (pathname.startsWith('/profile')) return 'profile';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/fuel')) return 'fuel';
  if (pathname.startsWith('/bookings')) return 'bookings';
  return '';
}

// Global context middleware
app.use((req, res, next) => {
  // Demo mode auto-login for seamless navigation
  if (!req.session.user_id && !req.session.logged_out) {
    req.session.user_id = 1;
  }

  const userId = req.session.user_id;
  const user = userId ? db.getUser(userId) : null;
  const unreadCount = userId ? db.unreadNotifications(userId) : 0;

  const todayObj = {
    strftime: (formatStr) => {
      const d = new Date();
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
      return formatStr
        .replace('%A', days[d.getDay()])
        .replace('%d', String(d.getDate()).padStart(2, '0'))
        .replace('%B', months[d.getMonth()])
        .replace('%Y', String(d.getFullYear()));
    }
  };

  const templateContext = {
    APP_NAME: 'AgriCare',
    current_user: user,
    today: todayObj,
    demo_banner: true,
    unread_count: unreadCount,
    csrf_token: req.session.csrf_token || (req.session.csrf_token = 'csrf-token-' + Math.random().toString(36).substring(2)),
    active: getActivePage(req.path),
    email_simulated: true,
    sms_simulated: true,
    google_enabled: Boolean(process.env.GOOGLE_CLIENT_ID),
    none: null,
    request: {
      path: req.path,
      method: req.method,
      args: {
        get: (key, fallback = null) => {
          const val = req.query[key];
          return (val !== undefined && val !== '') ? val : fallback;
        }
      },
      query: req.query
    },
    url_for: urlFor
  };

  res.locals = { ...res.locals, ...templateContext };
  next();
});

// Auth protection middleware
function requireLogin(req, res, next) {
  if (!req.session.user_id) {
    return res.redirect(`/login?next=${encodeURIComponent(req.originalUrl)}`);
  }
  next();
}

function requireApiLogin(req, res, next) {
  if (!req.session.user_id) {
    return res.status(401).json({ error: 'Authentication required. Please log in.' });
  }
  next();
}

// -------------------------------------------------------------
//  Google OAuth 2.0 / OpenID Connect Routes
// -------------------------------------------------------------

app.get('/auth/google', (req, res) => {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const redirectUri = process.env.GOOGLE_REDIRECT_URI || `${req.protocol}://${req.get('host')}/auth/google/callback`;

  if (!clientId) {
    return res.render('login.html', {
      error: null,
      google_enabled: true,
      google_error: "Google OAuth 2.0 requires GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI to be configured in your environment."
    });
  }

  const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${encodeURIComponent(clientId)}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=openid%20email%20profile&access_type=offline&prompt=consent`;
  res.redirect(authUrl);
});

app.get('/auth/google/callback', async (req, res) => {
  const { code, error } = req.query;
  if (error || !code) {
    return res.redirect(`/login?google_error=${encodeURIComponent(error || "Google authorization was cancelled.")}`);
  }

  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  const redirectUri = process.env.GOOGLE_REDIRECT_URI || `${req.protocol}://${req.get('host')}/auth/google/callback`;

  try {
    const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: "authorization_code"
      })
    });

    const tokenData = await tokenRes.json();
    if (!tokenData.access_token) {
      throw new Error(tokenData.error_description || "Failed to exchange authorization code for Google token.");
    }

    const userRes = await fetch("https://www.googleapis.com/oauth2/v2/userinfo", {
      headers: { Authorization: `Bearer ${tokenData.access_token}` }
    });
    const profile = await userRes.json();

    let user = db.getUserByEmail(profile.email);
    if (!user) {
      user = db.createUser({
        name: profile.name || "Google Farmer",
        email: profile.email,
        phone: "",
        password: Math.random().toString(36).slice(-10),
        role: "Farmer"
      });
    }

    req.session.user_id = user.user_id;
    delete req.session.logged_out;
    res.redirect('/dashboard');
  } catch (err) {
    console.error("[Google OAuth] Callback Error:", err.message);
    res.redirect(`/login?google_error=${encodeURIComponent(err.message)}`);
  }
});

// -------------------------------------------------------------
//  Page Routes
// -------------------------------------------------------------

app.get('/', (req, res) => {
  if (req.session.user_id && !req.session.logged_out) {
    return res.redirect('/dashboard');
  }
  res.render('landing.html');
});

app.get('/login', (req, res) => {
  if (req.session.user_id && !req.session.logged_out) {
    return res.redirect('/dashboard');
  }
  res.render('login.html', {
    error: null,
    google_enabled: Boolean(process.env.GOOGLE_CLIENT_ID),
    google_error: req.query.google_error || null
  });
});

app.post('/login', (req, res) => {
  const { email, identifier, password } = req.body;
  const ident = email || identifier;
  const user = db.getUserByIdentifier(ident);

  if (user && bcrypt.compareSync(password, user.password_hash)) {
    req.session.user_id = user.user_id;
    delete req.session.logged_out;
    return res.redirect('/dashboard');
  }

  res.status(401).render('login.html', {
    error: 'Invalid email/phone or password. (Demo credentials: farmer@demo.com / demo1234)',
    google_enabled: Boolean(process.env.GOOGLE_CLIENT_ID),
    google_error: null
  });
});

app.get('/register', (req, res) => {
  if (req.session.user_id && !req.session.logged_out) {
    return res.redirect('/dashboard');
  }
  res.render('register.html', { error: null });
});

app.post('/register', (req, res) => {
  const { name, email, phone, password, confirm_password, role } = req.body;
  if (!email || !password) {
    return res.status(400).render('register.html', { error: 'Email and password are required.' });
  }
  if (password !== confirm_password) {
    return res.status(400).render('register.html', { error: 'Passwords do not match.' });
  }

  const existing = db.getUserByEmail(email);
  if (existing) {
    return res.status(400).render('register.html', { error: 'An account with this email already exists.' });
  }

  const user = db.createUser({ name: name || 'Farmer', email, phone, password, role: role || 'Farmer' });
  req.session.user_id = user.user_id;
  delete req.session.logged_out;
  res.redirect('/dashboard');
});

app.get('/forgot-password', (req, res) => {
  res.render('forgot_password.html');
});

app.get('/reset-password', (req, res) => {
  const token = req.query.token || 'demo-token';
  res.render('reset_password.html', { token });
});

app.get('/verify-email', (req, res) => {
  const token = req.query.token || '';
  res.render('verify_email.html', { token });
});

app.get('/dashboard', requireLogin, (req, res) => {
  const data = db.dashboard(req.session.user_id);
  res.render('dashboard.html', { data });
});

app.get('/equipment', requireLogin, (req, res) => {
  const equipment = db.listEquipment(req.session.user_id);
  res.render('equipment.html', { equipment });
});

app.get('/equipment/:id', requireLogin, (req, res) => {
  const eid = Number(req.params.id);
  const equip = db.getEquipment(req.session.user_id, eid);
  if (!equip) {
    return res.status(404).render('404.html');
  }
  const maintenance = db.listMaintenance(req.session.user_id, eid);
  const predictions = db.listPredictions(req.session.user_id, eid);
  const latestPrediction = db.latestPrediction(req.session.user_id, eid);
  const latestOperational = db.latestOperational(req.session.user_id, eid);

  res.render('equipment_details.html', {
    equipment: equip,
    maintenance,
    predictions,
    latest_prediction: latestPrediction,
    latest_operational: latestOperational
  });
});

app.get('/maintenance', requireLogin, (req, res) => {
  const equipment = db.listEquipment(req.session.user_id);
  const maintenance = db.listMaintenance(req.session.user_id);
  res.render('maintenance.html', { equipment, maintenance });
});

app.get('/operational-data', requireLogin, (req, res) => {
  const equipment = db.listEquipment(req.session.user_id);
  res.render('operational_data.html', { equipment });
});

app.get('/prediction', requireLogin, (req, res) => {
  const equipment = db.listEquipment(req.session.user_id);
  const predictions = db.listPredictions(req.session.user_id);
  res.render('prediction.html', {
    equipment,
    predictions,
    model_status: mlService.modelStatus(),
    model_info: mlService.infoText(),
    metrics: mlService.getMetrics()
  });
});

app.get('/fuel', requireLogin, (req, res) => {
  const equipment = db.listEquipment(req.session.user_id);
  const records = db.listFuelRecords(req.session.user_id);
  const summary = db.getFuelSummary(req.session.user_id);
  res.render('fuel.html', { equipment, records, summary });
});

app.get('/bookings', requireLogin, (req, res) => {
  const equipment = db.listEquipment(req.session.user_id);
  const bookings = db.listBookings(req.session.user_id);
  const stats = {
    total: bookings.length,
    confirmed: bookings.filter(b => b.status === "Confirmed").length,
    completed: bookings.filter(b => b.status === "Completed").length,
    cancelled: bookings.filter(b => b.status === "Cancelled").length
  };
  res.render('bookings.html', { equipment, bookings, stats });
});

app.get('/chatbot', requireLogin, (req, res) => {
  const uid = req.session.user_id;
  const equipment = db.listEquipment(uid);
  const conversations = db.listConversations(uid);
  let active = req.query.c ? Number(req.query.c) : null;

  if (active) {
    const conv = db.getConversation(uid, active);
    if (!conv) active = null;
  }
  if (!active && conversations.length > 0) {
    active = conversations[0].conversation_id;
  }

  const messages = active ? db.listMessages(active) : [];

  res.render('chatbot.html', {
    equipment,
    conversations,
    active_conversation: active,
    messages,
    quick_prompts: chatbotService.QUICK_PROMPTS,
    disclaimer: chatbotService.DISCLAIMER
  });
});

app.get('/reports', requireLogin, (req, res) => {
  const equipment = db.listEquipment(req.session.user_id);
  res.render('reports.html', { equipment });
});

app.get('/notifications', requireLogin, (req, res) => {
  const notifications = db.listNotifications(req.session.user_id);
  res.render('notifications.html', { notifications });
});

app.get('/profile', requireLogin, (req, res) => {
  const uid = req.session.user_id;
  const profile = db.getProfile(uid) || {};
  const notif_prefs = db.getNotificationPrefs(uid);
  res.render('profile.html', {
    profile,
    notif_prefs,
    prefs: {}
  });
});

app.get('/admin', requireLogin, (req, res) => {
  const profile = db.getProfile(req.session.user_id) || {};
  if (!profile.is_admin) {
    return res.status(403).send("Admin access required.");
  }
  res.render('admin.html');
});

// -------------------------------------------------------------
//  API Routes
// -------------------------------------------------------------

// Auth APIs
app.post('/api/login', (req, res) => {
  const { email, identifier, password } = req.body;
  const ident = email || identifier;
  const user = db.getUserByIdentifier(ident);

  if (user && bcrypt.compareSync(password, user.password_hash)) {
    req.session.user_id = user.user_id;
    delete req.session.logged_out;
    return res.json({ redirect: '/dashboard', user: { name: user.name, email: user.email } });
  }

  return res.status(401).json({
    error: 'Invalid credentials. For demo mode, use farmer@demo.com with password demo1234.'
  });
});

app.post('/api/register', (req, res) => {
  const { name, email, phone, password, confirm_password, role } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required.' });
  }
  if (password !== confirm_password) {
    return res.status(400).json({ error: 'Passwords do not match.' });
  }
  if (db.getUserByEmail(email)) {
    return res.status(400).json({ error: 'An account with this email already exists.' });
  }

  const user = db.createUser({ name: name || 'Farmer', email, phone, password, role: role || 'Farmer' });
  req.session.user_id = user.user_id;
  delete req.session.logged_out;
  res.json({ redirect: '/dashboard' });
});

app.post('/api/logout', (req, res) => {
  req.session.logged_out = true;
  req.session.user_id = null;
  res.json({ redirect: '/login' });
});

app.post('/api/forgot-password', (req, res) => {
  res.json({ success: true, message: 'Password reset link sent (simulated in demo mode).' });
});

app.post('/api/reset-password', (req, res) => {
  res.json({ success: true, message: 'Password updated successfully. You can now log in.' });
});

app.post('/api/verify-email', (req, res) => {
  if (req.session.user_id) {
    db.updateProfile(req.session.user_id, { email_verified: true });
  }
  res.json({ success: true, message: 'Email address verified successfully.' });
});

app.post('/api/resend-verification', (req, res) => {
  res.json({ success: true, message: 'Verification link resent (simulated in demo mode).' });
});

app.post('/api/phone/send-otp', (req, res) => {
  res.json({ success: true, message: 'Verification OTP sent to phone (demo: 123456).' });
});

app.post('/api/phone/verify-otp', (req, res) => {
  if (req.session.user_id) {
    db.updateProfile(req.session.user_id, { phone_verified: true });
  }
  res.json({ success: true, message: 'Phone number verified successfully.' });
});

// Dashboard API
app.get('/api/dashboard', requireApiLogin, (req, res) => {
  const data = db.dashboard(req.session.user_id);
  res.json(data);
});

// Equipment APIs
app.get('/api/equipment', requireApiLogin, (req, res) => {
  const list = db.listEquipment(req.session.user_id);
  res.json(list);
});

app.post('/api/equipment', requireApiLogin, (req, res) => {
  const row = db.createEquipment(req.session.user_id, req.body);
  res.json(row);
});

app.get('/api/equipment/:id', requireApiLogin, (req, res) => {
  const item = db.getEquipment(req.session.user_id, req.params.id);
  if (!item) return res.status(404).json({ error: 'Equipment not found' });
  res.json(item);
});

app.put('/api/equipment/:id', requireApiLogin, (req, res) => {
  const ok = db.updateEquipment(req.session.user_id, req.params.id, req.body);
  if (!ok) return res.status(404).json({ error: 'Equipment not found' });
  res.json({ success: true });
});

app.delete('/api/equipment/:id', requireApiLogin, (req, res) => {
  db.deleteEquipment(req.session.user_id, req.params.id);
  res.json({ success: true });
});

// Maintenance & Service History APIs
app.get('/api/maintenance', requireApiLogin, (req, res) => {
  const eqId = req.query.equipment_id ? Number(req.query.equipment_id) : null;
  const list = db.listMaintenance(req.session.user_id, eqId);
  res.json(list);
});

app.post('/api/maintenance', requireApiLogin, (req, res) => {
  const row = db.createMaintenance(req.session.user_id, req.body);
  res.json(row);
});

app.put('/api/maintenance/:id', requireApiLogin, (req, res) => {
  const ok = db.updateMaintenance(req.session.user_id, req.params.id, req.body);
  if (!ok) return res.status(404).json({ error: 'Record not found' });
  res.json({ success: true });
});

app.delete('/api/maintenance/:id', requireApiLogin, (req, res) => {
  db.deleteMaintenance(req.session.user_id, req.params.id);
  res.json({ success: true });
});

app.get('/api/service-history', requireApiLogin, (req, res) => {
  const eqId = req.query.equipment_id ? Number(req.query.equipment_id) : null;
  res.json(db.listServiceHistory(req.session.user_id, eqId));
});

// Fuel Tracking APIs
app.get('/api/fuel', requireApiLogin, (req, res) => {
  const eqId = req.query.equipment_id ? Number(req.query.equipment_id) : null;
  res.json(db.listFuelRecords(req.session.user_id, eqId));
});

app.post('/api/fuel', requireApiLogin, (req, res) => {
  const record = db.addFuelRecord(req.session.user_id, req.body);
  res.json(record);
});

// Equipment Bookings APIs
app.get('/api/bookings', requireApiLogin, (req, res) => {
  const eqId = req.query.equipment_id ? Number(req.query.equipment_id) : null;
  res.json(db.listBookings(req.session.user_id, eqId));
});

app.post('/api/bookings', requireApiLogin, (req, res) => {
  try {
    const row = db.createBooking(req.session.user_id, req.body);
    res.json(row);
  } catch (err) {
    res.status(409).json({ error: err.message });
  }
});

app.post('/api/bookings/:id/cancel', requireApiLogin, (req, res) => {
  const ok = db.cancelBooking(req.session.user_id, req.params.id);
  res.json({ success: ok });
});

// Operational Data APIs
app.get('/api/operational-data', requireApiLogin, (req, res) => {
  const eqId = req.query.equipment_id ? Number(req.query.equipment_id) : null;
  const limit = req.query.limit ? Number(req.query.limit) : 50;
  const list = db.listOperational(req.session.user_id, eqId, limit);
  res.json(list);
});

app.post('/api/operational-data', requireApiLogin, (req, res) => {
  const row = db.createOperational(req.session.user_id, req.body);
  res.json(row);
});

app.post('/api/upload-csv', requireApiLogin, upload.single('csv'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No CSV file provided.' });
  }
  const content = req.file.buffer.toString('utf-8');
  const lines = content.split(/\r?\n/).filter(l => l.trim().length > 0);
  if (lines.length < 2) {
    return res.status(400).json({ error: 'CSV file is empty or missing headers.' });
  }

  const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
  let count = 0;
  const eqId = Number(req.body.equipment_id) || 1;

  for (let i = 1; i < lines.length; i++) {
    const vals = lines[i].split(',').map(v => v.trim());
    if (vals.length < headers.length) continue;
    const row = { equipment_id: eqId, source: 'csv' };
    headers.forEach((h, idx) => {
      row[h] = vals[idx];
    });
    db.createOperational(req.session.user_id, row);
    count++;
  }

  res.json({ success: true, count, message: `Successfully loaded ${count} readings.` });
});

// Predictive Maintenance APIs
app.get('/api/model-status', (req, res) => {
  res.json(mlService.modelStatus());
});

app.get('/api/predictions', requireApiLogin, (req, res) => {
  const eqId = req.query.equipment_id ? Number(req.query.equipment_id) : null;
  const list = db.listPredictions(req.session.user_id, eqId);
  res.json(list);
});

app.post('/api/predict', requireApiLogin, (req, res) => {
  const eqId = req.body.equipment_id;
  if (!eqId) {
    return res.status(400).json({ error: 'Please select an equipment to analyze.' });
  }

  const result = mlService.analyze(req.body);

  const predRecord = db.insertPrediction(req.session.user_id, eqId, {
    condition: result.condition,
    result: result.result,
    risk_level: result.risk_level,
    probability: result.risk_percentage || result.probability,
    recommendation: result.recommendations || result.recommendation,
    explanation: result.explanation,
    is_demo: 1
  });

  // If high risk, trigger notification and alert
  if (result.risk_level === 'High') {
    const eq = db.getEquipment(req.session.user_id, eqId);
    const eqName = eq ? eq.equipment_name : `Equipment #${eqId}`;
    db.createNotification(
      req.session.user_id,
      `High Risk Detected: ${eqName}`,
      `Anomaly detected: ${result.explanation.slice(0, 100)}`,
      'risk'
    );
    db.createAlert({
      userId: req.session.user_id,
      equipmentId: eqId,
      equipmentName: eqName,
      eventType: 'Prediction High Risk',
      title: `High Risk Detected on ${eqName}`,
      message: result.explanation,
      severity: 'high'
    });
  }

  res.json({
    ...result,
    prediction_id: predRecord.prediction_id
  });
});

// Chatbot APIs
app.get('/api/chat/conversations', requireApiLogin, (req, res) => {
  const list = db.listConversations(req.session.user_id);
  res.json(list);
});

app.get('/api/chat/conversations/:id/messages', requireApiLogin, (req, res) => {
  const msgs = db.listMessages(req.params.id);
  res.json(msgs);
});

app.delete('/api/chat/conversations/:id', requireApiLogin, (req, res) => {
  db.deleteConversation(req.session.user_id, req.params.id);
  res.json({ success: true });
});

app.post('/api/chat/clear', requireApiLogin, (req, res) => {
  const convId = req.body.conversation_id;
  if (convId) db.clearMessages(convId);
  res.json({ success: true });
});

app.post('/api/chat', requireApiLogin, async (req, res) => {
  const { message, equipment_id, conversation_id } = req.body;
  if (!message || !message.trim()) {
    return res.status(400).json({ error: 'Message cannot be empty.' });
  }

  let convId = conversation_id ? Number(conversation_id) : null;
  if (!convId) {
    const conv = db.createConversation(req.session.user_id, message.slice(0, 30));
    convId = conv.conversation_id;
  }

  // Save user message
  db.addMessage(convId, req.session.user_id, 'user', message, equipment_id);

  // Retrieve equipment if chosen
  const eq = equipment_id ? db.getEquipment(req.session.user_id, equipment_id) : null;
  const userEquip = db.listEquipment(req.session.user_id);
  const pastMsgs = db.listMessages(convId);

  const botReply = await chatbotService.answerQuestion({
    message,
    equipment: eq,
    pastMessages: pastMsgs,
    userEquipment: userEquip
  });

  // Save bot message
  const assistantMsg = db.addMessage(convId, req.session.user_id, 'assistant', botReply.answer, equipment_id);

  res.json({
    conversation_id: convId,
    answer: botReply.answer,
    disclaimer: botReply.disclaimer,
    message: assistantMsg
  });
});

// Reports APIs
app.get('/api/reports', requireApiLogin, (req, res) => {
  const { type = 'equipment', equipment_id, from, to, risk } = req.query;
  const uid = req.session.user_id;

  let rows = [];

  if (type === 'equipment') {
    let eqList = db.listEquipment(uid);
    if (equipment_id) eqList = eqList.filter(e => e.equipment_id === Number(equipment_id));
    if (risk) eqList = eqList.filter(e => e.risk_level.toLowerCase() === risk.toLowerCase());
    rows = eqList.map(e => ({
      "Equipment Name": e.equipment_name,
      "Type": e.equipment_type,
      "Brand / Model": `${e.brand || ''} ${e.model || ''}`.trim() || '—',
      "Operating Hours": `${e.operating_hours} h`,
      "Status": e.status,
      "Risk Level": e.risk_level,
      "Location": e.location || '—',
      "Next Service": e.next_service_date || '—'
    }));
  } else if (type === 'maintenance') {
    let mList = db.listMaintenance(uid, equipment_id);
    if (from) mList = mList.filter(m => (m.service_date || '') >= from);
    if (to) mList = mList.filter(m => (m.service_date || '') <= to);
    rows = mList.map(m => ({
      "Date": m.service_date,
      "Equipment": m.equipment_name,
      "Service Type": m.service_type,
      "Cost": `${m.cost} ₺`,
      "Technician": m.technician || 'Certified Tech',
      "Action Taken": m.action_taken || m.problem_description,
      "Status": m.status
    }));
  } else if (type === 'prediction') {
    let pList = db.listPredictions(uid, equipment_id);
    if (risk) pList = pList.filter(p => p.risk_level.toLowerCase() === risk.toLowerCase());
    rows = pList.map(p => ({
      "Date": p.prediction_date,
      "Equipment": p.equipment_name,
      "AI Result": p.result || (p.risk_level === 'High' ? 'HIGH RISK OF BREAKDOWN' : (p.risk_level === 'Medium' ? 'SERVICE REQUIRED' : 'GOOD CONDITION')),
      "Risk Level": p.risk_level,
      "Risk %": `${p.probability}%`,
      "Recommendation": p.recommendation
    }));
  } else if (type === 'risk') {
    let eqList = db.listEquipment(uid);
    if (risk) eqList = eqList.filter(e => e.risk_level.toLowerCase() === risk.toLowerCase());
    rows = eqList.map(e => ({
      "Equipment": e.equipment_name,
      "Type": e.equipment_type,
      "Risk Level": e.risk_level,
      "Status": e.status,
      "Hours": e.operating_hours
    }));
  }

  res.json({ rows });
});

// Notifications & Alerts APIs
app.get('/api/notifications', requireApiLogin, (req, res) => {
  res.json(db.listNotifications(req.session.user_id));
});

app.post('/api/notifications/read', requireApiLogin, (req, res) => {
  db.markNotificationsRead(req.session.user_id);
  res.json({ success: true });
});

app.get('/api/notifications/poll', requireApiLogin, (req, res) => {
  const unread = db.unreadNotifications(req.session.user_id);
  const notifs = db.listNotifications(req.session.user_id).slice(0, 5);
  res.json({ unread_count: unread, notifications: notifs });
});

app.get('/api/alerts', requireApiLogin, (req, res) => {
  res.json({ alerts: db.listAlerts(req.session.user_id) });
});

app.post('/api/alerts/test', requireApiLogin, (req, res) => {
  const alert = db.createAlert({
    userId: req.session.user_id,
    title: 'Test Maintenance Notification',
    message: 'Test alert sent successfully to verify email/SMS delivery simulation.',
    severity: 'low'
  });
  res.json({ success: true, alert });
});

// Profile & Preferences APIs
app.get('/api/profile', requireApiLogin, (req, res) => {
  res.json(db.getProfile(req.session.user_id));
});

app.put('/api/profile', requireApiLogin, (req, res) => {
  db.updateProfile(req.session.user_id, req.body);
  res.json({ success: true, profile: db.getProfile(req.session.user_id) });
});

app.post('/api/change-password', requireApiLogin, (req, res) => {
  const { current_password, new_password } = req.body;
  const user = db.getUser(req.session.user_id);
  if (user && bcrypt.compareSync(current_password, user.password_hash)) {
    user.password_hash = bcrypt.hashSync(new_password, 10);
    return res.json({ success: true, message: 'Password changed successfully.' });
  }
  res.status(400).json({ error: 'Incorrect current password.' });
});

app.get('/api/notification-preferences', requireApiLogin, (req, res) => {
  res.json(db.getNotificationPrefs(req.session.user_id));
});

app.put('/api/notification-preferences', requireApiLogin, (req, res) => {
  const updated = db.updateNotificationPrefs(req.session.user_id, req.body);
  res.json({ success: true, preferences: updated });
});

app.put('/api/preferences', requireApiLogin, (req, res) => {
  res.json({ success: true });
});

// Admin API
app.get('/api/admin/overview', requireApiLogin, (req, res) => {
  const profile = db.getProfile(req.session.user_id) || {};
  if (!profile.is_admin) {
    return res.status(403).json({ error: 'Admin access required.' });
  }
  res.json({
    stats: db.adminStats(),
    users: [
      {
        name: 'Demo Farmer',
        email: 'farmer@demo.com',
        phone: '+90 532 000 00 00',
        email_verified: true,
        phone_verified: false,
        is_admin: true,
        created_at: new Date(Date.now() - 400 * 86400000).toISOString()
      }
    ],
    alerts: db.listAlerts(null, 15)
  });
});

// 404 & 500 error handlers
app.use((req, res) => {
  res.status(404).render('404.html');
});

app.use((err, req, res, next) => {
  console.error("Unhandled error:", err);
  res.status(500).render('500.html');
});

// Start Server and attempt MySQL initialization
app.listen(PORT, '0.0.0.0', () => {
  console.log(`[AgriCare] Node.js server running on http://0.0.0.0:${PORT}`);
  initMySQL().catch(err => console.warn("[MySQL] Init skipped:", err.message));
});
