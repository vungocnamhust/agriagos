# ADR-004: Monolith modular trước, không microservice hóa sớm

## Status
Accepted

## Context
Đội cần tốc độ học nhanh, build vertical slices, debug nhanh.
Domain boundaries vẫn đang được chứng minh qua use cases thật.

## Decision
Bắt đầu bằng một modular monolith cho Agri OS Core.
Tách module theo domain:
- customers
- preorders
- orders
- lots
- inventory
- farm summary
- eventing/audit
- projections
- integrations

Chưa tách microservices ở phase đầu.

## Consequences
### Tốt
- Build nhanh
- Ít complexity vận hành
- Dễ refactor theo workflow thật

### Xấu
- Về sau phải chủ động nhìn dấu hiệu cần tách
- Cần giữ module boundaries rõ dù cùng codebase
