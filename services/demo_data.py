"""Realistic sample data used when the app runs in Demo Mode (no MySQL).

All timestamps are generated relative to ``now`` so the demo always looks
fresh. Data is deterministic (seeded RNG) and clearly labeled as demo data
in the UI. When MySQL is connected, this module is not used.
"""
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DEMO_PASSWORD = "demo1234"


def build_demo_state(now=None):
    """Return a fresh in-memory demo store (dicts + next-id counters)."""
    now = now or datetime.now()
    rng = random.Random(42)

    users = [{
        "user_id": 1,
        "name": "Demo Farmer",
        "email": "farmer@demo.com",
        "password_hash": generate_password_hash(DEMO_PASSWORD),
        "phone": "+90 532 000 00 00",
        "created_at": now - timedelta(days=400),
    }]

    equipment = [
        {"equipment_id": 1, "user_id": 1, "equipment_name": "Tractor TR001",
         "equipment_type": "Tractor", "brand": "Tümosan", "model": "81.110",
         "year": 2024, "registration_number": "TR-2024-001",
         "purchase_date": "2024-03-15", "operating_hours": 1240.0,
         "status": "Healthy", "created_at": now - timedelta(days=500)},
        {"equipment_id": 2, "user_id": 1, "equipment_name": "Tractor TR002",
         "equipment_type": "Tractor", "brand": "John Deere", "model": "5055E",
         "year": 2023, "registration_number": "JD-2023-114",
         "purchase_date": "2023-05-02", "operating_hours": 2860.0,
         "status": "Maintenance Due", "created_at": now - timedelta(days=600)},
        {"equipment_id": 3, "user_id": 1, "equipment_name": "Harvester HV001",
         "equipment_type": "Harvester", "brand": "Claas", "model": "Lexion 5300",
         "year": 2021, "registration_number": "CL-2021-032",
         "purchase_date": "2021-08-20", "operating_hours": 1980.0,
         "status": "Healthy", "created_at": now - timedelta(days=700)},
        {"equipment_id": 4, "user_id": 1, "equipment_name": "Irrigation Pump IP001",
         "equipment_type": "Irrigation Pump", "brand": "KSB", "model": "Etanorm 80-160",
         "year": 2022, "registration_number": "KS-2022-007",
         "purchase_date": "2022-04-11", "operating_hours": 3420.0,
         "status": "Healthy", "created_at": now - timedelta(days=640)},
        {"equipment_id": 5, "user_id": 1, "equipment_name": "Sprayer SP001",
         "equipment_type": "Sprayer", "brand": "Hardi", "model": "Commander 2800",
         "year": 2022, "registration_number": "HD-2022-019",
         "purchase_date": "2022-06-05", "operating_hours": 1505.0,
         "status": "High Risk", "created_at": now - timedelta(days=620)},
    ]

    maintenance = [
        {"maintenance_id": 1, "equipment_id": 1, "service_date": (now - timedelta(days=115)).date().isoformat(),
         "service_type": "Oil Change", "problem_description": "Routine 500-hour service",
         "action_taken": "Changed engine oil, oil filter and air filter",
         "parts_replaced": "Oil filter, air filter, 10L engine oil", "cost": 1850.00,
         "next_service_date": (now + timedelta(days=35)).date().isoformat(), "status": "Completed",
         "created_at": now - timedelta(days=115)},
        {"maintenance_id": 2, "equipment_id": 1, "service_date": (now - timedelta(days=33)).date().isoformat(),
         "service_type": "Regular Service", "problem_description": "Pre-harvest inspection",
         "action_taken": "Greased linkages, checked belts and tire pressure",
         "parts_replaced": "", "cost": 620.00,
         "next_service_date": (now + timedelta(days=92)).date().isoformat(), "status": "Completed",
         "created_at": now - timedelta(days=33)},
        {"maintenance_id": 3, "equipment_id": 2, "service_date": (now - timedelta(days=168)).date().isoformat(),
         "service_type": "Regular Service", "problem_description": "1500-hour service overdue check",
         "action_taken": "Full service performed, hydraulic fluid topped up",
         "parts_replaced": "Fuel filter, hydraulic filter", "cost": 2400.00,
         "next_service_date": now.date().isoformat(), "status": "Scheduled",
         "created_at": now - timedelta(days=168)},
        {"maintenance_id": 4, "equipment_id": 2, "service_date": (now - timedelta(days=295)).date().isoformat(),
         "service_type": "Hydraulic Repair", "problem_description": "Weak lift arm response",
         "action_taken": "Replaced hydraulic control valve seal kit",
         "parts_replaced": "Seal kit, hydraulic oil 4L", "cost": 1350.00,
         "next_service_date": (now - timedelta(days=60)).date().isoformat(), "status": "Completed",
         "created_at": now - timedelta(days=295)},
        {"maintenance_id": 5, "equipment_id": 3, "service_date": (now - timedelta(days=88)).date().isoformat(),
         "service_type": "Transmission Service", "problem_description": "Gearbox oil change per schedule",
         "action_taken": "Changed gearbox oil and checked clutch",
         "parts_replaced": "Gearbox oil 12L", "cost": 2100.00,
         "next_service_date": (now + timedelta(days=190)).date().isoformat(), "status": "Completed",
         "created_at": now - timedelta(days=88)},
        {"maintenance_id": 6, "equipment_id": 4, "service_date": (now - timedelta(days=132)).date().isoformat(),
         "service_type": "Electrical Repair", "problem_description": "Motor would not start",
         "action_taken": "Replaced starter relay and cleaned battery terminals",
         "parts_replaced": "Starter relay", "cost": 480.00,
         "next_service_date": (now + timedelta(days=230)).date().isoformat(), "status": "Completed",
         "created_at": now - timedelta(days=132)},
        {"maintenance_id": 7, "equipment_id": 5, "service_date": (now - timedelta(days=208)).date().isoformat(),
         "service_type": "Cooling System", "problem_description": "Coolant leak noticed near radiator",
         "action_taken": "Replaced radiator hose and refilled coolant",
         "parts_replaced": "Radiator hose, coolant 6L", "cost": 980.00,
         "next_service_date": (now - timedelta(days=40)).date().isoformat(), "status": "Completed",
         "created_at": now - timedelta(days=208)},
        {"maintenance_id": 8, "equipment_id": 5, "service_date": (now - timedelta(days=47)).date().isoformat(),
         "service_type": "Engine Repair", "problem_description": "Rough idle and power loss",
         "action_taken": "Cleaned injectors, replaced fuel filter",
         "parts_replaced": "Fuel filter, injector seal", "cost": 3100.00,
         "next_service_date": (now + timedelta(days=75)).date().isoformat(), "status": "Completed",
         "created_at": now - timedelta(days=47)},
    ]

    # ---- Deterministic operational data ----------------------------------
    # Each equipment gets realistic operating profiles; TR001 includes some
    # recent high-temperature readings that the ML model flags as anomalous.
    profiles = {
        1: dict(speed=2100, torque=420, load=78, coolant=88, oil=96, oilp=2.9,
                fuel=11.4, vspeed=7.5, batt=13.8, trans=8.2, spread=dict(
                    speed=180, torque=60, load=18, coolant=14, oil=18, oilp=0.6,
                    fuel=3.2, vspeed=4.0, batt=0.6, trans=1.6)),
        2: dict(speed=1950, torque=380, load=66, coolant=90, oil=101, oilp=2.6,
                fuel=10.2, vspeed=9.0, batt=13.5, trans=7.4, spread=dict(
                    speed=170, torque=55, load=16, coolant=12, oil=16, oilp=0.5,
                    fuel=2.8, vspeed=4.5, batt=0.5, trans=1.4)),
        3: dict(speed=2250, torque=480, load=84, coolant=92, oil=104, oilp=3.1,
                fuel=14.8, vspeed=5.0, batt=14.0, trans=9.6, spread=dict(
                    speed=190, torque=70, load=15, coolant=10, oil=14, oilp=0.5,
                    fuel=3.0, vspeed=2.5, batt=0.5, trans=1.8)),
        4: dict(speed=2950, torque=240, load=88, coolant=74, oil=82, oilp=3.4,
                fuel=7.2, vspeed=0.0, batt=13.9, trans=1.0, spread=dict(
                    speed=220, torque=40, load=10, coolant=8, oil=10, oilp=0.4,
                    fuel=1.4, vspeed=0.0, batt=0.4, trans=0.2)),
        5: dict(speed=2050, torque=410, load=72, coolant=96, oil=112, oilp=2.2,
                fuel=11.0, vspeed=6.0, batt=12.6, trans=8.0, spread=dict(
                    speed=160, torque=55, load=14, coolant=16, oil=18, oilp=0.5,
                    fuel=2.6, vspeed=3.0, batt=0.7, trans=1.5)),
    }

    operational = []
    did = 1
    for eid, p in profiles.items():
        n_rows = 30 if eid == 1 else 10
        for i in range(n_rows):
            t = now - timedelta(days=n_rows - i, hours=2 + (i % 5))
            row = {
                "data_id": did, "equipment_id": eid, "recorded_at": t,
                "engine_speed": round(p["speed"] + rng.uniform(-1, 1) * p["spread"]["speed"], 1),
                "engine_torque": round(p["torque"] + rng.uniform(-1, 1) * p["spread"]["torque"], 1),
                "engine_load": round(p["load"] + rng.uniform(-1, 1) * p["spread"]["load"], 2),
                "coolant_temperature": round(p["coolant"] + rng.uniform(-1, 1) * p["spread"]["coolant"], 2),
                "oil_temperature": round(p["oil"] + rng.uniform(-1, 1) * p["spread"]["oil"], 2),
                "oil_pressure": round(p["oilp"] + rng.uniform(-1, 1) * p["spread"]["oilp"], 2),
                "fuel_rate": round(p["fuel"] + rng.uniform(-1, 1) * p["spread"]["fuel"], 2),
                "vehicle_speed": round(max(0, p["vspeed"] + rng.uniform(-1, 1) * p["spread"]["vspeed"]), 2),
                "battery_voltage": round(p["batt"] + rng.uniform(-1, 1) * p["spread"]["batt"], 2),
                "transmission": round(p["trans"] + rng.uniform(-1, 1) * p["spread"]["trans"], 2),
                "operating_hours": round(p["speed"] / 10 * (i + 1) / 8, 1),
                "source": "csv" if eid == 1 and i < 8 else "manual",
            }
            # A few intentionally hot readings for TR001 (last week)
            if eid == 1 and i >= n_rows - 4:
                row["coolant_temperature"] = round(rng.uniform(103, 109), 2)
                row["oil_temperature"] = round(rng.uniform(118, 126), 2)
                row["oil_pressure"] = round(rng.uniform(1.4, 1.9), 2)
            operational.append(row)
            did += 1

    predictions = [
        {"prediction_id": 1, "equipment_id": 1, "prediction_date": now - timedelta(days=40),
         "condition": "Normal", "risk_level": "Low", "probability": 12.0,
         "recommendation": "Continue routine maintenance. No abnormal patterns detected — "
                           "follow the scheduled oil change and service intervals.",
         "explanation": "All operating parameters stayed within typical ranges for this tractor.",
         "is_demo": 1},
        {"prediction_id": 2, "equipment_id": 2, "prediction_date": now - timedelta(days=60),
         "condition": "Anomalous", "risk_level": "Medium", "probability": 64.0,
         "recommendation": "Service is overdue for this tractor. Book a full service soon and "
                           "check hydraulic fluid levels and filters.",
         "explanation": "Rising oil temperature combined with the overdue service interval "
                        "produced a medium-risk pattern.",
         "is_demo": 1},
        {"prediction_id": 3, "equipment_id": 5, "prediction_date": now - timedelta(days=20),
         "condition": "Anomalous", "risk_level": "High", "probability": 92.0,
         "recommendation": "Inspect the cooling system, engine temperature and oil condition. "
                           "High coolant and oil temperatures with low oil pressure indicate "
                           "the engine is running hot — have a technician check it before the next use.",
         "explanation": "Coolant temperature above 100°C, oil temperature above 110°C and oil "
                        "pressure below 2.0 bar were detected together.",
         "is_demo": 1},
    ]

    notifications = [
        {"notification_id": 1, "user_id": 1, "title": "Maintenance due for TR002",
         "message": "The regular service for Tractor TR002 (John Deere 5055E) is due today.",
         "notification_type": "maintenance", "is_read": 0, "created_at": now - timedelta(hours=5)},
        {"notification_id": 2, "user_id": 1, "title": "High maintenance risk detected",
         "message": "Sprayer SP001 is showing a high maintenance risk. Review the latest prediction.",
         "notification_type": "risk", "is_read": 0, "created_at": now - timedelta(days=1)},
        {"notification_id": 3, "user_id": 1, "title": "Service due in 50 operating hours",
         "message": "Tractor TR001 is approaching its next oil change interval (50 h remaining).",
         "notification_type": "maintenance", "is_read": 1, "created_at": now - timedelta(days=2)},
        {"notification_id": 4, "user_id": 1, "title": "New prediction available",
         "message": "A new condition prediction was generated for Sprayer SP001.",
         "notification_type": "prediction", "is_read": 0, "created_at": now - timedelta(days=3)},
    ]

    chat = [
        {"chat_id": 1, "user_id": 1, "question": "Why is my tractor showing high maintenance risk?",
         "answer": "The system detected an abnormal operating pattern. Please check engine "
                   "temperature, oil pressure and the cooling system condition.",
         "equipment_id": 5, "created_at": now - timedelta(days=2)},
    ]

    return {
        "users": users,
        "equipment": equipment,
        "maintenance": maintenance,
        "operational": operational,
        "predictions": predictions,
        "notifications": notifications,
        "chat": chat,
        "password_resets": [],
        "profiles": {1: {"email_verified": True, "phone_verified": False,
                          "is_admin": True, "farm_name": "Demo Farm",
                          "location": "Konya Plain"}},
        "email_verifications": [],
        "phone_otps": [],
        "notif_prefs": {},
        "alerts": [],
        "conversations": [],
        "messages": [],
        "next_ids": {
            "user": 2, "equipment": 6, "maintenance": 9, "operational": did,
            "prediction": 4, "notification": 5, "chat": 2, "alert": 1,
        },
    }