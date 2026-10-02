import bcrypt from 'bcryptjs';

const DEMO_PASSWORD = "demo1234";
const DEMO_PASSWORD_HASH = bcrypt.hashSync(DEMO_PASSWORD, 10);

function createInitialState() {
  const now = new Date();
  const daysAgo = (d) => new Date(now.getTime() - d * 24 * 60 * 60 * 1000);
  const daysAhead = (d) => new Date(now.getTime() + d * 24 * 60 * 60 * 1000);
  const formatDate = (date) => date.toISOString().slice(0, 10);

  const users = [
    {
      user_id: 1,
      name: "Demo Farmer",
      email: "farmer@demo.com",
      password_hash: DEMO_PASSWORD_HASH,
      phone: "+90 532 000 00 00",
      role: "Farmer",
      created_at: daysAgo(400)
    }
  ];

  const profiles = {
    1: {
      user_id: 1,
      name: "Demo Farmer",
      email: "farmer@demo.com",
      phone: "+90 532 000 00 00",
      email_verified: true,
      phone_verified: false,
      is_admin: true,
      farm_name: "Green Valley Farm",
      location: "Konya Plain, Sector 4"
    }
  };

  const notifPrefs = {
    1: {
      email_notifications: true,
      sms_notifications: false,
      alert_min_severity: "medium"
    }
  };

  const equipment = [
    {
      equipment_id: 1,
      user_id: 1,
      equipment_name: "Tractor TR001",
      equipment_type: "Tractor",
      brand: "Tümosan",
      model: "81.110",
      year: 2024,
      registration_number: "TR-2024-001",
      purchase_date: "2024-03-15",
      operating_hours: 1240.0,
      fuel_consumption: 11.4,
      usage_frequency: "Daily",
      current_condition: "Healthy",
      status: "Healthy",
      location: "Main Shed A",
      created_at: daysAgo(500)
    },
    {
      equipment_id: 2,
      user_id: 1,
      equipment_name: "Tractor TR002",
      equipment_type: "Tractor",
      brand: "John Deere",
      model: "5055E",
      year: 2023,
      registration_number: "JD-2023-114",
      purchase_date: "2023-05-02",
      operating_hours: 2860.0,
      fuel_consumption: 10.2,
      usage_frequency: "Daily",
      current_condition: "Maintenance Due",
      status: "Maintenance Due",
      location: "North Field Depot",
      created_at: daysAgo(600)
    },
    {
      equipment_id: 3,
      user_id: 1,
      equipment_name: "Harvester HV001",
      equipment_type: "Harvester",
      brand: "Claas",
      model: "Lexion 5300",
      year: 2021,
      registration_number: "CL-2021-032",
      purchase_date: "2021-08-20",
      operating_hours: 1980.0,
      fuel_consumption: 14.8,
      usage_frequency: "Seasonal",
      current_condition: "Healthy",
      status: "Healthy",
      location: "Harvester Bay 2",
      created_at: daysAgo(700)
    },
    {
      equipment_id: 4,
      user_id: 1,
      equipment_name: "Irrigation Pump IP001",
      equipment_type: "Water pump",
      brand: "KSB",
      model: "Etanorm 80-160",
      year: 2022,
      registration_number: "KS-2022-007",
      purchase_date: "2022-04-11",
      operating_hours: 3420.0,
      fuel_consumption: 7.2,
      usage_frequency: "Weekly",
      current_condition: "Healthy",
      status: "Healthy",
      location: "Pump House Canal 3",
      created_at: daysAgo(640)
    },
    {
      equipment_id: 5,
      user_id: 1,
      equipment_name: "Sprayer SP001",
      equipment_type: "Sprayer",
      brand: "Hardi",
      model: "Commander 2800",
      year: 2022,
      registration_number: "HD-2022-019",
      purchase_date: "2022-06-05",
      operating_hours: 1505.0,
      fuel_consumption: 11.0,
      usage_frequency: "Seasonal",
      current_condition: "High Risk",
      status: "High Risk",
      location: "Chemical Shed",
      created_at: daysAgo(620)
    }
  ];

  const maintenance = [
    {
      maintenance_id: 1,
      equipment_id: 1,
      service_date: formatDate(daysAgo(115)),
      service_type: "Oil Change",
      problem_description: "Routine 500-hour service",
      action_taken: "Changed engine oil, oil filter and air filter",
      parts_replaced: "Oil filter, air filter, 10L engine oil",
      technician: "Ahmet Usta (Tümosan Authorized)",
      cost: 1850.00,
      next_service_date: formatDate(daysAhead(35)),
      status: "Completed",
      created_at: daysAgo(115)
    },
    {
      maintenance_id: 2,
      equipment_id: 1,
      service_date: formatDate(daysAgo(33)),
      service_type: "Regular Service",
      problem_description: "Pre-harvest inspection",
      action_taken: "Greased linkages, checked belts and tire pressure",
      parts_replaced: "Drive belt tensioner",
      technician: "Mehmet Demir",
      cost: 620.00,
      next_service_date: formatDate(daysAhead(92)),
      status: "Completed",
      created_at: daysAgo(33)
    },
    {
      maintenance_id: 3,
      equipment_id: 2,
      service_date: formatDate(daysAgo(168)),
      service_type: "Regular Service",
      problem_description: "1500-hour service overdue check",
      action_taken: "Full service performed, hydraulic fluid topped up",
      parts_replaced: "Fuel filter, hydraulic filter",
      technician: "John Deere Service Konya",
      cost: 2400.00,
      next_service_date: formatDate(now),
      status: "Scheduled",
      created_at: daysAgo(168)
    },
    {
      maintenance_id: 4,
      equipment_id: 2,
      service_date: formatDate(daysAgo(295)),
      service_type: "Hydraulic Repair",
      problem_description: "Weak lift arm response",
      action_taken: "Replaced hydraulic control valve seal kit",
      parts_replaced: "Seal kit, hydraulic oil 4L",
      technician: "Hasan Çelik",
      cost: 1350.00,
      next_service_date: formatDate(daysAgo(60)),
      status: "Completed",
      created_at: daysAgo(295)
    },
    {
      maintenance_id: 5,
      equipment_id: 3,
      service_date: formatDate(daysAgo(88)),
      service_type: "Transmission Service",
      problem_description: "Gearbox oil change per schedule",
      action_taken: "Changed gearbox oil and checked clutch",
      parts_replaced: "Gearbox oil 12L",
      technician: "Claas Regional Specialist",
      cost: 2100.00,
      next_service_date: formatDate(daysAhead(190)),
      status: "Completed",
      created_at: daysAgo(88)
    },
    {
      maintenance_id: 6,
      equipment_id: 4,
      service_date: formatDate(daysAgo(132)),
      service_type: "Electrical Repair",
      problem_description: "Motor would not start",
      action_taken: "Replaced starter relay and cleaned battery terminals",
      parts_replaced: "Starter relay",
      technician: "Ömer Elektrik",
      cost: 480.00,
      next_service_date: formatDate(daysAhead(230)),
      status: "Completed",
      created_at: daysAgo(132)
    },
    {
      maintenance_id: 7,
      equipment_id: 5,
      service_date: formatDate(daysAgo(208)),
      service_type: "Cooling System",
      problem_description: "Coolant leak noticed near radiator",
      action_taken: "Replaced radiator hose and refilled coolant",
      parts_replaced: "Radiator hose, coolant 6L",
      technician: "Ali Yıldız",
      cost: 980.00,
      next_service_date: formatDate(daysAgo(40)),
      status: "Completed",
      created_at: daysAgo(208)
    },
    {
      maintenance_id: 8,
      equipment_id: 5,
      service_date: formatDate(daysAgo(47)),
      service_type: "Engine Repair",
      problem_description: "Rough idle and power loss",
      action_taken: "Cleaned injectors, replaced fuel filter",
      parts_replaced: "Fuel filter, injector seal",
      technician: "Ahmet Usta",
      cost: 3100.00,
      next_service_date: formatDate(daysAhead(75)),
      status: "Completed",
      created_at: daysAgo(47)
    }
  ];

  // Dedicated Service History records
  const serviceHistory = maintenance.map((m, idx) => ({
    history_id: idx + 1,
    equipment_id: m.equipment_id,
    service_date: m.service_date,
    service_type: m.service_type,
    parts_replaced: m.parts_replaced,
    cost: m.cost,
    technician: m.technician || "Authorized Technician",
    remarks: m.action_taken || m.problem_description
  }));

  // Fuel Tracking Records
  const fuelRecords = [
    { fuel_id: 1, equipment_id: 1, date: formatDate(daysAgo(2)), fuel_quantity: 65, fuel_cost: 2600, operating_hours: 1240, notes: "Full tank before spring plowing" },
    { fuel_id: 2, equipment_id: 1, date: formatDate(daysAgo(9)), fuel_quantity: 50, fuel_cost: 2000, operating_hours: 1215, notes: "Field transport" },
    { fuel_id: 3, equipment_id: 2, date: formatDate(daysAgo(3)), fuel_quantity: 75, fuel_cost: 3000, operating_hours: 2860, notes: "Deep tillage operation" },
    { fuel_id: 4, equipment_id: 2, date: formatDate(daysAgo(14)), fuel_quantity: 80, fuel_cost: 3200, operating_hours: 2810, notes: "Regular field work" },
    { fuel_id: 5, equipment_id: 3, date: formatDate(daysAgo(20)), fuel_quantity: 140, fuel_cost: 5600, operating_hours: 1980, notes: "Barley harvest batch 1" },
    { fuel_id: 6, equipment_id: 4, date: formatDate(daysAgo(5)), fuel_quantity: 40, fuel_cost: 1600, operating_hours: 3420, notes: "Night irrigation cycle" },
    { fuel_id: 7, equipment_id: 5, date: formatDate(daysAgo(12)), fuel_quantity: 45, fuel_cost: 1800, operating_hours: 1505, notes: "Herbicide spraying" }
  ];

  // Equipment Bookings / Rentals
  const bookings = [
    {
      booking_id: 1,
      equipment_id: 1,
      user_id: 1,
      booking_date: formatDate(daysAhead(2)),
      start_time: "08:00",
      end_time: "14:00",
      purpose: "Wheat planting in East Field",
      status: "Confirmed",
      created_at: daysAgo(1)
    },
    {
      booking_id: 2,
      equipment_id: 3,
      user_id: 1,
      booking_date: formatDate(daysAhead(5)),
      start_time: "07:00",
      end_time: "18:00",
      purpose: "Wheat field harvest contracted",
      status: "Confirmed",
      created_at: daysAgo(2)
    },
    {
      booking_id: 3,
      equipment_id: 2,
      user_id: 1,
      booking_date: formatDate(daysAgo(4)),
      start_time: "09:00",
      end_time: "17:00",
      purpose: "Rotavator soil prep",
      status: "Completed",
      created_at: daysAgo(6)
    }
  ];

  // Operational telematics
  const profilesMap = {
    1: { speed: 2100, torque: 420, load: 78, coolant: 88, oil: 96, oilp: 2.9, fuel: 11.4, vspeed: 7.5, batt: 13.8, trans: 8 },
    2: { speed: 1950, torque: 380, load: 66, coolant: 90, oil: 101, oilp: 2.6, fuel: 10.2, vspeed: 9.0, batt: 13.5, trans: 7 },
    3: { speed: 2250, torque: 480, load: 84, coolant: 92, oil: 104, oilp: 3.1, fuel: 14.8, vspeed: 5.0, batt: 14.0, trans: 9 },
    4: { speed: 2950, torque: 240, load: 88, coolant: 74, oil: 82, oilp: 3.4, fuel: 7.2, vspeed: 0.0, batt: 13.9, trans: 1 },
    5: { speed: 2050, torque: 410, load: 72, coolant: 96, oil: 112, oilp: 2.2, fuel: 11.0, vspeed: 6.0, batt: 12.6, trans: 8 }
  };

  const operational = [];
  let did = 1;
  for (const [eidStr, p] of Object.entries(profilesMap)) {
    const eid = Number(eidStr);
    const nRows = eid === 1 ? 25 : 10;
    for (let i = 0; i < nRows; i++) {
      const recDate = new Date(now.getTime() - (nRows - i) * 24 * 60 * 60 * 1000);
      const isHot = eid === 1 && i >= nRows - 4;
      const isHighRisk = eid === 5;
      operational.push({
        data_id: did++,
        equipment_id: eid,
        recorded_at: recDate.toISOString().slice(0, 16).replace('T', ' '),
        engine_speed: Math.round(p.speed + (Math.sin(i) * 60)),
        engine_torque: Math.round(p.torque + (Math.cos(i) * 25)),
        engine_load: Math.round((p.load + (Math.sin(i * 2) * 8)) * 10) / 10,
        coolant_temperature: isHot ? 104.5 : (isHighRisk ? 98.2 : Math.round((p.coolant + Math.sin(i) * 3) * 10) / 10),
        oil_temperature: isHot ? 116.8 : (isHighRisk ? 114.2 : Math.round((p.oil + Math.cos(i) * 4) * 10) / 10),
        oil_pressure: isHot ? 1.7 : (isHighRisk ? 1.85 : Math.round((p.oilp + Math.sin(i) * 0.2) * 100) / 100),
        fuel_rate: Math.round((p.fuel + Math.sin(i) * 1.5) * 10) / 10,
        vehicle_speed: Math.round((p.vspeed + Math.cos(i) * 1.5) * 10) / 10,
        battery_voltage: Math.round((p.batt + Math.sin(i) * 0.2) * 10) / 10,
        transmission: p.trans,
        operating_hours: Math.round((p.speed / 10 * (i + 1) / 8) * 10) / 10,
        source: eid === 1 && i < 8 ? "csv" : "manual"
      });
    }
  }

  const predictions = [
    {
      prediction_id: 1,
      equipment_id: 1,
      prediction_date: daysAgo(40).toISOString().slice(0, 16).replace('T', ' '),
      condition: "Normal",
      result: "GOOD CONDITION",
      risk_level: "Low",
      probability: 12.0,
      recommendation: "Continue routine maintenance. No abnormal patterns detected — follow scheduled oil change and service intervals.",
      explanation: "All operating parameters stayed within typical ranges for this tractor.",
      is_demo: 1
    },
    {
      prediction_id: 2,
      equipment_id: 2,
      prediction_date: daysAgo(60).toISOString().slice(0, 16).replace('T', ' '),
      condition: "Anomalous",
      result: "SERVICE REQUIRED",
      risk_level: "Medium",
      probability: 64.0,
      recommendation: "Service is overdue for this tractor. Book a full service soon and check hydraulic fluid levels and filters.",
      explanation: "Rising oil temperature combined with overdue service interval produced a medium-risk pattern.",
      is_demo: 1
    },
    {
      prediction_id: 3,
      equipment_id: 5,
      prediction_date: daysAgo(20).toISOString().slice(0, 16).replace('T', ' '),
      condition: "Anomalous",
      result: "HIGH RISK OF BREAKDOWN",
      risk_level: "High",
      probability: 92.0,
      recommendation: "Inspect cooling system, engine temperature and oil condition. High coolant and oil temperatures with low oil pressure indicate engine is running hot — have a technician check it before next use.",
      explanation: "Coolant temperature above 100°C, oil temperature above 110°C and oil pressure below 2.0 bar were detected together.",
      is_demo: 1
    }
  ];

  const notifications = [
    {
      notification_id: 1,
      user_id: 1,
      title: "Maintenance due for TR002",
      message: "The regular service for Tractor TR002 (John Deere 5055E) is due today.",
      notification_type: "maintenance",
      is_read: 0,
      created_at: new Date(now.getTime() - 5 * 60 * 60 * 1000).toISOString()
    },
    {
      notification_id: 2,
      user_id: 1,
      title: "High maintenance risk detected",
      message: "Sprayer SP001 is showing a high maintenance risk (92%). Immediate inspection advised.",
      notification_type: "risk",
      is_read: 0,
      created_at: daysAgo(1).toISOString()
    },
    {
      notification_id: 3,
      user_id: 1,
      title: "Booking confirmed for Tractor TR001",
      message: "Your booking for Tractor TR001 on " + formatDate(daysAhead(2)) + " has been confirmed.",
      notification_type: "booking",
      is_read: 0,
      created_at: daysAgo(1).toISOString()
    },
    {
      notification_id: 4,
      user_id: 1,
      title: "Service due in 50 operating hours",
      message: "Tractor TR001 is approaching its next oil change interval (50 h remaining).",
      notification_type: "maintenance",
      is_read: 1,
      created_at: daysAgo(2).toISOString()
    }
  ];

  const alerts = [
    {
      alert_id: 1,
      user_id: 1,
      equipment_id: 5,
      equipment_name: "Sprayer SP001",
      event_type: "Prediction High Risk",
      title: "Critical Overheating Risk on Sprayer SP001",
      message: "High coolant temp (>100°C) and low oil pressure detected during analysis.",
      severity: "high",
      email_status: "simulated",
      sms_status: "simulated",
      created_at: daysAgo(1).toISOString()
    }
  ];

  const conversations = [
    {
      conversation_id: 1,
      user_id: 1,
      title: "Tractor TR001 High Risk Inquiry",
      created_at: daysAgo(2),
      updated_at: daysAgo(2)
    }
  ];

  const messages = [
    {
      message_id: 1,
      conversation_id: 1,
      user_id: 1,
      role: "user",
      content: "Why is my tractor showing high maintenance risk?",
      equipment_id: 5,
      created_at: daysAgo(2)
    },
    {
      message_id: 2,
      conversation_id: 1,
      user_id: 1,
      role: "assistant",
      content: "The system detected an abnormal operating pattern: high coolant and oil temperatures combined with lower-than-normal oil pressure. Please check engine coolant levels, clean radiator fins, and check engine oil condition.",
      equipment_id: 5,
      created_at: daysAgo(2)
    }
  ];

  return {
    users,
    profiles,
    notifPrefs,
    equipment,
    maintenance,
    serviceHistory,
    fuelRecords,
    bookings,
    operational,
    predictions,
    notifications,
    alerts,
    conversations,
    messages,
    nextIds: {
      user: 2,
      equipment: 6,
      maintenance: 9,
      serviceHistory: 9,
      fuel: 8,
      booking: 4,
      operational: did,
      prediction: 4,
      notification: 5,
      alert: 2,
      conversation: 2,
      message: 3
    }
  };
}

