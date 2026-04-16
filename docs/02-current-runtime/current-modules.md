# Current Modules

## Nói ngắn gọn

Nếu chỉ nhìn code, runtime hiện có 5 lớp chính:
- API routes
- services
- core
- models
- store

## 1. API routes

Thư mục: `agos_app/app/api/routes/`

Nhiệm vụ:
- nhận HTTP request
- parse path và body
- gọi service
- trả response model

Các file chính:
- `actor_authority.py`
- `actor_affiliations.py`
- `organizations.py`
- `project_scopes.py`
- `shared_resources.py`
- `customers.py`
- `preorders.py`
- `orders.py`
- `lots.py`
- `farm.py`
- `views.py`
- `events.py`
- `audit.py`

## 2. Services

Thư mục: `agos_app/app/services/`

Nhiệm vụ:
- giữ logic nghiệp vụ
- enforce policy và authz hiện hành
- emit event
- append audit
- phối hợp store và gateway

Các service đáng chú ý:
- `organizations.py`
- `project_scopes.py`
- `project_assignments.py`
- `project_contributions.py`
- `project_cost_records.py`
- `project_revenue_records.py`
- `financial_allocations.py`
- `shared_resources.py`
- `customers.py`
- `preorders.py`
- `orders.py`
- `lots.py`
- `read_authz.py`
- `audit.py`

## 3. Core

Thư mục: `agos_app/app/core/`

Nhiệm vụ:
- state machine
- idempotency gate
- event factory
- authz primitives và helper

Các file chính:
- `gateway.py`
- `events.py`
- `authz.py`
- `event_registry.py`
- `policy_sets.py`

## 4. Models

Thư mục: `agos_app/app/models/`

Nhiệm vụ:
- DTO request và response
- enum domain
- common response envelope

Các models chính phản ánh domain hiện hành:
- `organizations.py`
- `project_scopes.py`
- `actor_authority.py`
- `financial_allocations.py`
- `customers.py`
- `preorders.py`
- `orders.py`
- `lots.py`
- `shared_resources.py`
- `views.py`

## 5. Store

Thư mục: `agos_app/app/store/`

Nhiệm vụ:
- persistence cho PostgreSQL path
- fallback in-memory path
- audit và event append

Lưu ý:
- PostgreSQL là write path chính khi config bật.
- In-memory là fallback cho local simulation hoặc test.