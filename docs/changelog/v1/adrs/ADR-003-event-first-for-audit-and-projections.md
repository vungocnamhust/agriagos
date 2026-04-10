# ADR-003: Ghi event nghiệp vụ sớm để nuôi audit, projections và agent context

## Status
Accepted

## Context
Hệ cần:
- audit
- debug
- analytics
- projections theo role
- context cho agent về sau

Nếu chỉ update bảng trạng thái hiện tại mà không giữ event log, sau này rất khó lần lại flow.

## Decision
Dùng event log từ phase đầu ở mức app/outbox đơn giản.
Mọi workflow quan trọng phải sinh event nghiệp vụ rõ tên, ví dụ:
- CustomerCreated
- PreorderPlaced
- HarvestedLotCreated
- LotReleased
- OrderAllocated
- OrderPacked
- OrderDelivered
- CustomerPreferenceUpdated

## Consequences
### Tốt
- Debug tốt hơn
- Dễ build read models
- Sau này AI/agent có timeline nghiệp vụ đáng tin

### Xấu
- Tăng công thiết kế event payload
- Cần discipline trong naming và correlation ids