class InMemStore {
  constructor() {
    this.state = createInitialState();
  }

  // --- Auth & Users ---
  getUser(userId) {
    return this.state.users.find(u => u.user_id === Number(userId)) || null;
  }

  getUserByEmail(email) {
    if (!email) return null;
    return this.state.users.find(u => u.email.toLowerCase() === email.toLowerCase()) || null;
  }

  getUserByIdentifier(ident) {
    if (!ident) return null;
    const cleanIdent = String(ident).trim();
    const cleanDigits = cleanIdent.replace(/[^0-9]/g, '');
    return this.state.users.find(u => {
      if (u.email.toLowerCase() === cleanIdent.toLowerCase()) return true;
      if (cleanDigits && u.phone && u.phone.replace(/[^0-9]/g, '') === cleanDigits) return true;
      return false;
    }) || null;
  }

  createUser({ name, email, password, phone, role = "Farmer" }) {
    const uid = this.state.nextIds.user++;
    const hash = password ? bcrypt.hashSync(password, 10) : "";
    const user = {
      user_id: uid,
      name,
      email: email.toLowerCase(),
      password_hash: hash,
      phone: phone || "",
      role,
      created_at: new Date()
    };
    this.state.users.push(user);
    this.state.profiles[uid] = {
      user_id: uid,
      name,
      email: email.toLowerCase(),
      phone: phone || "",
      email_verified: true,
      phone_verified: false,
      is_admin: false,
      farm_name: "My Farm",
      location: ""
    };
    this.state.notifPrefs[uid] = {
      email_notifications: true,
      sms_notifications: false,
      alert_min_severity: "medium"
    };
    return user;
  }

