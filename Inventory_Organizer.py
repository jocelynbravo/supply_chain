"""
inventory_optimizer.py  |  EOQ & Safety Stock Optimization
=============================================================
Reads SKU demand history from SQLite, computes optimal
reorder quantities and safety stock levels per SKU, and
flags SKUs where current parameters are suboptimal.

Usage:
    python analysis/inventory_optimizer.py
    python analysis/inventory_optimizer.py --export results/inventory_recs.csv
"""

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DB_PATH = "supply_chain.db"

# Cost assumptions (can be overridden per SKU in production)
ORDERING_COST_PER_ORDER = 35.0   # $ fixed cost per purchase order
HOLDING_COST_RATE       = 0.25   # 25% of unit cost per year
SERVICE_LEVEL           = 0.95   # 95% → z = 1.645
Z_SCORE                 = stats.norm.ppf(SERVICE_LEVEL)


# ──────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    con = sqlite3.connect(DB_PATH)
    skus = pd.read_sql("SELECT * FROM skus", con)
    demand = pd.read_sql("""
        SELECT sku_id, demand_date, qty_requested, qty_fulfilled
        FROM demand
        ORDER BY sku_id, demand_date
    """, con)
    con.close()
    return skus, demand


# ──────────────────────────────────────────────
# Demand forecasting (exponential smoothing)
# ──────────────────────────────────────────────
def exponential_smoothing(series: pd.Series, alpha: float = 0.3) -> float:
    """Return one-step-ahead forecast from Holt's simple exponential smoothing."""
    if len(series) == 0:
        return 0.0
    s = float(series.iloc[0])
    for obs in series.iloc[1:]:
        s = alpha * obs + (1 - alpha) * s
    return s


def demand_stats(demand_df: pd.DataFrame) -> pd.DataFrame:
    """Compute weekly demand mean, std, and forecast per SKU."""
    # Resample to weekly totals
    demand_df["demand_date"] = pd.to_datetime(demand_df["demand_date"])
    weekly = (
        demand_df
        .groupby(["sku_id", pd.Grouper(key="demand_date", freq="W")])
        ["qty_requested"]
        .sum()
        .reset_index()
    )

    records = []
    for sku_id, grp in weekly.groupby("sku_id"):
        series = grp["qty_requested"]
        records.append({
            "sku_id":          sku_id,
            "weekly_mean":     round(series.mean(), 2),
            "weekly_std":      round(series.std(ddof=1) if len(series) > 1 else 0.0, 2),
            "weekly_forecast": round(exponential_smoothing(series), 2),
            "annual_demand":   round(series.mean() * 52, 0),
            "n_weeks":         len(series),
        })
    return pd.DataFrame(records)


# ──────────────────────────────────────────────
# EOQ & Safety Stock
# ──────────────────────────────────────────────
def compute_eoq(annual_demand: float, unit_cost: float) -> int:
    """Economic Order Quantity."""
    if annual_demand <= 0 or unit_cost <= 0:
        return 0
    H   = HOLDING_COST_RATE * unit_cost
    eoq = np.sqrt(2 * annual_demand * ORDERING_COST_PER_ORDER / H)
    return max(1, int(round(eoq)))


def compute_safety_stock(weekly_std: float, lead_time_weeks: float) -> int:
    """Safety stock = Z × σ_demand × √(lead time)."""
    ss = Z_SCORE * weekly_std * np.sqrt(lead_time_weeks)
    return max(0, int(np.ceil(ss)))


def compute_reorder_point(weekly_mean: float, lead_time_weeks: float,
                           safety_stock: int) -> int:
    """ROP = (weekly_mean × lead_time_weeks) + safety_stock."""
    return int(np.ceil(weekly_mean * lead_time_weeks)) + safety_stock


def compute_annual_holding_cost(eoq: int, unit_cost: float) -> float:
    """Avg inventory = EOQ / 2; holding cost = avg_inv × H."""
    return round((eoq / 2) * HOLDING_COST_RATE * unit_cost, 2)


def compute_annual_ordering_cost(annual_demand: float, eoq: int) -> float:
    """Annual ordering cost = (D / EOQ) × S."""
    if eoq <= 0:
        return 0.0
    return round((annual_demand / eoq) * ORDERING_COST_PER_ORDER, 2)


