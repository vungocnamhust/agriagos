# ADR-006: OpenAPI Spec Là Committed Artifact — Contract Before Implementation

**Status:** Accepted
**Date:** 2026-04-10
**Deciders:** Architecture team

---

## Context

FastAPI tự động generate OpenAPI spec từ route signatures — điều này tốt nhưng chưa đủ.
Khi spec chưa được commit vào git, không thể:
- Review API contract độc lập với implementation
- Detect breaking changes ở code review
- Cung cấp stable contract cho client integration (mobile app, Zalo bot, ERP webhook)

## Decision

**OpenAPI spec là committed artifact, không phải generated artifact.**

Baseline spec: `docs/changelog/v1/openapi/agros-api-v1.0.yaml`

Rules:
1. Mọi thay đổi route/DTO/response code phải update spec file trong **cùng commit**
2. Additive changes (thêm optional field, thêm endpoint): update `agros-api-v1.0.yaml`
3. Breaking changes: tạo file mới `agros-api-v1.1.yaml`, không overwrite v1.0
4. Không được merge PR nếu spec file không sync với code

## Consequences

- CI có thể validate spec file matches server-generated spec (future automation)
- Breaking change detection: diff `agros-api-v1.0.yaml` trước/sau PR
- Client teams có thể xem contract mà không cần chạy server
- `.claude/rules/api-contract-first.md` được update để reference spec file location

## Định nghĩa Breaking Change

| Change | Breaking? |
|--------|-----------|
| Thêm optional request field | Không |
| Thêm response field | Không |
| Thêm endpoint mới | Không |
| Xóa request/response field | **Có** |
| Rename field | **Có** |
| Đổi field type | **Có** |
| Make optional field required | **Có** |
| Xóa endpoint | **Có** |
| Đổi HTTP status code | **Có** |