  getProfile(userId) {
    const uid = Number(userId);
    let p = this.state.profiles[uid];
    if (!p) {
      const u = this.getUser(uid);
      if (u) {
        p = {
          user_id: uid,
          name: u.name,
          email: u.email,
          phone: u.phone || "",
          email_verified: true,
          phone_verified: false,
          is_admin: u.role === "Admin",
          farm_name: "Farm",
          location: ""
        };
        this.state.profiles[uid] = p;
      }
    }
    return p ? { ...p } : null;
  }

  updateProfile(userId, data) {
    const uid = Number(userId);
    if (!this.state.profiles[uid]) {
      this.getProfile(uid);
    }
    if (this.state.profiles[uid]) {
      Object.assign(this.state.profiles[uid], data);
      const u = this.getUser(uid);
      if (u) {
        if (data.name) u.name = data.name;
        if (data.email) u.email = data.email.toLowerCase();
        if (data.phone) u.phone = data.phone;
      }
      return true;
    }
    return false;
  }

  getNotificationPrefs(userId) {
    return this.state.notifPrefs[Number(userId)] || {
      email_notifications: true,
      sms_notifications: false,
      alert_min_severity: "medium"
    };
  }

  updateNotificationPrefs(userId, prefs) {
    const uid = Number(userId);
    this.state.notifPrefs[uid] = { ...this.getNotificationPrefs(uid), ...prefs };
    return this.state.notifPrefs[uid];
  }

