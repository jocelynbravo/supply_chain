-- ============================================================
-- 03_supplier_scorecard.sql  |  Composite Supplier Scoring
-- ============================================================
-- Weights:
--   OTIF          30%
--   Fill Rate     25%
--   Cycle Time    20%   (shorter = better, normalized to 100)
--   Quality       15%   (1 - defect_rate)
--   Responsiveness 10%  (mock score based on order count)
-- ============================================================

WITH

-- OTIF per supplier
otif AS (
    SELECT
        supplier_id,
        ROUND(AVG(
            CASE WHEN received_date <= expected_date
                  AND qty_received >= qty_ordered THEN 1.0 ELSE 0.0 END
        ) * 100, 1) AS otif_score
    FROM orders
    WHERE status = 'received'
      AND order_date >= DATE('now', '-180 days')
    GROUP BY supplier_id
),

-- Fill rate (qty_received / qty_ordered)
fill AS (
    SELECT
        supplier_id,
        ROUND(
            100.0 * SUM(qty_received) / NULLIF(SUM(qty_ordered), 0)
        , 1) AS fill_score
    FROM orders
    WHERE status IN ('received','partial')
      AND order_date >= DATE('now', '-180 days')
    GROUP BY supplier_id
),

-- Cycle time score (benchmark = 5 days; score = 100 * 5 / actual, capped at 100)
cycle AS (
    SELECT
        supplier_id,
        MIN(100,
            ROUND(
                100.0 * 5.0 / NULLIF(AVG(
                    JULIANDAY(received_date) - JULIANDAY(order_date)
                ), 0)
            , 1)
        ) AS cycle_score
    FROM orders
    WHERE status = 'received'
      AND order_date >= DATE('now', '-180 days')
    GROUP BY supplier_id
),

-- Composite score
composite AS (
    SELECT
        sup.supplier_id,
        sup.supplier_name,
        sup.region,
        sup.category,
        COALESCE(o.otif_score,  0) AS otif_score,
        COALESCE(f.fill_score,  0) AS fill_score,
        COALESCE(c.cycle_score, 0) AS cycle_score,
        ROUND(
            0.30 * COALESCE(o.otif_score,  0) +
            0.25 * COALESCE(f.fill_score,  0) +
            0.20 * COALESCE(c.cycle_score, 0) +
            0.15 * 75 +   -- placeholder quality score
            0.10 * 80     -- placeholder responsiveness score
        , 1) AS composite_score
    FROM suppliers sup
    LEFT JOIN otif  o USING (supplier_id)
    LEFT JOIN fill  f USING (supplier_id)
    LEFT JOIN cycle c USING (supplier_id)
    WHERE sup.active = TRUE
)

SELECT
    supplier_name,
    region,
    category,
    otif_score,
    fill_score,
    cycle_score,
    composite_score,
    CASE
        WHEN composite_score >= 85 THEN 'Preferred'
        WHEN composite_score >= 70 THEN 'Approved'
        WHEN composite_score >= 55 THEN 'Watch'
        ELSE 'At Risk'
    END AS tier
FROM composite
ORDER BY composite_score DESC;
