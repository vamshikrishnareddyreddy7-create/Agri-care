/* AgriCare — API service layer.
   Every network call the frontend makes goes through these functions, so the
   Flask backend can be connected / swapped in one place. */
const API = (() => {
  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  async function request(method, url, body) {
    const opts = { method, headers: { "X-CSRF-Token": csrfToken() } };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    let data = null;
    try { data = await res.json(); } catch (_) { /* empty body */ }
    if (!res.ok) {
      const msg = (data && data.error) || `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  function upload(url, formData) {
    return fetch(url, { method: "POST", body: formData }).then(async (res) => {
      let data = null;
      try { data = await res.json(); } catch (_) { /* ignore */ }
      if (!res.ok) throw new Error((data && data.error) || `Request failed (${res.status})`);
      return data;
    });
  }

  return {
    // Auth
    login: (identifier, password) => request("POST", "/api/login", { email: identifier, password }),
    register: (payload) => request("POST", "/api/register", payload),
    logout: () => request("POST", "/api/logout"),
    forgotPassword: (email) => request("POST", "/api/forgot-password", { email }),
    resetPassword: (token, password, confirm_password) =>
      request("POST", "/api/reset-password", { token, password, confirm_password }),
    verifyEmail: (token) => request("POST", "/api/verify-email", { token }),
    resendVerification: () => request("POST", "/api/resend-verification"),

    // Phone OTP
    sendOtp: (phone) => request("POST", "/api/phone/send-otp", { phone }),
    verifyOtp: (phone, code) => request("POST", "/api/phone/verify-otp", { phone, code }),

    // Dashboard
    getDashboard: () => request("GET", "/api/dashboard"),

    // Equipment
    getEquipment: () => request("GET", "/api/equipment"),
    createEquipment: (data) => request("POST", "/api/equipment", data),
    updateEquipment: (id, data) => request("PUT", `/api/equipment/${id}`, data),
    deleteEquipment: (id) => request("DELETE", `/api/equipment/${id}`),
    getEquipmentDetail: (id) => request("GET", `/api/equipment/${id}`),

    // Maintenance
    getMaintenance: (equipmentId) =>
      request("GET", `/api/maintenance${equipmentId ? `?equipment_id=${equipmentId}` : ""}`),
    createMaintenance: (data) => request("POST", "/api/maintenance", data),
    updateMaintenance: (id, data) => request("PUT", `/api/maintenance/${id}`, data),
    deleteMaintenance: (id) => request("DELETE", `/api/maintenance/${id}`),

    // Operational data
    postOperationalData: (data) => request("POST", "/api/operational-data", data),
    uploadCsv: (formData) => upload("/api/upload-csv", formData),
    getOperationalData: (equipmentId, limit = 25) => {
      const p = new URLSearchParams();
      if (equipmentId) p.set("equipment_id", equipmentId);
      p.set("limit", limit);
      return request("GET", `/api/operational-data?${p.toString()}`);
    },

    // Predictions
    predict: (payload) => request("POST", "/api/predict", payload),
    getPredictions: (equipmentId) =>
      request("GET", `/api/predictions${equipmentId ? `?equipment_id=${equipmentId}` : ""}`),
    getModelStatus: () => request("GET", "/api/model-status"),

    // Chatbot
    chat: (message, equipmentId, language, conversationId) => request("POST", "/api/chat", { message, equipment_id: equipmentId, language, conversation_id: conversationId }),
    getConversations: (q) => request("GET", `/api/chat/conversations${q ? `?q=${encodeURIComponent(q)}` : ""}`),
    getConversationMessages: (id) => request("GET", `/api/chat/conversations/${id}/messages`),
    deleteConversation: (id) => request("DELETE", `/api/chat/conversations/${id}`),
    getChatHistory: () => request("GET", "/api/chat/history"),
    clearChat: () => request("POST", "/api/chat/clear"),

    // Reports
    getReports: (params) => {
      const qs = new URLSearchParams(params).toString();
      return request("GET", `/api/reports?${qs}`);
    },

    // Notifications
    getNotifications: () => request("GET", "/api/notifications"),
    markNotificationsRead: () => request("POST", "/api/notifications/read"),
    pollNotifications: (sinceId) => request("GET", `/api/notifications/poll?since_id=${sinceId || 0}`),
    getNotificationPrefs: () => request("GET", "/api/notification-preferences"),
    updateNotificationPrefs: (data) => request("PUT", "/api/notification-preferences", data),
    getAlerts: () => request("GET", "/api/alerts"),
    sendTestAlert: () => request("POST", "/api/alerts/test"),

    // Admin
    getAdminOverview: () => request("GET", "/api/admin/overview"),

    // Profile
    getProfile: () => request("GET", "/api/profile"),
    updateProfile: (data) => request("PUT", "/api/profile", data),
    changePassword: (data) => request("POST", "/api/change-password", data),
    updatePreferences: (data) => request("PUT", "/api/preferences", data),
  };
})();

/* Redirect helper used after login/registration. */
function redirectTo(url) { window.location.href = url; }