  // --- Equipment ---
  listEquipment(userId) {
    const uid = Number(userId);
    return this.state.equipment
      .filter(e => e.user_id === uid)
      .map(e => {
        const pred = this.latestPrediction(uid, e.equipment_id);
        const maint = this.listMaintenance(uid, e.equipment_id);
        const currentYear = new Date().getFullYear();
        const age = e.year ? Math.max(0, currentYear - e.year) : 0;
        return {
          ...e,
          age,
          risk_level: pred ? pred.risk_level : (e.status === "High Risk" ? "High" : (e.status === "Maintenance Due" ? "Medium" : "Low")),
          risk_probability: pred ? pred.probability : null,
          last_service_date: maint.length > 0 ? maint[0].service_date : null,
          next_service_date: maint.length > 0 ? maint[0].next_service_date : null,
        };
      });
  }

  getEquipment(userId, equipmentId) {
    const uid = Number(userId);
    const eid = Number(equipmentId);
    const eq = this.state.equipment.find(e => e.user_id === uid && e.equipment_id === eid);
    if (!eq) return null;
    const pred = this.latestPrediction(uid, eid);
    const maint = this.listMaintenance(uid, eid);
    const currentYear = new Date().getFullYear();
    const age = eq.year ? Math.max(0, currentYear - eq.year) : 0;
    return {
      ...eq,
      age,
      risk_level: pred ? pred.risk_level : (eq.status === "High Risk" ? "High" : (eq.status === "Maintenance Due" ? "Medium" : "Low")),
      risk_probability: pred ? pred.probability : null,
      last_service_date: maint.length > 0 ? maint[0].service_date : null,
      next_service_date: maint.length > 0 ? maint[0].next_service_date : null,
    };
  }

