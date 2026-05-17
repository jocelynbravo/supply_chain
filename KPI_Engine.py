"""
kpi_engine.py  |  Supply Chain KPI Computation & Reporting
=============================================================
Reads from the SQLite database, computes all core KPIs, and
produces a printed report + matplotlib visualizations.

Usage:
    python analysis/kpi_engine.py
    python analysis/kpi_engine.py --save-charts
"""

import argparse
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

DB_PATH = "supply_chain.db"
CHART_DIR = Path("charts")

plt.rcParams.update({
    "font.family":      "monospace",
    "axes.spines.top":  False,
    "axes.spines.right":False,
    "figure.dpi":       120,
})

# ──────────────────────────────────────────────
# DB helpers
# ──────────────────────────────────────────────
def query(sql: str, params=()) -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    df  = pd.read_sql_query(sql, con, params=params)
    con.close()
    return df


# ──────────────────────────────────────────────
# KPI Calculations
# ──────────────────────────────────────────────
def calc_otif(days: int = 90) -> dict:
    df = query(f"""
        SELECT
            AVG(CASE WHEN received_date <= expected_date THEN 1.0 ELSE 0.0 END) AS on_time,
            AVG(CASE WHEN qty_received  >= qty_ordered   THEN 1.0 ELSE 0.0 END) AS in_full,
            AVG(CASE WHEN received_date <= expected_date
                      AND qty_received  >= qty_ordered   THEN 1.0 ELSE 0.0 END) AS otif,
            COUNT(*) AS n
        FROM orders
        WHERE status = 'received'
          AND order_date >= DATE('now', '-{days} days')
    """)
    row = df.iloc[0]
    return {
        "on_time_pct": round(row["on_time"]  * 100, 1),
        "in_full_pct": round(row["in_full"]  * 100, 1),
        "otif_rate":   round(row["otif"]     * 100, 1),
        "n_orders":    int(row["n"]),
    }


def calc_fill_rate(days: int = 90) -> pd.DataFrame:
    return query(f"""
        SELECT
            sku_id,
            SUM(qty_requested)  AS total_requested,
            SUM(qty_fulfilled)  AS total_fulfilled,
            ROUND(100.0 * SUM(qty_fulfilled) / MAX(SUM(qty_requested), 1), 1) AS fill_rate_pct
        FROM demand
        WHERE demand_date >= DATE('now', '-{days} days')
        GROUP BY sku_id
        ORDER BY fill_rate_pct ASC
    """)


def calc_stockout_rate() -> pd.DataFrame:
    return query("""
        SELECT
            i.sku_id,
            COUNT(*) AS total_days,
            SUM(CASE WHEN (i.qty_on_hand - i.qty_reserved) <= 0 THEN 1 ELSE 0 END) AS stockout_days,
            ROUND(100.0 *
                SUM(CASE WHEN (i.qty_on_hand - i.qty_reserved) <= 0 THEN 1 ELSE 0 END)
                / COUNT(*), 1) AS stockout_rate_pct
        FROM inventory i
        GROUP BY i.sku_id
        HAVING stockout_rate_pct > 0
        ORDER BY stockout_rate_pct DESC
        LIMIT 20
    """)


def calc_cycle_time() -> pd.DataFrame:
    return query("""
        SELECT
            sup.supplier_name,
            COUNT(o.order_id) AS orders,
            ROUND(AVG(JULIANDAY(o.received_date) - JULIANDAY(o.order_date)), 1) AS avg_cycle_days
        FROM orders o
        JOIN suppliers sup USING (supplier_id)
        WHERE o.status = 'received'
        GROUP BY sup.supplier_id
        ORDER BY avg_cycle_days
    """)


def calc_supplier_scorecard() -> pd.DataFrame:
    sql = Path("sql/03_supplier_scorecard.sql").read_text()
    return query(sql)


def calc_at_risk_skus() -> pd.DataFrame:
    return query("""
        SELECT
            i.sku_id,
            s.description,
            s.safety_stock,
            (i.qty_on_hand - i.qty_reserved) AS qty_available,
            s.reorder_point,
            CASE
                WHEN (i.qty_on_hand - i.qty_reserved) <= 0             THEN 'STOCKOUT'
                WHEN (i.qty_on_hand - i.qty_reserved) < s.safety_stock THEN 'CRITICAL'
                ELSE 'REORDER'
            END AS status
        FROM inventory i
        JOIN skus s USING (sku_id)
        WHERE i.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory)
          AND (i.qty_on_hand - i.qty_reserved) < s.reorder_point
        ORDER BY qty_available
        LIMIT 20
    """)


