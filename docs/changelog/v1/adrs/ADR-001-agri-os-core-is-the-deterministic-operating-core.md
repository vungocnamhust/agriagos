# ADR-001: Agri OS Core là deterministic operating core

## Status
Accepted

## Context
Hệ thống cần đi từ thực tế: quản lý khách hàng, preorder, order, lot, inventory, plot/crop cơ bản và phân quyền trước.
Nếu dồn toàn bộ logic vào ERP, CRM hoặc farm app thì workflow liên thông sẽ rất khó kiểm soát.
Nếu để AI/agent đứng giữa quá sớm thì source of truth sẽ mơ hồ.

## Decision
Dùng `Agri OS Core` làm deterministic operating core.

Agri OS Core giữ:
- canonical customer identity dùng cho order/preorder/purchase truth
- preorder, order, lot, allocation, inventory movements
- event log / audit
- policy/workflow logic
- read models theo role

Các hệ ngoài giữ domain mà chúng mạnh nhất:
- ERP: accounting final, chứng từ, inventory/accounting sync
- LiteFarm/farm app: dữ liệu nông học sâu
- CRM/omnichannel: conversations, activities, outreach

## Consequences
### Tốt
- Giữ được một lớp điều phối chung cho toàn chuỗi
- Không bị 3 hệ cùng tranh source of truth
- Sau này gắn agent dễ hơn vì có core rõ

### Xấu
- Phải tự build một phần core orchestration
- Cần mapping/sync nghiêm túc với hệ ngoài