  createEquipment(userId, data) {
    const eid = this.state.nextIds.equipment++;
    const currentYear = new Date().getFullYear();
    const year = data.year ? Number(data.year) : currentYear;
    const row = {
      equipment_id: eid,
      user_id: Number(userId),
      equipment_name: data.equipment_name || "New Machine",
      equipment_type: data.equipment_type || "Tractor",
      brand: data.brand || "",
      model: data.model || "",
      year: year,
      registration_number: data.registration_number || `EQ-${String(eid).padStart(3, '0')}`,
      purchase_date: data.purchase_date || new Date().toISOString().slice(0, 10),
      operating_hours: Number(data.operating_hours || 0),
      fuel_consumption: Number(data.fuel_consumption || 10.0),
      usage_frequency: data.usage_frequency || "Daily",
      current_condition: data.status || "Healthy",
      status: data.status || "Healthy",
      location: data.location || "Farm Yard",
      created_at: new Date()
    };
    this.state.equipment.push(row);
    return row;
  }

  updateEquipment(userId, equipmentId, data) {
    const eq = this.state.equipment.find(e => e.user_id === Number(userId) && e.equipment_id === Number(equipmentId));
    if (!eq) return false;
    Object.assign(eq, data);
    if (data.status) eq.current_condition = data.status;
    return true;
  }

  deleteEquipment(userId, equipmentId) {
    const uid = Number(userId);
    const eid = Number(equipmentId);
    this.state.equipment = this.state.equipment.filter(e => !(e.user_id === uid && e.equipment_id === eid));
    this.state.maintenance = this.state.maintenance.filter(m => m.equipment_id !== eid);
    this.state.serviceHistory = this.state.serviceHistory.filter(s => s.equipment_id !== eid);
    this.state.fuelRecords = this.state.fuelRecords.filter(f => f.equipment_id !== eid);
    this.state.bookings = this.state.bookings.filter(b => b.equipment_id !== eid);
    this.state.operational = this.state.operational.filter(o => o.equipment_id !== eid);
    this.state.predictions = this.state.predictions.filter(p => p.equipment_id !== eid);
    return true;
  }

  // --- Maintenance & Service History ---
  listMaintenance(userId, equipmentId = null) {
    const uid = Number(userId);
    const userEqIds = new Set(this.state.equipment.filter(e => e.user_id === uid).map(e => e.equipment_id));
    const eqMap = Object.fromEntries(this.state.equipment.map(e => [e.equipment_id, e]));

    return this.state.maintenance
      .filter(m => userEqIds.has(m.equipment_id) && (!equipmentId || m.equipment_id === Number(equipmentId)))
      .map(m => ({
        ...m,
        equipment_name: eqMap[m.equipment_id]?.equipment_name || `Equipment #${m.equipment_id}`
      }))
      .sort((a, b) => (b.service_date || '').localeCompare(a.service_date || ''));
  }

  createMaintenance(userId, data) {
    const mid = this.state.nextIds.maintenance++;
    const row = {
      maintenance_id: mid,
      equipment_id: Number(data.equipment_id),
      service_date: data.service_date || new Date().toISOString().slice(0, 10),
      service_type: data.service_type || "Regular Service",
      problem_description: data.problem_description || "",
      action_taken: data.action_taken || "",
      parts_replaced: data.parts_replaced || "",
      technician: data.technician || "Certified Field Technician",
      cost: parseFloat(data.cost || 0),
      next_service_date: data.next_service_date || "",
      status: data.status || "Completed",
      created_at: new Date()
    };
    this.state.maintenance.unshift(row);

    // Also record in service history
    this.addServiceHistory({
      equipment_id: row.equipment_id,
      service_date: row.service_date,
      service_type: row.service_type,
      parts_replaced: row.parts_replaced,
      cost: row.cost,
      technician: row.technician,
      remarks: row.action_taken || row.problem_description
    });

    // Update equipment status if maintenance is completed
    const eq = this.state.equipment.find(e => e.equipment_id === row.equipment_id);
    if (eq) {
      if (data.status === "Completed" && eq.status === "Maintenance Due") {
        eq.status = "Healthy";
        eq.current_condition = "Healthy";
      }
      if (row.next_service_date) {
        eq.next_service_date = row.next_service_date;
      }
    }
    return row;
  }

  updateMaintenance(userId, maintenanceId, data) {
    const row = this.state.maintenance.find(m => m.maintenance_id === Number(maintenanceId));
    if (!row) return false;
    Object.assign(row, data);
    return true;
  }

  deleteMaintenance(userId, maintenanceId) {
    const mid = Number(maintenanceId);
    this.state.maintenance = this.state.maintenance.filter(m => m.maintenance_id !== mid);
    return true;
  }

  listServiceHistory(userId, equipmentId = null) {
    const uid = Number(userId);
    const userEqIds = new Set(this.state.equipment.filter(e => e.user_id === uid).map(e => e.equipment_id));
    const eqMap = Object.fromEntries(this.state.equipment.map(e => [e.equipment_id, e]));

    return this.state.serviceHistory
      .filter(s => userEqIds.has(s.equipment_id) && (!equipmentId || s.equipment_id === Number(equipmentId)))
      .map(s => ({
        ...s,
        equipment_name: eqMap[s.equipment_id]?.equipment_name || `Equipment #${s.equipment_id}`
      }))
      .sort((a, b) => (b.service_date || '').localeCompare(a.service_date || ''));
  }

