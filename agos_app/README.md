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
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/agriagos
alembic upgrade head
```

Các revision đầu tiên đã bao gồm customer, preorder, order, lot, lot_evidence, qc_reviews,
allocation, inventory movement, event/audit log, external mapping, và các view đọc sớm.
