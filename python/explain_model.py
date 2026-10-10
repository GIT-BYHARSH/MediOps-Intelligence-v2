"""Explain the trained models: which inputs matter most?
Method: permutation importance. Shuffle one input column at a time on the unseen test
claims and measure how much the model's AUC drops. A big drop = the model relied on it."""
import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.inspection import permutation_importance

from db import PROJECT_ROOT

DATA_PATH = PROJECT_ROOT / "data" / "processed" / "ml_features.csv"
MODEL_DIR = PROJECT_ROOT / "ai" / "models"
CHART_PATH = PROJECT_ROOT / "assets" / "charts" / "05_model_drivers.png"
SPLIT_DATE = "2025-07-01"
BLUE, RED, GREY = "#1f4e79", "#c0392b", "#b0b7bf"

df = pd.read_csv(DATA_PATH, parse_dates=["visit_date"])
df["is_shortfall"] = (df["claim_status"] != "Approved").astype(int)
df["hospital_id"] = df["hospital_id"].astype(str)
df["insurer_id"] = df["insurer_id"].astype(str)

# A 30,000-claim sample of the unseen future keeps this fast
test = df[df["visit_date"] >= SPLIT_DATE].sample(30_000, random_state=42)

plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "axes.titleweight": "bold",
                     "axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

for ax, (target, title) in zip(axes, [("is_rejected", "What drives full REJECTION"),
                                       ("is_shortfall", "What drives SHORTFALL (paid less than claimed)")]):
    bundle = joblib.load(MODEL_DIR / f"{target}_model.joblib")
    model, category_types, features = bundle["model"], bundle["category_types"], bundle["features"]

    X = test[features].copy()
    for column, dtype in category_types.items():
        X[column] = X[column].astype(dtype)

    result = permutation_importance(model, X, test[target], scoring="roc_auc",
                                    n_repeats=3, random_state=42, n_jobs=1)
    importance = pd.Series(result.importances_mean, index=features).sort_values(ascending=False)

    print(f"\n{title}: top 8 inputs (AUC drop when shuffled)")
    print(importance.head(8).round(4).to_string())

    top = importance.head(8).iloc[::-1]
    ax.barh(top.index, top.values, color=[RED if v > 0.005 else GREY for v in top.values])
    ax.set_title(title)
    ax.set_xlabel("Drop in AUC when this input is shuffled")

fig.tight_layout()
fig.savefig(CHART_PATH, dpi=150, bbox_inches="tight")
print(f"\nSaved chart to {CHART_PATH}")