  addServiceHistory(data) {
    const hid = this.state.nextIds.serviceHistory++;
    const row = {
      history_id: hid,
      equipment_id: Number(data.equipment_id),
      service_date: data.service_date || new Date().toISOString().slice(0, 10),
      service_type: data.service_type || "Routine Maintenance",
      parts_replaced: data.parts_replaced || "None",
      cost: parseFloat(data.cost || 0),
      technician: data.technician || "Certified Technician",
      remarks: data.remarks || "Service performed according to manufacturer specifications."
    };
    this.state.serviceHistory.unshift(row);
    return row;
  }

  // --- Fuel Tracking ---
  listFuelRecords(userId, equipmentId = null) {
    const uid = Number(userId);
    const userEqIds = new Set(this.state.equipment.filter(e => e.user_id === uid).map(e => e.equipment_id));
    const eqMap = Object.fromEntries(this.state.equipment.map(e => [e.equipment_id, e]));

    return this.state.fuelRecords
      .filter(f => userEqIds.has(f.equipment_id) && (!equipmentId || f.equipment_id === Number(equipmentId)))
      .map(f => ({
        ...f,
        equipment_name: eqMap[f.equipment_id]?.equipment_name || `Equipment #${f.equipment_id}`
      }))
      .sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  }

  addFuelRecord(userId, data) {
    const fid = this.state.nextIds.fuel++;
    const row = {
      fuel_id: fid,
      equipment_id: Number(data.equipment_id),
      date: data.date || new Date().toISOString().slice(0, 10),
      fuel_quantity: parseFloat(data.fuel_quantity || 0),
      fuel_cost: parseFloat(data.fuel_cost || 0),
      operating_hours: parseFloat(data.operating_hours || 0),
      notes: data.notes || ""
    };
    this.state.fuelRecords.unshift(row);
    return row;
  }

  getFuelSummary(userId) {
    const records = this.listFuelRecords(userId);
    const totalLiters = Math.round(records.reduce((sum, r) => sum + (r.fuel_quantity || 0), 0) * 10) / 10;
    const totalCost = Math.round(records.reduce((sum, r) => sum + (r.fuel_cost || 0), 0));
    const avgCostPerLiter = totalLiters > 0 ? Math.round((totalCost / totalLiters) * 100) / 100 : 0;
    return {
      total_liters: totalLiters,
      total_cost: totalCost,
      avg_cost_per_liter: avgCostPerLiter,
      record_count: records.length
    };
  }

  // --- Equipment Booking / Rental ---
  listBookings(userId, equipmentId = null) {
    const uid = Number(userId);
    const userEqIds = new Set(this.state.equipment.filter(e => e.user_id === uid).map(e => e.equipment_id));
    const eqMap = Object.fromEntries(this.state.equipment.map(e => [e.equipment_id, e]));

    return this.state.bookings
      .filter(b => userEqIds.has(b.equipment_id) && (!equipmentId || b.equipment_id === Number(equipmentId)))
      .map(b => ({
        ...b,
        equipment_name: eqMap[b.equipment_id]?.equipment_name || `Equipment #${b.equipment_id}`
      }))
      .sort((a, b) => (b.booking_date || '').localeCompare(a.booking_date || ''));
  }

  createBooking(userId, data) {
    const eid = Number(data.equipment_id);
    const date = data.booking_date;
    const start = data.start_time || "08:00";
    const end = data.end_time || "17:00";

    // Double-booking conflict check
    const existing = this.state.bookings.find(b =>
      b.equipment_id === eid &&
      b.booking_date === date &&
      b.status !== "Cancelled" &&
      !(end <= b.start_time || start >= b.end_time)
    );

    if (existing) {
      throw new Error(`Conflict: Equipment is already booked on ${date} between ${existing.start_time} and ${existing.end_time}.`);
    }

    const bid = this.state.nextIds.booking++;
    const row = {
      booking_id: bid,
      equipment_id: eid,
      user_id: Number(userId),
      booking_date: date,
      start_time: start,
      end_time: end,
      purpose: data.purpose || "Field Operation",
      status: "Confirmed",
      created_at: new Date()
    };
    this.state.bookings.unshift(row);

    // Notify user
    const eq = this.state.equipment.find(e => e.equipment_id === eid);
    this.createNotification(
      userId,
      "Equipment Booking Confirmed",
      `Your reservation for ${eq?.equipment_name || 'Machine'} on ${date} (${start} - ${end}) is confirmed.`,
      "booking"
    );

    return row;
  }

  cancelBooking(userId, bookingId) {
    const bid = Number(bookingId);
    const b = this.state.bookings.find(x => x.booking_id === bid);
    if (!b) return false;
    b.status = "Cancelled";
    return true;
  }

  // --- Operational Telemetry ---
  listOperational(userId, equipmentId = null, limit = 50) {
    const uid = Number(userId);
    const userEqIds = new Set(this.state.equipment.filter(e => e.user_id === uid).map(e => e.equipment_id));
    const eqMap = Object.fromEntries(this.state.equipment.map(e => [e.equipment_id, e]));

    return this.state.operational
      .filter(o => userEqIds.has(o.equipment_id) && (!equipmentId || o.equipment_id === Number(equipmentId)))
      .map(o => ({
        ...o,
        equipment_name: eqMap[o.equipment_id]?.equipment_name || `Equipment #${o.equipment_id}`
      }))
      .sort((a, b) => String(b.recorded_at).localeCompare(String(a.recorded_at)))
      .slice(0, limit);
  }

  latestOperational(userId, equipmentId) {
    const list = this.listOperational(userId, equipmentId, 1);
    return list.length ? list[0] : null;
  }