# ──────────────────────────────────────────────
# Delta vs current parameters
# ──────────────────────────────────────────────
def flag_discrepancies(recs: pd.DataFrame, skus: pd.DataFrame) -> pd.DataFrame:
    merged = recs.merge(
        skus[["sku_id", "eoq", "safety_stock", "reorder_point", "unit_cost"]],
        on="sku_id",
        suffixes=("_recommended", "_current"),
    )
    merged["eoq_delta"]    = merged["eoq_recommended"]    - merged["eoq_current"]
    merged["ss_delta"]     = merged["ss_recommended"]     - merged["safety_stock"]
    merged["rop_delta"]    = merged["rop_recommended"]    - merged["reorder_point"]

    def flag(row):
        flags = []
        if abs(row["eoq_delta"]) > 0.15 * row["eoq_current"]:
            flags.append("EOQ_DRIFT")
        if row["ss_delta"] < -5:
            flags.append("OVERSTOCK_RISK")
        if row["ss_delta"] > 5:
            flags.append("UNDERSTOCK_RISK")
        if row["rop_delta"] < -10:
            flags.append("ROP_TOO_HIGH")
        return ", ".join(flags) if flags else "OK"

    merged["recommendation"] = merged.apply(flag, axis=1)
    return merged


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", default=None, help="Path to save CSV output")
    args = parser.parse_args()

    print("\nLoading data...")
    skus, demand_df = load_data()
    print(f"  {len(skus)} SKUs | {len(demand_df):,} demand rows")

    print("Computing demand statistics...")
    stats_df = demand_stats(demand_df)

    print("Computing optimal inventory parameters...")
    records = []
    for _, row in stats_df.iterrows():
        sku_row = skus[skus["sku_id"] == row["sku_id"]]
        if sku_row.empty:
            continue
        sku = sku_row.iloc[0]

        lead_time_weeks = max(1, round(7 / 7, 2))  # placeholder 1 week; use supplier table in prod
        eoq      = compute_eoq(row["annual_demand"], sku["unit_cost"])
        ss       = compute_safety_stock(row["weekly_std"], lead_time_weeks)
        rop      = compute_reorder_point(row["weekly_mean"], lead_time_weeks, ss)
        hold_c   = compute_annual_holding_cost(eoq, sku["unit_cost"])
        order_c  = compute_annual_ordering_cost(row["annual_demand"], eoq)

        records.append({
            "sku_id":              row["sku_id"],
            "weekly_mean":         row["weekly_mean"],
            "weekly_forecast":     row["weekly_forecast"],
            "annual_demand":       row["annual_demand"],
            "eoq_recommended":     eoq,
            "ss_recommended":      ss,
            "rop_recommended":     rop,
            "annual_holding_cost": hold_c,
            "annual_ordering_cost":order_c,
            "total_annual_cost":   round(hold_c + order_c, 2),
        })

    recs_df = pd.DataFrame(records)
    final   = flag_discrepancies(recs_df, skus)

    # Summary
    n_ok      = (final["recommendation"] == "OK").sum()
    n_flagged = len(final) - n_ok
    print()
    print("=" * 60)
    print("  INVENTORY OPTIMIZATION SUMMARY")
    print("=" * 60)
    print(f"  SKUs analyzed:         {len(final)}")
    print(f"  Parameters OK:         {n_ok}")
    print(f"  Need adjustment:       {n_flagged}")
    print(f"  Avg EOQ (recommended): {int(recs_df['eoq_recommended'].mean())}")
    print(f"  Avg Safety Stock:      {int(recs_df['ss_recommended'].mean())}")
    print(f"  Est. Annual Inv Cost:  ${recs_df['total_annual_cost'].sum():,.0f}")
    print("=" * 60)

    flagged = final[final["recommendation"] != "OK"][
        ["sku_id", "eoq_recommended", "eoq_current", "ss_recommended",
         "safety_stock", "recommendation"]
    ].head(15)
    if len(flagged) > 0:
        print("\nTop flagged SKUs:")
        print(flagged.to_string(index=False))

    if args.export:
        Path(args.export).parent.mkdir(parents=True, exist_ok=True)
        final.to_csv(args.export, index=False)
        print(f"\n  Exported → {args.export}")

    print()


if __name__ == "__main__":
    main()
