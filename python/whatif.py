"""What-if simulator: change the team's hours, win chances, effort or staff cost and see recovery update.

Same logic as sql/analysis_05 and python/sensitivity_analysis.py, but fast enough for sliders.
Win chances and effort hours are ASSUMPTIONS (see docs/sensitivity_report.md).
"""
import numpy as np
import pandas as pd

from db import get_engine

REASONS = ["Incomplete Documents", "Coding Error", "Medical Necessity Not Met"]
BASE_WIN = np.array([0.70, 0.60, 0.35])
BASE_EFF = np.array([1.0, 2.0, 5.0])
STRATEGIES = ["Priority score", "Largest amount first", "Quickest first", "Random order"]
N_RANDOM = 5


def load_claims(engine=None):
    """Recoverable claims as numpy arrays (49,069 rows)."""
    df = pd.read_sql(
        "SELECT claim_id, rejection_reason, recoverable_amount FROM report_claim "
        "WHERE recoverable_amount IS NOT NULL ORDER BY claim_id",
        engine or get_engine(),
    )
    reason_idx = df["rejection_reason"].map({r: i for i, r in enumerate(REASONS)}).to_numpy()
    rng = np.random.default_rng(42)
    return {
        "claim_id": df["claim_id"].to_numpy(),
        "rec": df["recoverable_amount"].to_numpy(dtype=float),
        "reason_idx": reason_idx,
        "random_orders": [rng.permutation(len(df)) for _ in range(N_RANDOM)],
    }


def _recovered(order, hours, expected, budget):
    within = np.cumsum(hours[order]) <= budget
    return float(expected[order][within].sum())


def simulate(data, hours=10_000, win_multiplier=1.0, effort_multiplier=1.0, cost_per_hour=500.0):
    """Return a DataFrame: strategy, recovery in crore, times random, return per Rs 1 of staff cost.
    The team ranks AND is paid out using the same (adjusted) win chances and effort."""
    win = np.clip(BASE_WIN * win_multiplier, 0.01, 0.99)[data["reason_idx"]]
    eff = (BASE_EFF * effort_multiplier)[data["reason_idx"]]
    rec, cid = data["rec"], data["claim_id"]
    expected = rec * win
    orders = {
        "Priority score": np.lexsort((cid, -(expected / eff))),
        "Largest amount first": np.lexsort((cid, -rec)),
        "Quickest first": np.lexsort((cid, -rec, eff)),
    }
    out = {name: _recovered(o, eff, expected, hours) for name, o in orders.items()}
    out["Random order"] = float(np.mean([_recovered(p, eff, expected, hours) for p in data["random_orders"]]))
    cost = hours * cost_per_hour
    frame = pd.DataFrame({
        "strategy": STRATEGIES,
        "recovery_cr": [out[s] / 1e7 for s in STRATEGIES],
    })
    frame["times_random"] = frame["recovery_cr"] / frame.loc[frame["strategy"] == "Random order", "recovery_cr"].iloc[0]
    frame["return_per_rs1_cost"] = [out[s] / cost if cost > 0 else float("nan") for s in STRATEGIES]
    return frame
