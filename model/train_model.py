"""Train the predictive-maintenance demo model.

Pipeline (run from the project root):

    python model/train_model.py

1. Generates a realistic tractor operational dataset (normal + injected
   abnormal readings) and writes model/tractor_operational_dataset.csv.
2. Trains an anomaly/condition classifier: XGBoost when available, otherwise
   scikit-learn's GradientBoosting.
3. Evaluates on a held-out test split and prints honest metrics.
4. Saves the model to model/predictive_model.pkl so ml_service can use it.

The task is condition/anomaly prediction converted into a maintenance-risk
indicator — the model does NOT predict failure dates, and no accuracy numbers
are ever presented as predictions of real-world failures.
"""
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FEATURES = [
    "engine_speed", "engine_torque", "engine_load", "coolant_temperature",
    "oil_temperature", "oil_pressure", "fuel_rate", "vehicle_speed",
    "battery_voltage", "transmission",
]

# (typical mean, typical spread) — mirrors services/ml_service.py ranges
TYPICAL = {
    "engine_speed": (2000, 220), "engine_torque": (400, 70),
    "engine_load": (72, 14), "coolant_temperature": (88, 9),
    "oil_temperature": (97, 11), "oil_pressure": (2.9, 0.45),
    "fuel_rate": (10.5, 2.8), "vehicle_speed": (6.5, 4.0),
    "battery_voltage": (13.7, 0.45), "transmission": (8.0, 1.6),
}


def make_dataset(n_normal=4000, n_anomalous=180, seed=7):
    rng = np.random.default_rng(seed)
    normal, anomalies = [], []

    for _ in range(n_normal):
        row = {f: float(np.clip(rng.normal(*TYPICAL[f]), 0, None)) for f in FEATURES}
        normal.append(row)

    for _ in range(n_anomalous):
        row = {f: float(np.clip(rng.normal(*TYPICAL[f]), 0, None)) for f in FEATURES}
        mode = random.randrange(3)
        if mode == 0:      # overheating: hot coolant + hot oil + low pressure
            row["coolant_temperature"] = float(rng.uniform(103, 112))
            row["oil_temperature"] = float(rng.uniform(113, 129))
            row["oil_pressure"] = float(rng.uniform(1.2, 1.9))
        elif mode == 1:    # electrical: weak battery
            row["battery_voltage"] = float(rng.uniform(11.7, 12.3))
        else:              # overloaded engine
            row["engine_load"] = float(rng.uniform(96, 108))
            row["engine_speed"] = float(rng.uniform(2900, 3300))
        anomalies.append(row)

    return normal, anomalies


def to_arrays(normal, anomalies):
    X = np.array([[r[f] for f in FEATURES] for r in normal + anomalies], dtype=float)
    y = np.array([0] * len(normal) + [1] * len(anomalies))
    return X, y


def main():
    import joblib
    try:
        import xgboost as xgb
        clf = xgb.XGBClassifier(n_estimators=220, max_depth=5, learning_rate=0.08,
                                subsample=0.9, colsample_bytree=0.9,
                                random_state=7, eval_metric="logloss", verbosity=0)
        clf_name = "XGBoost"
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        clf = GradientBoostingClassifier(n_estimators=220, max_depth=4,
                                         learning_rate=0.08, random_state=7)
        clf_name = "GradientBoosting (XGBoost not installed)"

    normal, anomalies = make_dataset()
    X, y = to_arrays(normal, anomalies)

    from sklearn.model_selection import train_test_split
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2,
                                              random_state=7, stratify=y)
    clf.fit(X_tr, y_tr)

    from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
    y_proba = clf.predict_proba(X_te)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)
    print(f"Trained classifier : {clf_name}")
    print(f"Dataset            : {len(X)} rows "
          f"({len(normal)} normal / {len(anomalies)} anomalous)")
    print(f"Test accuracy      : {accuracy_score(y_te, y_pred):.3f}")
    print(f"Test ROC AUC       : {roc_auc_score(y_te, y_proba):.3f}")
    print(classification_report(y_te, y_pred, target_names=["Normal", "Anomalous"],
                                zero_division=0))

    # ---- persist dataset CSV (for the capstone report) -----------------
    try:
        import pandas as pd
        df = pd.DataFrame([{**r, "condition": "Anomalous" if l else "Normal"}
                           for r, l in zip(normal + anomalies, y)])
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "tractor_operational_dataset.csv")
        df.to_csv(csv_path, index=False)
        print(f"Dataset CSV        : {csv_path}")
    except ImportError:
        import csv
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "tractor_operational_dataset.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FEATURES + ["condition"])
            writer.writeheader()
            for r, l in zip(normal + anomalies, y):
                writer.writerow({**r, "condition": "Anomalous" if l else "Normal"})
        print(f"Dataset CSV        : {csv_path}")

    # ---- persist model ------------------------------------------------
    # The raw estimator is pickled directly (not a custom wrapper class) so
    # joblib.load works from any module. predict_proba() returns
    # [P(Normal), P(Anomalous)] using the FEATURES column order above.
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "predictive_model.pkl")
    joblib.dump(clf, model_path)
    print(f"Model saved        : {model_path}")
    print(f"Feature order      : {', '.join(FEATURES)}")
    print("\nRestart the Flask app; /api/predict will then use the real model "
          "(responses are no longer labeled 'Demo').")


if __name__ == "__main__":
    main()