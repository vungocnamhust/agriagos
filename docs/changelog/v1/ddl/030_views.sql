-- 030_views.sql
-- Lightweight operational views for deterministic core

CREATE OR REPLACE VIEW available_lots_board AS
SELECT
    l.lot_id,
    l.lot_code,
    l.product_sku_id,
    p.sku_code,
    p.sku_name,
    l.released_qty,
    l.available_qty,
    l.status,
    l.harvest_or_production_date
FROM lots l
JOIN product_skus p ON p.product_sku_id = l.product_sku_id
WHERE l.status = 'released';

CREATE OR REPLACE VIEW pending_fulfillment_board AS
SELECT
    o.order_id,
    o.order_code,
    c.full_name AS customer_name,
    o.status,
    o.delivery_date_expected AS shipping_deadline
FROM sales_orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.status IN ('confirmed','allocated','partially_allocated','packed','partially_packed','shipped');

CREATE OR REPLACE VIEW customer_360_view AS
SELECT
    c.customer_id,
    c.customer_code,
    c.full_name,
    c.phone,
    c.tags,
    c.last_order_at,
    (
      SELECT COUNT(*) FROM sales_orders o WHERE o.customer_id = c.customer_id
    ) AS total_orders,
    (
      SELECT COUNT(*) FROM preorders p WHERE p.customer_id = c.customer_id AND p.status IN ('confirmed','active')
    ) AS active_preorders
FROM customers c;
