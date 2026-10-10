"""Train and compare claim models using a time-based split.
Train on visits before 1 Jul 2025, test on visits from 1 Jul 2025 (the 'future').

Two questions are modelled:
  1. rejection  : will the claim be fully rejected?
  2. shortfall  : will the claim be paid less than claimed (rejected OR partially approved)?
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from db import PROJECT_ROOT

DATA_PATH = PROJECT_ROOT / "data" / "processed" / "ml_features.csv"
MODEL_DIR = PROJECT_ROOT / "ai" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

SPLIT_DATE = "2025-07-01"

# Inputs known BEFORE the claim is submitted
CATEGORICAL = ["hospital_id", "hospital_type", "department_name", "insurer_id", "insurer_type",
               "visit_type", "treatment_type", "diagnosis", "gender"]
NUMERIC = ["total_beds", "waiting_minutes", "length_of_stay", "age", "claim_amount",
           "consultation_charge", "medicine_charge", "lab_charge", "room_charge",
           "surgery_charge", "visit_month", "is_winter"]
FEATURES = CATEGORICAL + NUMERIC

df = pd.read_csv(DATA_PATH, parse_dates=["visit_date"])
df["is_shortfall"] = (df["claim_status"] != "Approved").astype(int)

# ---------- Theoretical ceiling ----------
# The simulated outcomes are random draws with raised odds for the planted groups.
# If a model knew those exact odds, this is the best AUC any model could reach.
bill_total = df[["consultation_charge", "medicine_charge", "lab_charge",
                 "room_charge", "surgery_charge"]].sum(axis=1)
p_reject = np.full(len(df), 0.10)
p_reject[(df["insurer_id"] == 4) & df["hospital_id"].isin([6, 7])] = 0.28
p_reject[(df["hospital_id"] == 4) & (df["department_name"] == "Cardiology")] = 0.22
p_reject[bill_total > 200_000] = 0.20
p_reject[df["visit_month"].isin([12, 1])] += 0.04
p_partial = np.where(df["treatment_type"] == "Surgery", 0.40, 0.14)
ceiling = {"is_rejected": p_reject, "is_shortfall": p_reject + p_partial}

# IDs are labels, not quantities
df["hospital_id"] = df["hospital_id"].astype(str)
df["insurer_id"] = df["insurer_id"].astype(str)

is_train = (df["visit_date"] < SPLIT_DATE).to_numpy()
train, test = df[is_train], df[~is_train]
X_train, X_test = train[FEATURES], test[FEATURES]
print(f"Train: {len(train):,} claims | Test: {len(test):,} claims (the unseen future)\n")

category_types = {c: pd.CategoricalDtype(sorted(train[c].unique())) for c in CATEGORICAL}


def for_boosting(X):
    X = X.copy()
    for c in CATEGORICAL:
        X[c] = X[c].astype(category_types[c])
    return X


def report(name, y_true, scores):
    auc = roc_auc_score(y_true, scores)
    avg_precision = average_precision_score(y_true, scores)
    top_n = int(len(scores) * 0.10)
    top_10 = np.argsort(-np.asarray(scores), kind="stable")[:top_n]   # the riskiest 10% of claims
    captured = y_true.to_numpy()[top_10].sum() / y_true.sum() * 100
    print(f"  {name:<28} AUC {auc:.3f} | avg precision {avg_precision:.3f} | top 10% catch {captured:.0f}%")


for target, label in [("is_rejected", "REJECTION (fully rejected)"),
                      ("is_shortfall", "SHORTFALL (rejected or partially approved)")]:
    y_train, y_test = train[target], test[target]
    print(f"{label}: {y_train.mean() * 100:.1f}% of training claims, {y_test.mean() * 100:.1f}% of test claims")

    report("Guessing at random", y_test, np.random.default_rng(0).random(len(y_test)))

    logit = make_pipeline(
        ColumnTransformer([("categories", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
                           ("numbers", StandardScaler(), NUMERIC)]),
        LogisticRegression(max_iter=1000),
    )
    logit.fit(X_train, y_train)
    report("Logistic regression", y_test, logit.predict_proba(X_test)[:, 1])

    boost = HistGradientBoostingClassifier(
        categorical_features="from_dtype", learning_rate=0.05, max_iter=400,
        max_leaf_nodes=31, min_samples_leaf=100, early_stopping=True,
        validation_fraction=0.1, n_iter_no_change=20, random_state=42,
    )
    boost.fit(for_boosting(X_train), y_train)
    report("Gradient boosting", y_test, boost.predict_proba(for_boosting(X_test))[:, 1])

    report("Ceiling (knows the rules)", y_test, ceiling[target][~is_train])

    joblib.dump({"model": boost, "category_types": category_types, "features": FEATURES},
                MODEL_DIR / f"{target}_model.joblib")
    print()

print(f"Models saved in {MODEL_DIR}")
