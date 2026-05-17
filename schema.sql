-- ============================================================
-- 01_schema.sql  |  Supply Chain Analytics Database Schema
-- ============================================================

CREATE TABLE suppliers (
    supplier_id     TEXT PRIMARY KEY,
    supplier_name   TEXT NOT NULL,
    region          TEXT,
    category        TEXT,
    lead_time_days  INTEGER,
    active          BOOLEAN DEFAULT TRUE,
    onboarded_date  DATE
);

CREATE TABLE skus (
    sku_id          TEXT PRIMARY KEY,
    description     TEXT,
    category        TEXT,
    unit_cost       NUMERIC(10,2),
    reorder_point   INTEGER,
    eoq             INTEGER,
    safety_stock    INTEGER,
    supplier_id     TEXT REFERENCES suppliers(supplier_id)
);

CREATE TABLE orders (
    order_id        TEXT PRIMARY KEY,
    sku_id          TEXT REFERENCES skus(sku_id),
    supplier_id     TEXT REFERENCES suppliers(supplier_id),
    order_date      DATE NOT NULL,
    expected_date   DATE,
    received_date   DATE,
    qty_ordered     INTEGER,
    qty_received    INTEGER,
    unit_cost       NUMERIC(10,2),
    status          TEXT  -- 'pending','received','partial','cancelled'
);

CREATE TABLE inventory (
    snapshot_date   DATE,
    sku_id          TEXT REFERENCES skus(sku_id),
    qty_on_hand     INTEGER,
    qty_reserved    INTEGER,
    qty_available   INTEGER GENERATED ALWAYS AS (qty_on_hand - qty_reserved) STORED,
    PRIMARY KEY (snapshot_date, sku_id)
);

CREATE TABLE demand (
    demand_date     DATE,
    sku_id          TEXT REFERENCES skus(sku_id),
    qty_requested   INTEGER,
    qty_fulfilled   INTEGER,
    channel         TEXT,
    PRIMARY KEY (demand_date, sku_id)
);

-- Indexes for analytical query performance
CREATE INDEX idx_orders_date        ON orders(order_date);
CREATE INDEX idx_orders_supplier    ON orders(supplier_id);
CREATE INDEX idx_orders_sku         ON orders(sku_id);
CREATE INDEX idx_inventory_sku      ON inventory(sku_id);
CREATE INDEX idx_demand_date        ON demand(demand_date);
