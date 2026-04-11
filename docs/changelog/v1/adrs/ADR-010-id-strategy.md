# ADR-005: ID Strategy — UUID cho Machine ID, Sequential Code cho Human-Readable

**Status:** Accepted
**Date:** 2026-04-10
**Deciders:** Architecture team

---

## Context

Cần 2 loại identifier khác nhau:
1. **Machine ID**: để join tables, foreign keys, API paths — ưu tiên uniqueness và performance
2. **Human code**: để hiển thị trong Zalo, báo cáo, invoice — ưu tiên readability và memorability

Không được dùng UUID substring (`CUST-a3f2b1c4`) làm human code vì:
- Không meaningful với business users
- Không sortable theo thời gian
- Không dễ nhớ hay verify qua điện thoại

## Decision

**Machine IDs:** UUID thuần (v4), không có prefix, không có type encoding.
```
customerId: "550e8400-e29b-41d4-a716-446655440000"
orderId:    "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
```

**Human codes:** Format `{PREFIX}-{YYYYMM}-{SEQ}` hoặc biến thể theo domain:

| Entity | Prefix | Format | Ví dụ |
|--------|--------|--------|-------|
| Customer | KH | KH-YYYYMM-NNNN | KH-202604-0001 |
| Preorder | DT | DT-YYYYMM-NNNN | DT-202604-0001 |
| Order | ORD | ORD-YYYYMM-NNNN | ORD-202604-0001 |
| Lot | LOT | LOT-{SKU_ABBR}-YYYYMM-NNN | LOT-DAU-202604-001 |
| Plot | VU | VU-NNN | VU-001 |
| CropCycle | — | VU-NNN-YYYY{A\|B\|C} | VU-001-2026A |

**Sequence tracking:**
- Phase 1: `len(store_for_entity_this_month) + 1` (in-memory, acceptable)
- Phase 2: PostgreSQL sequence per `(entity_type, year_month)` table

## Consequences

- `core/codegen.py` là nơi duy nhất chứa code generation logic
- Các services không được tự generate code — phải gọi `codegen.*`
- Human code phải unique trong cùng `(entity_type, year_month)` — collision resolution ở Phase 2
- Khi rename prefix hoặc thay format: tạo ADR mới, không silent change

## Migration note

Code format hiện tại (`CUST-{uuid[:8]}`, `ORD-{uuid[:8]}`, etc.) sẽ được replace trong Feature 2
của technical baseline sprint. Existing records với old format giữ nguyên để không break API consumers.
