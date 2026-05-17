-- ============================================================
-- 02_kpi_queries.sql  |  Core Supply Chain KPI Calculations
-- ============================================================


-- ─────────────────────────────────────────
-- 1. OTIF Rate (On-Time In-Full)
--    On-time  = received_date <= expected_date
--    In-full  = qty_received  >= qty_ordered
-- ─────────────────────────────────────────
WITH otif_base AS (
    SELECT
        order_id,
        CASE WHEN received_date <= expected_date THEN 1 ELSE 0 END AS on_time,
        CASE WHEN qty_received  >= qty_ordered   THEN 1 ELSE 0 END AS in_full
    FROM orders
    WHERE status = 'received'
      AND order_date >= DATE('now', '-90 days')
)
SELECT
    COUNT(*)                                            AS total_orders,
    ROUND(AVG(on_time)  * 100, 1)                      AS on_time_pct,
    ROUND(AVG(in_full)  * 100, 1)                      AS in_full_pct,
    ROUND(AVG(on_time * in_full) * 100, 1)             AS otif_rate
FROM otif_base;


-- ─────────────────────────────────────────
-- 2. Fill Rate (demand fulfillment)
-- ─────────────────────────────────────────
SELECT
    sku_id,
    SUM(qty_requested)                                  AS total_requested,
    SUM(qty_fulfilled)                                  AS total_fulfilled,
    ROUND(
        100.0 * SUM(qty_fulfilled) / NULLIF(SUM(qty_requested), 0)
    , 1)                                                AS fill_rate_pct
FROM demand
WHERE demand_date >= DATE('now', '-90 days')
GROUP BY sku_id
ORDER BY fill_rate_pct ASC;


-- ─────────────────────────────────────────
-- 3. Stockout Rate
--    Days where qty_available = 0 / total snapshot days
-- ─────────────────────────────────────────
SELECT
    i.sku_id,
    s.description,
    COUNT(*)                                            AS snapshot_days,
    SUM(CASE WHEN i.qty_available <= 0 THEN 1 ELSE 0 END) AS stockout_days,
    ROUND(
        100.0 * SUM(CASE WHEN i.qty_available <= 0 THEN 1 ELSE 0 END)
              / COUNT(*)
    , 1)                                                AS stockout_rate_pct
FROM inventory i
JOIN skus s USING (sku_id)
WHERE i.snapshot_date >= DATE('now', '-90 days')
GROUP BY i.sku_id
HAVING stockout_rate_pct > 0
ORDER BY stockout_rate_pct DESC;


-- ─────────────────────────────────────────
-- 4. Average Order Cycle Time (days)
-- ─────────────────────────────────────────
SELECT
    sup.supplier_name,
    COUNT(o.order_id)                                   AS orders,
    ROUND(AVG(
        JULIANDAY(o.received_date) - JULIANDAY(o.order_date)
    ), 1)                                               AS avg_cycle_days,
    MIN(JULIANDAY(o.received_date) - JULIANDAY(o.order_date)) AS min_days,
    MAX(JULIANDAY(o.received_date) - JULIANDAY(o.order_date)) AS max_days
FROM orders o
JOIN suppliers sup USING (supplier_id)
WHERE o.status = 'received'
  AND o.order_date >= DATE('now', '-180 days')
GROUP BY sup.supplier_id
ORDER BY avg_cycle_days;


-- ─────────────────────────────────────────
-- 5. At-Risk SKUs (below safety stock level)
-- ─────────────────────────────────────────
SELECT
    i.sku_id,
    s.description,
    s.category,
    s.safety_stock,
    i.qty_available,
    s.reorder_point,
    CASE
        WHEN i.qty_available <= 0             THEN 'STOCKOUT'
        WHEN i.qty_available < s.safety_stock THEN 'CRITICAL'
        WHEN i.qty_available < s.reorder_point THEN 'REORDER NOW'
        ELSE 'OK'
    END                                                 AS status
FROM inventory i
JOIN skus s USING (sku_id)
WHERE i.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory)
  AND i.qty_available < s.reorder_point
ORDER BY
    CASE WHEN i.qty_available <= 0 THEN 0
         WHEN i.qty_available < s.safety_stock THEN 1
         ELSE 2 END,
    i.qty_available;


-- ─────────────────────────────────────────
-- 6. Spend Analysis — rolling 12 months
-- ─────────────────────────────────────────
SELECT
    sup.supplier_name,
    sup.category,
    sup.region,
    COUNT(DISTINCT o.order_id)                          AS order_count,
    SUM(o.qty_ordered * o.unit_cost)                   AS total_spend,
    ROUND(
        100.0 * SUM(o.qty_ordered * o.unit_cost)
              / SUM(SUM(o.qty_ordered * o.unit_cost)) OVER ()
    , 2)                                                AS spend_share_pct
FROM orders o
JOIN suppliers sup USING (supplier_id)
WHERE o.order_date >= DATE('now', '-365 days')
GROUP BY sup.supplier_id
ORDER BY total_spend DESC;
