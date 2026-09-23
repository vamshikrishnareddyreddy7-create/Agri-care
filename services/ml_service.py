"""Machine-learning prediction service.

The model (when connected) performs **condition / anomaly prediction** on
operational data and the result is converted into a maintenance-risk
indicator. It does NOT predict the exact date of a failure.

* If ``model/predictive_model.pkl`` exists, it is loaded with joblib and used.
  Responses are then flagged ``"is_demo": false``.
* Otherwise a transparent rule-based check over typical operating ranges is
  used and every response is explicitly flagged ``"is_demo": true`` and
  labeled "Demo Prediction — ML model not connected".
"""
import os

import joblib

from config import Config

FEATURES = [
    "engine_speed", "engine_torque", "engine_load", "coolant_temperature",
    "oil_temperature", "oil_pressure", "fuel_rate", "vehicle_speed",
    "battery_voltage", "transmission",
]

# Typical operating ranges used by the demo rule-based check.
TYPICAL_RANGES = {
    "engine_speed": (800, 2800, "RPM"),
    "engine_torque": (100, 650, "Nm"),
    "engine_load": (0, 95, "%"),
    "coolant_temperature": (70, 100, "°C"),
    "oil_temperature": (75, 110, "°C"),
    "oil_pressure": (2.0, 4.5, "bar"),
    "fuel_rate": (0, 22, "L/h"),
    "vehicle_speed": (0, 45, "km/h"),
    "battery_voltage": (12.4, 14.6, "V"),
    "transmission": (1, 12, "gear"),
}

# Hard anomaly triggers used by the demo checker.
_HARD_FLAGS = {
    "coolant_temperature": (103.0, "Coolant temperature is above the typical maximum (100 °C)."),
    "oil_temperature": (112.0, "Oil temperature is above the typical maximum (110 °C)."),
    "oil_pressure": (None, "Oil pressure is below the typical minimum (2.0 bar)."),
    "battery_voltage": (None, "Battery voltage is below the typical minimum (12.4 V)."),
    "engine_load": (95.0, "Engine load is above the typical maximum (95%)."),
}

RECOMMENDATIONS = {
    "coolant_temperature": "Inspect the cooling system: check coolant level, radiator fins, "
                           "fan belt and thermostat. Do not open the radiator cap while hot.",
    "oil_temperature": "Check the oil level and oil cooler. If the oil looks burnt or watery, "
                       "have it changed and inspect the lubrication system.",
    "oil_pressure": "Stop the engine and check the oil level, oil filter and for leaks. "
                    "Low oil pressure can seriously damage the engine.",
    "battery_voltage": "Check battery terminals, charge level and the alternator. "
                       "Replace the battery if it no longer holds a charge.",
    "engine_load": "Reduce the load and check for a clogged air filter or fuel problem.",
}

_model = None
_model_error = None
_MODEL_CONNECTED = False


def _load_model():
    global _model, _MODEL_CONNECTED, _model_error
    if _model is not None or _MODEL_CONNECTED:
        return
    if not os.path.exists(Config.MODEL_PATH):
        _model_error = "model file not found"
        return
    try:
        _model = joblib.load(Config.MODEL_PATH)
        # Validate the expected interface
        if not hasattr(_model, "predict_proba"):
            raise ValueError("model object has no predict_proba()")
        _MODEL_CONNECTED = True
    except Exception as exc:            # noqa: BLE001
        _model_error = str(exc)
        _model = None
        _MODEL_CONNECTED = False


def model_connected():
    _load_model()
    return _MODEL_CONNECTED


def model_status():
    _load_model()
    if _MODEL_CONNECTED:
        return {"connected": True, "path": Config.MODEL_PATH}
    return {"connected": False, "error": _model_error or "model file not found"}


def _as_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{field}' must be a number.")


def analyze(params, save=True, db=None, user_id=None, equipment_id=None):
    """Run the condition analysis and return the full result object.

    ``params`` maps feature names to numeric strings/numbers. At least the
    required features must be present; missing ones default to typical values.
    """
    _load_model()

    cleaned = {}
    for f in FEATURES:
        v = params.get(f)
        if v in (None, ""):
            cleaned[f] = None
        else:
            cleaned[f] = _as_float(v, f)

    if _MODEL_CONNECTED:
        result = _predict_with_model(cleaned)
    else:
        result = _predict_demo(cleaned)

    result["demo"] = not _MODEL_CONNECTED
    result["model_connected"] = _MODEL_CONNECTED
    result["explanation"] = _build_explanation(cleaned, result.get("flags", []),
                                               result["condition"])
    result.pop("flags", None)

    if save and db and user_id and equipment_id:
        from datetime import datetime
        db.insert_prediction(user_id, equipment_id, {
            "prediction_date": datetime.now(),
            "condition": result["condition"],
            "risk_level": result["risk_level"],
            "probability": result["probability"],
            "recommendation": result["recommendation"],
            "explanation": result["explanation"],
            "is_demo": result["demo"],
        })
    return result


