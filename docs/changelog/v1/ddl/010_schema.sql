-- 010_schema.sql
-- Deterministic core schema for Agri OS v1
-- Note: accounting final remains in ERP. This schema focuses on operational truth.

BEGIN;

CREATE TABLE IF NOT EXISTS customers (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    channel_source TEXT,
    default_address TEXT,
    district TEXT,
    province TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','blocked')),
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    last_order_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_preferences (
    preference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    preference_type TEXT NOT NULL,
    preference_value TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'human' CHECK (source IN ('human','integration','ai_suggestion')),
    confidence_level NUMERIC(4,3) NOT NULL DEFAULT 1.000 CHECK (confidence_level >= 0 AND confidence_level <= 1),
    confirmed_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_skus (
    product_sku_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku_code TEXT NOT NULL UNIQUE,
    sku_name TEXT NOT NULL,
    category TEXT,
    unit TEXT NOT NULL,
    pack_size TEXT,
    default_price NUMERIC(18,2),
    is_preorder_supported BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS preorders (
    preorder_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    preorder_code TEXT NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customers(customer_id),
    product_sku_id UUID NOT NULL REFERENCES product_skus(product_sku_id),
    committed_qty NUMERIC(18,3) NOT NULL CHECK (committed_qty > 0),
    allocated_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (allocated_qty >= 0),
    delivered_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (delivered_qty >= 0),
    remaining_qty NUMERIC(18,3) NOT NULL CHECK (remaining_qty >= 0),
    delivery_cadence TEXT,
    deposit_amount NUMERIC(18,2),
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','confirmed','active','completed','cancelled')),
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS plots (
    plot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plot_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    location_text TEXT,
    area_value NUMERIC(18,3) NOT NULL,
    area_unit TEXT NOT NULL,
    owner_name TEXT,
    manager_user_id TEXT,
    geo_lat NUMERIC(10,7),
    geo_lng NUMERIC(10,7),
    soil_note TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crop_cycles (
    crop_cycle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plot_id UUID NOT NULL REFERENCES plots(plot_id),
    crop_name TEXT NOT NULL,
    start_date DATE NOT NULL,
    growth_stage TEXT NOT NULL CHECK (growth_stage IN ('seeded','growing','flowering_or_maturing','harvest_window','harvested')),
    status TEXT NOT NULL CHECK (status IN ('planned','active','near_harvest','harvested','closed','cancelled')),
    expected_harvest_from TIMESTAMPTZ,
    expected_harvest_to TIMESTAMPTZ,
    estimated_yield_qty NUMERIC(18,3),
    actual_yield_qty NUMERIC(18,3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lots (
    lot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_code TEXT NOT NULL UNIQUE,
    product_sku_id UUID NOT NULL REFERENCES product_skus(product_sku_id),
    source_type TEXT NOT NULL CHECK (source_type IN ('crop_cycle','processing_batch','purchase_inbound')),
    source_ref_id TEXT NOT NULL,
    harvest_or_production_date TIMESTAMPTZ NOT NULL,
    actual_qty NUMERIC(18,3) NOT NULL CHECK (actual_qty > 0),
    available_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (available_qty >= 0),
    reserved_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
    released_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (released_qty >= 0),
    quality_note TEXT,
    status TEXT NOT NULL CHECK (status IN ('draft','harvested','qc_pending','released','blocked','depleted','closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lot_evidence (
    lot_evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id UUID NOT NULL REFERENCES lots(lot_id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('photo','video','checklist','note','document','measurement')),
    object_storage_key TEXT,
    text_value TEXT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (object_storage_key IS NOT NULL OR text_value IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS qc_reviews (
    qc_review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id UUID NOT NULL REFERENCES lots(lot_id) ON DELETE CASCADE,
    checklist_version TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('pending','passed','failed','needs_more_evidence')),
    reviewer_id TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_code TEXT NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customers(customer_id),
    channel TEXT NOT NULL CHECK (channel IN ('web','admin','zalo','facebook','phone')),
    order_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivery_date_expected TIMESTAMPTZ,
    shipping_address TEXT,
    payment_intent TEXT,
    note TEXT,
    status TEXT NOT NULL CHECK (status IN ('draft','confirmed','allocated','partially_allocated','packed','partially_packed','shipped','delivered','partially_delivered','cancel_requested','cancelled','failed')),
    payment_status TEXT NOT NULL DEFAULT 'unpaid' CHECK (payment_status IN ('unpaid','partially_paid','paid','refunded','writeoff')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales_order_lines (
    order_line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES sales_orders(order_id) ON DELETE CASCADE,
    product_sku_id UUID NOT NULL REFERENCES product_skus(product_sku_id),
    ordered_qty NUMERIC(18,3) NOT NULL CHECK (ordered_qty > 0),
    allocated_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (allocated_qty >= 0),
    packed_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (packed_qty >= 0),
    delivered_qty NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (delivered_qty >= 0),
    unit TEXT NOT NULL,
    source_preorder_id UUID REFERENCES preorders(preorder_id),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','allocated','packed','delivered','cancelled'))
);

CREATE TABLE IF NOT EXISTS allocations (
    allocation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_line_id UUID NOT NULL REFERENCES sales_order_lines(order_line_id) ON DELETE CASCADE,
    lot_id UUID NOT NULL REFERENCES lots(lot_id),
    allocated_qty NUMERIC(18,3) NOT NULL CHECK (allocated_qty > 0),
    status TEXT NOT NULL CHECK (status IN ('active','released','consumed','cancelled')),
    allocated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    inventory_movement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id UUID NOT NULL REFERENCES lots(lot_id),
    movement_type TEXT NOT NULL CHECK (
        movement_type IN (
            'release','reserve','release_reservation','consume','adjustment','discard','return'
        )
    ),
    qty NUMERIC(18,3) NOT NULL CHECK (qty > 0),
    related_order_id UUID REFERENCES sales_orders(order_id),
    related_order_line_id UUID REFERENCES sales_order_lines(order_line_id),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS external_mappings (
    external_mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_system TEXT NOT NULL,
    external_object_type TEXT NOT NULL,
    external_object_id TEXT NOT NULL,
    internal_object_type TEXT NOT NULL,
    internal_object_id TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending' CHECK (sync_status IN ('pending','synced','failed','needs_review')),
    last_synced_at TIMESTAMPTZ,
    last_error TEXT,
    UNIQUE (external_system, external_object_type, external_object_id)
);

CREATE TABLE IF NOT EXISTS channel_identity_bindings (
    binding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_type TEXT NOT NULL CHECK (channel_type IN ('phone','zalo','facebook','email')),
    channel_value TEXT NOT NULL,
    customer_id UUID REFERENCES customers(customer_id) ON DELETE CASCADE,
    confidence_level NUMERIC(4,3) NOT NULL DEFAULT 1.000 CHECK (confidence_level >= 0 AND confidence_level <= 1),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','candidate','rejected')),
    UNIQUE (channel_type, channel_value)
);

CREATE TABLE IF NOT EXISTS domain_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_name TEXT NOT NULL,
    event_version INTEGER NOT NULL DEFAULT 1,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_type TEXT NOT NULL CHECK (actor_type IN ('user','system','agent','integration')),
    actor_id TEXT,
    correlation_id TEXT,
    causation_id TEXT,
    idempotency_key TEXT,
    source TEXT NOT NULL DEFAULT 'core' CHECK (source IN ('core','integration','system_job','agent')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id TEXT,
    actor_role TEXT,
    action_name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('allowed','denied','escalated','failed')),
    reason_code TEXT,
    before_snapshot JSONB,
    after_snapshot JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    operation_name TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_snapshot JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

COMMIT;