  createOperational(userId, data) {
    const did = this.state.nextIds.operational++;
    const row = {
      data_id: did,
      equipment_id: Number(data.equipment_id),
      recorded_at: data.recorded_at || new Date().toISOString().slice(0, 16).replace('T', ' '),
      engine_speed: Number(data.engine_speed || 0),
      engine_torque: Number(data.engine_torque || 0),
      engine_load: Number(data.engine_load || 0),
      coolant_temperature: Number(data.coolant_temperature || 0),
      oil_temperature: Number(data.oil_temperature || 0),
      oil_pressure: Number(data.oil_pressure || 0),
      fuel_rate: Number(data.fuel_rate || 0),
      vehicle_speed: Number(data.vehicle_speed || 0),
      battery_voltage: Number(data.battery_voltage || 0),
      transmission: Number(data.transmission || 0),
      operating_hours: Number(data.operating_hours || 0),
      source: data.source || "manual"
    };
    this.state.operational.unshift(row);

    const eq = this.state.equipment.find(e => e.equipment_id === row.equipment_id);
    if (eq && row.operating_hours > eq.operating_hours) {
      eq.operating_hours = row.operating_hours;
    }
    return row;
  }

  // --- Predictions ---
  listPredictions(userId, equipmentId = null) {
    const uid = Number(userId);
    const userEqIds = new Set(this.state.equipment.filter(e => e.user_id === uid).map(e => e.equipment_id));
    const eqMap = Object.fromEntries(this.state.equipment.map(e => [e.equipment_id, e]));

    return this.state.predictions
      .filter(p => userEqIds.has(p.equipment_id) && (!equipmentId || p.equipment_id === Number(equipmentId)))
      .map(p => ({
        ...p,
        equipment_name: eqMap[p.equipment_id]?.equipment_name || `Equipment #${p.equipment_id}`
      }))
      .sort((a, b) => String(b.prediction_date).localeCompare(String(a.prediction_date)));
  }

  latestPrediction(userId, equipmentId) {
    const list = this.listPredictions(userId, equipmentId);
    return list.length ? list[0] : null;
  }

  insertPrediction(userId, equipmentId, predData) {
    const pid = this.state.nextIds.prediction++;
    const row = {
      prediction_id: pid,
      equipment_id: Number(equipmentId),
      prediction_date: predData.prediction_date || new Date().toISOString().slice(0, 16).replace('T', ' '),
      condition: predData.condition,
      result: predData.result || (predData.risk_level === "High" ? "HIGH RISK OF BREAKDOWN" : (predData.risk_level === "Medium" ? "SERVICE REQUIRED" : "GOOD CONDITION")),
      risk_level: predData.risk_level,
      probability: predData.probability,
      recommendation: predData.recommendation,
      explanation: predData.explanation,
      is_demo: predData.is_demo !== undefined ? predData.is_demo : 1
    };
    this.state.predictions.unshift(row);

    // Update equipment status
    const eq = this.state.equipment.find(e => e.equipment_id === Number(equipmentId));
    if (eq) {
      if (predData.risk_level === "High") {
        eq.status = "High Risk";
        eq.current_condition = "High Risk";
      } else if (predData.risk_level === "Medium" && eq.status === "Healthy") {
        eq.status = "Maintenance Due";
        eq.current_condition = "Maintenance Due";
      }
    }
    return row;
  }

  // --- Notifications & Alerts ---
  listNotifications(userId) {
    return this.state.notifications
      .filter(n => n.user_id === Number(userId))
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  }

  unreadNotifications(userId) {
    return this.state.notifications.filter(n => n.user_id === Number(userId) && !n.is_read).length;
  }

  markNotificationsRead(userId) {
    this.state.notifications.forEach(n => {
      if (n.user_id === Number(userId)) n.is_read = 1;
    });
    return true;
  }

  createNotification(userId, title, message, type = "info") {
    const nid = this.state.nextIds.notification++;
    const row = {
      notification_id: nid,
      user_id: Number(userId),
      title,
      message,
      notification_type: type,
      is_read: 0,
      created_at: new Date().toISOString()
    };
    this.state.notifications.unshift(row);
    return row;
  }

  listAlerts(userId = null, limit = 50) {
    return this.state.alerts
      .filter(a => !userId || a.user_id === Number(userId))
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
      .slice(0, limit);
  }

  createAlert({ userId, equipmentId, equipmentName, eventType, title, message, severity = "medium" }) {
    const aid = this.state.nextIds.alert++;
    const row = {
      alert_id: aid,
      user_id: Number(userId),
      equipment_id: equipmentId ? Number(equipmentId) : null,
      equipment_name: equipmentName || "Equipment",
      event_type: eventType || "Notice",
      title,
      message,
      severity,
      email_status: "simulated",
      sms_status: "simulated",
      created_at: new Date().toISOString()
    };
    this.state.alerts.unshift(row);
    return row;
  }

  // --- Conversations & Chat ---
  listConversations(userId) {
    return this.state.conversations
      .filter(c => c.user_id === Number(userId))
      .sort((a, b) => String(b.updated_at || b.created_at).localeCompare(String(a.updated_at || a.created_at)));
  }

  getConversation(userId, conversationId) {
    return this.state.conversations.find(c => c.user_id === Number(userId) && c.conversation_id === Number(conversationId)) || null;
  }

  createConversation(userId, title = "New Chat") {
    const cid = this.state.nextIds.conversation++;
    const conv = {
      conversation_id: cid,
      user_id: Number(userId),
      title,
      created_at: new Date(),
      updated_at: new Date()
    };
    this.state.conversations.unshift(conv);
    return conv;
  }

  deleteConversation(userId, conversationId) {
    const cid = Number(conversationId);
    this.state.conversations = this.state.conversations.filter(c => !(c.user_id === Number(userId) && c.conversation_id === cid));
    this.state.messages = this.state.messages.filter(m => m.conversation_id !== cid);
    return true;
  }

