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

## DB-first mode (mặc định)
Mặc định app đang chạy DB-first cho các luồng `orders` / `preorders` và đồng bộ
`lots` / `allocations` trong các bước allocate/cancel.

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
allocation, inventory movement, event/audit log, external mapping, và các view đọc sớm.
