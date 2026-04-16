# Current Runtime Overview

## Nói ngắn gọn

Đây là phần mô tả đúng cái đang ship trong runtime hiện tại, bám theo code dưới `agos_app/app/`.

Runtime đang mount các nhóm API chính:
- actors
- affiliations
- organizations
- projects
- shared resources
- customers
- preorders
- orders
- lots
- farm
- views
- events
- audit

## 1. Cái gì đang có thật trong runtime

### Core write path

Runtime hiện có write path theo hướng:
- route nhận request
- service xử lý nghiệp vụ
- gateway kiểm tra state transition và idempotency
- store ghi state
- append domain event
- append audit nếu cần

### Authz hiện có

Authz hiện tại chạy chủ yếu theo:
- role normalization
- service-layer checks
- protected read surfaces
- deny và audit cho bypass request

### Các aggregate hoặc lane đã có

- Organization
- ProjectScope
- Actor Identity baseline
- Actor Affiliation baseline
- Shared Resource
- Customer
- Preorder
- Order
- Lot
- Allocation related flows
- Project Assignment
- Project Contribution
- Project Cost Record lane đầu tiên
- Project Revenue Record lane đầu tiên
- Financial Allocation baseline lane đầu tiên

## 2. Điều rất quan trọng

Những thứ sau chưa được mô tả như thể đã ship đầy đủ:
- full PermissionGrant engine
- full delegated permission runtime
- field-level masking engine
- agent session scope runtime
- tool gateway runtime
- canonical user account aggregate
- full org or project ABAC engine

## 3. Các route group đang mount

Theo `app/api/router.py`, runtime đang mount:
- `/health`
- `/api/v1/actors`
- `/api/v1/affiliations`
- `/api/v1/customers`
- `/api/v1/organizations`
- `/api/v1/projects`
- `/api/v1/shared-resources`
- `/api/v1/preorders`
- `/api/v1/orders`
- `/api/v1/lots`
- `/api/v1/farm`
- `/api/v1/views`
- `/api/v1/events`
- `/api/v1/audit`

## 4. Runtime này không phải gì

- Không phải một engine AI tự trị.
- Không phải một app chat là source of truth.
- Không phải chỉ là hệ nội bộ cho một hợp tác xã.
- Không phải một permission platform đầy đủ theo nghĩa enterprise IAM.

## 5. Runtime này là gì

- Một deterministic core cho vận hành nông nghiệp mở.
- Một nơi giữ sự thật cho commercial, lot, inventory-related facts, contribution lane đầu tiên, authz checks hiện hành, audit và event.
- Một nền để sau này AI đi qua contract thay vì chạm trực tiếp vào truth.