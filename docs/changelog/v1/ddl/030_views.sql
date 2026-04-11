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
WHERE l.status = 'released'
  AND l.available_qty > 0;

CREATE OR REPLACE VIEW pending_fulfillment_board AS
SELECT
    o.order_id,
    o.order_code,
    c.full_name AS customer_name,
    o.status,
    o.delivery_date_expected AS shipping_deadline
FROM sales_orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.status IN ('confirmed','allocated','packed','shipped');

CREATE OR REPLACE VIEW customer_360_view AS
SELECT
    c.customer_id,
    jsonb_build_object(
      'customerId', c.customer_id,
      'customerCode', c.customer_code,
      'fullName', c.full_name,
      'phone', c.phone,
      'status', c.status,
      'createdAt', c.created_at,
      'tags', c.tags,
      'channelSource', c.channel_source,
      'defaultAddress', c.default_address,
      'district', c.district,
      'province', c.province,
      'notes', c.notes,
      'lastOrderAt', c.last_order_at
    ) AS customer,
    COALESCE(
      (
        SELECT jsonb_agg(
          jsonb_build_object(
            'preorderId', p.preorder_id,
            'preorderCode', p.preorder_code,
            'customerId', p.customer_id,
            'productSkuId', p.product_sku_id,
            'committedQty', p.committed_qty,
            'allocatedQty', p.allocated_qty,
            'deliveredQty', p.delivered_qty,
            'remainingQty', p.remaining_qty,
            'status', p.status,
            'startDate', p.start_date
          )
          ORDER BY p.created_at DESC, p.preorder_id DESC
        )
        FROM preorders p
        WHERE p.customer_id = c.customer_id
          AND p.status = 'active'
      ),
      '[]'::jsonb
    ) AS active_preorders,
    COALESCE(
      (
        SELECT jsonb_agg(
          jsonb_build_object(
            'orderId', o.order_id,
            'orderCode', o.order_code,
            'customerId', o.customer_id,
            'orderDate', o.order_date,
            'channel', o.channel,
            'status', o.status,
            'paymentStatus', o.payment_status,
            'deliveryDateExpected', o.delivery_date_expected,
            'shippingAddress', o.shipping_address,
            'note', o.note,
            'createdBy', o.created_by,
            'sourcePreorderFlag', o.source_preorder_flag,
            'lines', COALESCE(
              (
                SELECT jsonb_agg(
                  jsonb_build_object(
                    'orderLineId', sol.order_line_id,
                    'productSkuId', sol.product_sku_id,
                    'orderedQty', sol.ordered_qty,
                    'allocatedQty', sol.allocated_qty,
                    'packedQty', sol.packed_qty,
                    'deliveredQty', sol.delivered_qty,
                    'unit', sol.unit,
                    'status', sol.status,
                    'sourcePreorderId', sol.source_preorder_id
                  )
                  ORDER BY sol.order_line_id
                )
                FROM sales_order_lines sol
                WHERE sol.order_id = o.order_id
              ),
              '[]'::jsonb
            )
          )
          ORDER BY o.created_at DESC, o.order_id DESC
        )
        FROM (
          SELECT *
          FROM sales_orders
          WHERE customer_id = c.customer_id
          ORDER BY created_at DESC, order_id DESC
          LIMIT 10
        ) o
      ),
      '[]'::jsonb
    ) AS recent_orders,
    COALESCE(
      (
        SELECT jsonb_agg(
          jsonb_build_object(
            'preferenceType', cp.preference_type,
            'preferenceValue', cp.preference_value,
            'confidenceLevel', cp.confidence_level
          )
          ORDER BY cp.updated_at DESC, cp.preference_type, cp.preference_value
        )
        FROM customer_preferences cp
        WHERE cp.customer_id = c.customer_id
      ),
      '[]'::jsonb
    ) AS preferences
FROM customers c;

CREATE OR REPLACE VIEW farm_summary_board AS
SELECT
  p.plot_id,
  p.plot_code,
  p.name AS plot_name,
  p.location_text,
  p.area_value,
  p.area_unit,
  p.status AS plot_status,
  c.crop_cycle_id,
  c.crop_name,
  c.growth_stage,
  c.status AS crop_cycle_status,
  c.expected_harvest_from,
  c.expected_harvest_to,
  c.estimated_yield_qty
FROM plots p
LEFT JOIN crop_cycles c
  ON c.plot_id = p.plot_id
   AND c.status NOT IN ('closed', 'cancelled');
