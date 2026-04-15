# ADR-012: Organization là legal-operating owner aggregate, không đồng nhất với tenant

**Status:** Proposed
**Date:** 2026-04-15
**Deciders:** Architecture team, Founder/Product

---

## Context

Agri OS hiện là Phase 1 deterministic-core monolith và `tenant_id` mới chỉ là placeholder deployment/integration boundary, chưa phải runtime multi-tenant scoping. Trong khi đó domain thực tế cần mô hình hóa một chủ thể vận hành hoặc pháp lý như hộ sản xuất, gia đình có thương hiệu riêng, solo founder, HTX, hoặc chủ thể tương đương. Customer identity vẫn là canonical identity dùng chung toàn hệ sinh thái, nên không thể giải bài toán này bằng cách biến customer thành dữ liệu thuộc riêng từng tổ chức.

## Decision

Chúng ta sẽ thêm `Organization` như một canonical business aggregate cho legal-operating owner. `Tenant` vẫn giữ nghĩa deployment/integration boundary và không bị thay thế trong epic này. Rollout `organization_id` sẽ đi theo hướng additive: standalone Organization trước, farm-side aggregates sau, commercial-side aggregates tiếp theo, còn customer vẫn là shared ecosystem identity. Brand/business-facing identity sẽ ở trong profile của `Organization`; chưa tạo brand aggregate riêng.

## Trade-offs

**Gains:**
- Mô hình domain khớp hơn với thực tế business owner trong hệ sinh thái.
- Mở đường cho future data scoping, permissions, và integration tracing mà không phải one-shot rewrite.

**Costs:**
- Tăng thêm một aggregate, migration, docs, và test surfaces mới.
- Một thời gian sẽ có coexistence giữa dữ liệu đã gắn organization và dữ liệu chưa gắn organization.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Reuse `tenant_id` như business organization | Sai nghĩa authority baseline hiện tại, dễ phá boundary integration/deployment. |
| Add `organization_id` cho mọi bảng ngay trong một đợt | Blast radius quá lớn so với current runtime và rollout readiness. |
| Tách brand aggregate riêng ngay | Chưa có lifecycle hoặc ownership riêng đủ rõ để justify thêm aggregate. |

## Migration Impact

**Scope:** Medium

- Code: thêm route/model/service/store cho Organization, sau đó rollout dần association theo domain.
- Data: tạo bảng `organizations`, rồi staged nullable `organization_id` cho selected tables.
- Contracts: thêm `/api/v1/organizations`; existing APIs phải giữ backward compatibility trong epic đầu.
- Deployment: docs/ADR trước, schema sau, standalone CRUD tiếp theo, rồi staged association rollout.

## Revisit Conditions

Revisit khi `tenant` cần trở thành runtime scoping boundary thật, khi một organization vận hành nhiều brand với lifecycle độc lập, hoặc khi integration rollout yêu cầu org-aware event/audit/idempotency semantics rộng hơn additive propagation hiện tại.