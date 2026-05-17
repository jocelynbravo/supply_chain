# Supply Chain Analytics Portfolio

**End-to-end supply chain analysis system** — from raw transactional data to actionable KPI dashboards and inventory optimization recommendations.

---

## Project Overview

This project simulates a real-world supply chain analyst workflow across three interconnected modules:

| Module | Description | Skills |
|--------|-------------|--------|
| `01_data_pipeline` | ETL pipeline ingesting supplier, order, and inventory data | Python, SQL, Pandas |
| `02_kpi_dashboard` | KPI computation engine (OTIF, fill rate, stockout rate, cycle time) | Python, SQL, Matplotlib |
| `03_inventory_optimizer` | EOQ + safety stock optimizer with demand forecasting | NumPy, SciPy, SQL |

---

## Repository Structure

```
supply-chain-analyst/
│
├── data/
│   ├── orders.csv              # Simulated order transactions (10,000 rows)
│   ├── suppliers.csv           # Supplier master data
│   └── inventory.csv           # SKU-level inventory snapshot
│
├── sql/
│   ├── 01_schema.sql           # Database schema definition
│   ├── 02_kpi_queries.sql      # Core KPI calculations
│   └── 03_supplier_scorecard.sql  # Supplier performance scoring
│
├── analysis/
│   ├── etl_pipeline.py         # Data ingestion & cleaning
│   ├── kpi_engine.py           # KPI computation module
│   └── inventory_optimizer.py  # EOQ & safety stock model
│
├── notebooks/
│   └── supply_chain_analysis.ipynb  # End-to-end walkthrough notebook
│
└── README.md
```

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/supply-chain-analyst.git
cd supply-chain-analyst

# Install dependencies
pip install -r requirements.txt

# Generate synthetic data
python analysis/etl_pipeline.py --generate

# Run KPI engine
python analysis/kpi_engine.py

# Run inventory optimizer
python analysis/inventory_optimizer.py
```

---

## Key Metrics Computed

- **OTIF Rate** — On-Time In-Full delivery performance
- **Fill Rate** — % of demand fulfilled from available stock
- **Stockout Rate** — Frequency of zero-inventory events
- **Order Cycle Time** — Average order-to-delivery duration
- **Supplier Scorecard** — Composite performance index across 5 dimensions
- **EOQ** — Economic Order Quantity per SKU
- **Safety Stock** — Statistically optimal buffer inventory

---

## Methods & Models

### Demand Forecasting
Uses a 12-week rolling average with exponential smoothing (`α = 0.3`) to forecast demand and compute safety stock buffers.

### Inventory Optimization (EOQ)
```
EOQ = √(2DS / H)
  D = Annual demand
  S = Ordering cost per order
  H = Holding cost per unit per year
```

### Safety Stock
```
Safety Stock = Z × σ_LT × √(Lead Time)
  Z    = Service level z-score (1.645 for 95%)
  σ_LT = Standard deviation of lead time demand
```

---

## Tech Stack

- **Python 3.11** — Core analysis & modeling
- **SQLite / PostgreSQL** — Data storage & KPI queries
- **Pandas & NumPy** — Data wrangling & computation
- **SciPy** — Statistical modeling
- **Matplotlib & Seaborn** — Visualization
- **Jupyter** — Interactive exploration

---

## Sample Output

```
============================================================
  SUPPLY CHAIN KPI REPORT — Q3 2024
============================================================
  OTIF Rate:          87.4%   ▲ +2.1% vs Q2
  Fill Rate:          94.2%   ▲ +0.8% vs Q2
  Stockout Rate:       3.1%   ▼ -1.4% vs Q2
  Avg Cycle Time:     4.7 days
  Active SKUs:          248
  At-Risk SKUs:          19   (below safety stock)
============================================================
  Top Supplier:    Apex Industrial     Score: 91/100
  Worst Supplier:  Global Parts Co.    Score: 58/100
============================================================
```
