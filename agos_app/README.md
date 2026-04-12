# FastAPI Skeleton v1

Skeleton này bám theo OpenAPI v1 của deterministic core.

## Mục tiêu
- route groups rõ theo domain
- DTOs rõ
- chỗ nào là stub thì để TODO rất rõ
- chưa nhét business logic hoặc AI vào sớm

## Chạy local
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Cài dependencies cho test/dev
```bash
pip install -r requirements-dev.txt
```

## Migration database
Schema Phase 1 hiện được apply bằng Alembic thay vì chỉ đọc từ bộ SQL docs.

```bash
docker run --name agriagos-postgres-dev \
	-e POSTGRES_DB=agriagos \
	-e POSTGRES_USER=agriagos \
	-e POSTGRES_PASSWORD=agriagos \
	-p 127.0.0.1:5436:5432 \
	-d postgres:15-alpine

export DATABASE_URL=postgresql+psycopg://agriagos:agriagos@127.0.0.1:5436/agriagos
alembic upgrade head
```

## Chạy integration test PostgreSQL
```bash
export DATABASE_URL=postgresql+psycopg://agriagos:agriagos@127.0.0.1:5436/agriagos
pytest tests/test_*integration.py -m postgres_integration

# hoặc chỉ chạy sweep views/store PostgreSQL
pytest tests/test_view_board_integration.py -m postgres_integration
```

## DB-first mode (mặc định)
Mặc định app đang chạy DB-first trên PostgreSQL cho các luồng chính:

- `customers` và `customer_preferences`
- `preorders`
- `orders` / `allocations`
- `lots`, `lot_evidence`, `qc_reviews`
- `events`, `views`, và durable `idempotency_records`

```bash
export POSTGRES_WRITE_PATH_ENABLED=true
export DATABASE_URL=postgresql+psycopg://agriagos:agriagos@127.0.0.1:5436/agriagos
uvicorn app.main:app --reload
```

Nếu cần chạy chế độ mô phỏng in-memory cho test/dev cục bộ, có thể tắt:

```bash
export POSTGRES_WRITE_PATH_ENABLED=false
```

Các revision đầu tiên đã bao gồm customer, preorder, order, lot, lot_evidence, qc_reviews,
allocation, inventory movement, event/audit log, external mapping, durable idempotency,
và các view đọc sớm.

## Runtime reality

- Phase 1 hiện dùng direct PostgreSQL reads/writes trong service/store layer và vẫn append domain events vào `domain_events`.
- Projection workers vẫn là hướng kiến trúc tài liệu hóa cho phase sau, chưa phải runtime mặc định.
- `POSTGRES_WRITE_PATH_ENABLED=false` chỉ nên dùng cho mô phỏng local hoặc test thủ công.
- Protected routes hiện dùng shared actor context từ request headers/body `meta`; runtime đã gate `/api/v1/events`, `/api/v1/views/*`, raw `/api/v1/farm/*`, `/api/v1/audit`, raw customer reads, preorder/order routes, và lot/QC surfaces ở service layer.
- `qc_reviewer` là top-level role cho QC lane. Agent/automation bypass chỉ tồn tại như mechanism hook; Phase 1 chưa enable bất kỳ bypass lane nào.