# ---------------------------------------------------------------------- #
#  Model path
# ---------------------------------------------------------------------- #
def _predict_with_model(cleaned):
    import numpy as np
    defaults = {"engine_speed": 2000.0, "engine_torque": 400.0, "engine_load": 70.0,
                "coolant_temperature": 88.0, "oil_temperature": 96.0, "oil_pressure": 2.9,
                "fuel_rate": 10.0, "vehicle_speed": 6.0, "battery_voltage": 13.8,
                "transmission": 8.0}
    row = np.array([[cleaned.get(f) if cleaned.get(f) is not None else defaults[f]
                     for f in FEATURES]], dtype=float)
    prob = float(_model.predict_proba(row)[0, 1]) * 100.0
    prob = round(min(99.9, max(0.1, prob)), 1)
    condition = "Anomalous" if prob >= 50 else "Normal"
    risk_level = "Low" if prob < 50 else ("Medium" if prob < 75 else "High")
    recommendation = _recommendation_for(condition, risk_level, prob)
    return {"condition": condition, "risk_level": risk_level,
            "probability": prob, "recommendation": recommendation,
            "flags": []}


# ---------------------------------------------------------------------- #
#  Demo (rule-based) path
# ---------------------------------------------------------------------- #
def _predict_demo(cleaned):
    flags = []
    severity = 0.0
    for f in FEATURES:
        v = cleaned.get(f)
        if v is None:
            continue
        lo, hi, unit = TYPICAL_RANGES[f]
        hard, hard_msg = _HARD_FLAGS.get(f, (None, ""))
        if f == "oil_pressure" or f == "battery_voltage":
            if hard is None and v < lo:
                flags.append((f, hard_msg))
                severity += min(1.0, (lo - v) / lo * 2.2)
            elif v > hi:
                severity += min(1.0, (v - hi) / hi * 1.8)
        else:
            if hard is not None and v > hard:
                flags.append((f, hard_msg))
                severity += min(1.0, (v - hard) / hard * 3.0)
            elif v > hi:
                severity += min(0.7, (v - hi) / hi * 1.6)
            elif v < lo:
                severity += min(0.5, (lo - v) / lo * 1.2)

    prob = round(min(99.0, max(2.0, severity * 100.0)), 1)
    if not flags and prob < 40:
        condition, risk_level = "Normal", "Low"
    elif prob < 65:
        condition, risk_level = "Anomalous", "Medium"
    else:
        condition, risk_level = "Anomalous", "High"
    return {"condition": condition, "risk_level": risk_level,
            "probability": prob,
            "recommendation": _recommendation_for(condition, risk_level, prob),
            "flags": flags}


def _recommendation_for(condition, risk_level, prob):
    if condition == "Normal":
        return ("No abnormal operating patterns detected. Continue routine maintenance "
                "and follow the scheduled service intervals.")
    if risk_level == "High":
        return ("Inspect the cooling system, engine temperature and oil condition. "
                "The machine should be checked by a qualified technician before "
                "further heavy use.")
    return ("An abnormal operating pattern was detected. Compare the flagged "
            "parameters with the operator's manual, and book a service in the "
            "next few days.")


def _build_explanation(cleaned, flags, condition="Normal"):
    if flags:
        lines = [f"- {msg}" for _, msg in flags]
        return ("The prediction was generated because one or more operating "
                "parameters were outside their typical range:\n" + "\n".join(lines))
    if _MODEL_CONNECTED:
        if condition == "Anomalous":
            return ("The machine learning model detected an abnormal operating "
                    "pattern: this reading deviates from the normal patterns it "
                    "learned from agricultural equipment data.")
        return ("The machine learning model compared this reading with the normal "
                "operating patterns it learned from agricultural equipment data "
                "and did not find a significant deviation.")
    return ("All entered parameters are inside the typical operating ranges used "
            "by the demo analysis.")


def info_text():
    """Small 'About Predictive Maintenance' copy shown on the prediction page."""
    return ("The Machine Learning model learns patterns from agricultural equipment "
            "operational data and identifies abnormal operating conditions. The "
            "prediction is used as an early maintenance-risk indicator.")