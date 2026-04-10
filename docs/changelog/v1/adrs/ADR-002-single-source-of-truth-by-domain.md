# ADR-002: Mỗi domain chỉ có một source of truth

## Status
Accepted

## Context
Các domain chính của hệ:
- customer identity
- preorder
- order
- lot
- allocation
- inventory movement
- plot/crop summary
- accounting final
- conversations

Nếu một domain có nhiều nguồn sự thật đồng thời, team sẽ khó debug, sync và audit.

## Decision
Chốt source of truth theo domain như sau:
- Customer identity canonical dùng cho giao dịch: Agri OS Core
- Preorder: Agri OS Core
- Order vận hành: Agri OS Core
- Lot / Allocation / Inventory movement: Agri OS Core
- Plot/Crop summary: Agri OS Core snapshot hoặc farm app theo phase
- Nông học sâu: farm app
- Accounting / journal final: ERP
- Conversations / campaign activity: CRM

## Consequences
### Tốt
- Rõ ownership
- Dễ sync
- Giảm shadow truth

### Xấu
- Phải chấp nhận có snapshot/read model ở hệ khác
- Cần rule conflict resolution khi sync