# ──────────────────────────────────────────────
# Charts
# ──────────────────────────────────────────────
def chart_otif_breakdown(kpi: dict, save: bool = False):
    labels = ["On-Time %", "In-Full %", "OTIF Rate"]
    values = [kpi["on_time_pct"], kpi["in_full_pct"], kpi["otif_rate"]]
    colors = ["#1D9E75", "#378ADD", "#7F77DD"]

    fig, ax = plt.subplots(figsize=(6, 3))
    bars = ax.barh(labels, values, color=colors, height=0.5)
    ax.set_xlim(0, 110)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.axvline(x=85, color="#D85A30", linestyle="--", linewidth=1, label="85% target")
    for bar, val in zip(bars, values):
        ax.text(val + 1, bar.get_y() + bar.get_height() / 2,
                f"{val}%", va="center", fontsize=10)
    ax.legend(fontsize=9)
    ax.set_title("OTIF Breakdown — Last 90 Days", fontsize=12)
    plt.tight_layout()
    if save:
        CHART_DIR.mkdir(exist_ok=True)
        plt.savefig(CHART_DIR / "otif_breakdown.png")
    plt.show()


def chart_supplier_scorecard(df: pd.DataFrame, save: bool = False):
    tier_colors = {
        "Preferred": "#1D9E75",
        "Approved":  "#378ADD",
        "Watch":     "#EF9F27",
        "At Risk":   "#E24B4A",
    }
    df = df.sort_values("composite_score")
    colors = [tier_colors.get(t, "#888780") for t in df["tier"]]

    fig, ax = plt.subplots(figsize=(7, max(4, len(df) * 0.4)))
    ax.barh(df["supplier_name"], df["composite_score"], color=colors, height=0.6)
    ax.set_xlim(0, 110)
    ax.axvline(x=85, color="#D85A30", linestyle="--", linewidth=1, alpha=0.7)
    ax.axvline(x=70, color="#EF9F27", linestyle="--", linewidth=1, alpha=0.7)
    for _, row in df.iterrows():
        ax.text(row["composite_score"] + 1, df.index[df["supplier_name"] == row["supplier_name"]].tolist()[0] if False else list(df["supplier_name"]).index(row["supplier_name"]),
                f"{row['composite_score']}", va="center", fontsize=9)
    ax.set_title("Supplier Scorecard", fontsize=12)
    ax.set_xlabel("Composite Score (0–100)")
    plt.tight_layout()
    if save:
        CHART_DIR.mkdir(exist_ok=True)
        plt.savefig(CHART_DIR / "supplier_scorecard.png")
    plt.show()


# ──────────────────────────────────────────────
# Report Printer
# ──────────────────────────────────────────────
def print_report(kpi, fill_df, stockout_df, cycle_df, at_risk_df, scorecard_df):
    overall_fill = round(fill_df["fill_rate_pct"].mean(), 1)
    overall_stockout = round(stockout_df["stockout_rate_pct"].mean(), 1) if len(stockout_df) > 0 else 0.0
    avg_cycle = round(cycle_df["avg_cycle_days"].mean(), 1)

    print()
    print("=" * 60)
    print("  SUPPLY CHAIN KPI REPORT")
    print("=" * 60)
    print(f"  OTIF Rate:          {kpi['otif_rate']}%")
    print(f"  On-Time Rate:       {kpi['on_time_pct']}%")
    print(f"  In-Full Rate:       {kpi['in_full_pct']}%")
    print(f"  Fill Rate (avg):    {overall_fill}%")
    print(f"  Stockout Rate:      {overall_stockout}%")
    print(f"  Avg Cycle Time:     {avg_cycle} days")
    print(f"  Orders Analyzed:    {kpi['n_orders']:,}")
    print("-" * 60)
    print(f"  At-Risk SKUs:       {len(at_risk_df)}")
    critical = at_risk_df[at_risk_df["status"] == "STOCKOUT"]
    print(f"  Stockouts:          {len(critical)}")
    print("-" * 60)
    if len(scorecard_df) > 0:
        best  = scorecard_df.iloc[0]
        worst = scorecard_df.iloc[-1]
        print(f"  Top Supplier:  {best['supplier_name']:<22}  Score: {best['composite_score']}/100")
        print(f"  Needs Work:    {worst['supplier_name']:<22}  Score: {worst['composite_score']}/100")
    print("=" * 60)
    print()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-charts", action="store_true")
    args = parser.parse_args()

    print("\nRunning KPI engine...")
    kpi          = calc_otif()
    fill_df      = calc_fill_rate()
    stockout_df  = calc_stockout_rate()
    cycle_df     = calc_cycle_time()
    at_risk_df   = calc_at_risk_skus()
    scorecard_df = calc_supplier_scorecard()

    print_report(kpi, fill_df, stockout_df, cycle_df, at_risk_df, scorecard_df)

    chart_otif_breakdown(kpi, save=args.save_charts)
    chart_supplier_scorecard(scorecard_df, save=args.save_charts)


if __name__ == "__main__":
    main()