  listMessages(conversationId) {
    return this.state.messages
      .filter(m => m.conversation_id === Number(conversationId))
      .sort((a, b) => a.message_id - b.message_id);
  }

  addMessage(conversationId, userId, role, content, equipmentId = null) {
    const mid = this.state.nextIds.message++;
    const msg = {
      message_id: mid,
      conversation_id: Number(conversationId),
      user_id: Number(userId),
      role,
      content,
      equipment_id: equipmentId ? Number(equipmentId) : null,
      created_at: new Date()
    };
    this.state.messages.push(msg);

    const conv = this.state.conversations.find(c => c.conversation_id === Number(conversationId));
    if (conv) {
      conv.updated_at = new Date();
      if (role === "user" && (conv.title === "New Chat" || conv.title === "General Discussion")) {
        conv.title = content.slice(0, 32) + (content.length > 32 ? "…" : "");
      }
    }
    return msg;
  }

  clearMessages(conversationId) {
    const cid = Number(conversationId);
    this.state.messages = this.state.messages.filter(m => m.conversation_id !== cid);
    return true;
  }

  // --- Comprehensive Dashboard Data Provider ---
  dashboard(userId) {
    const equipment = this.listEquipment(userId);
    const maintenance = this.listMaintenance(userId);
    const predictions = this.listPredictions(userId);
    const notifications = this.listNotifications(userId);
    const bookings = this.listBookings(userId);
    const fuelSummary = this.getFuelSummary(userId);

    const good = equipment.filter(e => e.status === "Healthy").length;
    const due = equipment.filter(e => e.status === "Maintenance Due" || e.status === "Warning").length;
    const highRisk = equipment.filter(e => e.status === "High Risk").length;

    // Upcoming maintenance
    const todayStr = new Date().toISOString().slice(0, 10);
    const upcomingMaintenance = maintenance
      .filter(m => m.next_service_date && m.next_service_date >= todayStr)
      .sort((a, b) => a.next_service_date.localeCompare(b.next_service_date))
      .slice(0, 5);

    // Active bookings
    const activeBookings = bookings
      .filter(b => b.status === "Confirmed" && b.booking_date >= todayStr)
      .slice(0, 5);

    const conditionChart = {
      labels: ["Healthy", "Maintenance Due", "Warning", "High Risk"],
      values: [
        equipment.filter(e => e.status === "Healthy").length,
        equipment.filter(e => e.status === "Maintenance Due").length,
        equipment.filter(e => e.status === "Warning").length,
        equipment.filter(e => e.status === "High Risk").length,
      ],
      colors: ["#22c55e", "#f59e0b", "#eab308", "#ef4444"],
    };

    const riskChart = {
      labels: ["Low", "Medium", "High"],
      values: [
        equipment.filter(e => e.risk_level === "Low").length,
        equipment.filter(e => e.risk_level === "Medium").length,
        equipment.filter(e => e.risk_level === "High").length,
      ],
      colors: ["#22c55e", "#f59e0b", "#ef4444"]
    };

    const months = [];
    const counts = [];
    const now = new Date();
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const mStr = d.toLocaleString('en-US', { month: 'short' });
      const yearMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      months.push(mStr);
      counts.push(maintenance.filter(m => (m.service_date || '').startsWith(yearMonth)).length);
    }
    const maintenanceChart = { labels: months, values: counts };

    const usageChart = {
      labels: equipment.map(e => e.equipment_name),
      values: equipment.map(e => parseFloat(e.operating_hours || 0)),
      colors: "#166534"
    };

    const activity = [];
    for (const m of maintenance.slice(0, 6)) {
      activity.push({
        type: "maintenance",
        text: `${m.equipment_name} maintenance recorded`,
        detail: m.service_type,
        date: m.service_date
      });
    }
    for (const p of predictions.slice(0, 5)) {
      activity.push({
        type: "prediction",
        text: `Prediction generated for ${p.equipment_name}`,
        detail: `${p.result || p.condition} · ${p.risk_level} risk (${p.probability}%)`,
        date: p.prediction_date
      });
    }
    for (const n of notifications.slice(0, 4)) {
      activity.push({
        type: "notification",
        text: n.title,
        detail: n.message,
        date: n.created_at
      });
    }
    activity.sort((a, b) => String(b.date).localeCompare(String(a.date)));

    return {
      stats: {
        total: equipment.length,
        good,
        due,
        high_risk: highRisk,
        fuel_liters: fuelSummary.total_liters,
        fuel_cost: fuelSummary.total_cost,
        active_bookings: activeBookings.length
      },
      health: equipment.map(e => ({
        equipment_id: e.equipment_id,
        equipment_name: e.equipment_name,
        equipment_type: e.equipment_type,
        status: e.status,
        risk_level: e.risk_level,
        risk_probability: e.risk_probability,
        last_service_date: e.last_service_date,
        next_service_date: e.next_service_date
      })),
      charts: {
        condition: conditionChart,
        risk: riskChart,
        maintenance: maintenanceChart,
        usage: usageChart
      },
      upcoming_maintenance: upcomingMaintenance,
      active_bookings: activeBookings,
      fuel_summary: fuelSummary,
      activity: activity.slice(0, 8)
    };
  }

  // --- Admin stats ---
  adminStats() {
    const totalUsers = this.state.users.length;
    const verifiedUsers = Object.values(this.state.profiles).filter(p => p.email_verified).length;
    const phoneVerified = Object.values(this.state.profiles).filter(p => p.phone_verified).length;
    const totalAlerts = this.state.alerts.length;
    return {
      total_users: totalUsers,
      email_verified: verifiedUsers,
      phone_verified: phoneVerified,
      alerts_total: totalAlerts,
      email_failed: 0,
      sms_failed: 0
    };
  }
}

export const db = new InMemStore();
export default db;
