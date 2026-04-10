# ADR-009: Core owns plot/crop summary; LiteFarm may own deep field data later

## Status
Accepted

## Context
Boundary `plot/crop` là chỗ dễ drift nhất trong baseline: nếu để LiteFarm làm nguồn sâu quá sớm, team dễ bỏ trống snapshot cần cho traceability thương mại; nếu nhét hết field ops sâu vào Core, deterministic core sẽ bị kéo lệch khỏi trọng tâm phase đầu. Team cần chốt mặc định phase đầu để routes, models, và integration work không bị hiểu hai kiểu.

## Decision
Phase 1 mặc định để **Agri OS Core** giữ `plot/crop summary` đủ dùng cho thương mại và traceability. **LiteFarm** chỉ được coi là nguồn sâu cho farm data ở phase tích hợp hoặc với tenant đã chốt snapshot contract rõ ràng; kể cả khi đó, Core vẫn phải giữ snapshot tối thiểu để nối `plot -> crop cycle -> lot -> order`.

## Consequences
### Tốt
- Giữ deterministic core tự chạy được workflow farm-summary -> lot -> order ở phase đầu
- Không làm mất traceability khi integration với LiteFarm chưa ổn định

### Xấu
- Sẽ tồn tại một lớp snapshot cần reconcile khi LiteFarm trở thành nguồn sâu
- Team phải giữ kỷ luật mapping và snapshot contract rõ ràng theo tenant

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Để LiteFarm làm source chính cho plot/crop ngay từ phase đầu | Đẩy quá sớm dependency integration vào workflow lõi và làm mờ traceability trong Core |
| Đưa cả field ops sâu vào Core | Mở rộng deterministic core quá sớm ra ngoài trọng tâm thương mại phase đầu |

## Migration Impact

**Scope:** Medium

- Code: farm routes, models, integration adapters, và mapping logic phải giữ được chế độ `Core default / LiteFarm deep-source later`
- Data: cần snapshot tối thiểu cho plot/crop khi tenant dùng LiteFarm
- Contracts: integration với LiteFarm phải định nghĩa rõ snapshot contract trước khi sync sâu
- Deployment: không yêu cầu cutover ngay; chỉ khóa mặc định phase đầu và điều kiện để đổi mode

## Revisit Conditions
Xem lại quyết định này khi LiteFarm integration trở thành bắt buộc cho một tenant thực, khi field ops sâu bắt đầu là nhu cầu vận hành hằng ngày, hoặc khi traceability cần nhiều farm data hơn mức summary hiện tại. Nếu chưa có snapshot contract rõ ràng, không được đổi ownership mặc định.