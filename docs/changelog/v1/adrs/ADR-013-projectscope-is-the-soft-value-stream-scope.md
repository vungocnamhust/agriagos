# ADR-013: ProjectScope là lớp soft scope cho value stream dưới Organization

**Status:** Proposed
**Date:** 2026-04-16
**Deciders:** Architecture team, Founder/Product

---

## Context

`Organization` vừa đủ để mô hình hóa legal-operating owner, nhưng vẫn quá thô để trả lời các câu hỏi như một dòng giá trị đang lời hay lỗ, những hộ nào bị tác động, tài nguyên nào đang dùng chung, hay ai đã đóng góp vào kết quả đó. Trong thực tế Agri OS, một hộ gia đình hoặc một organization có thể đồng thời vận hành nhiều chuỗi như gạo mùa, dược liệu, mật ong, Farm Visit, retreat, hoặc gói quà. `Tenant` là sai boundary cho bài toán này, còn việc ép toàn bộ action phải mang một `project_id` cứng ngay từ đầu sẽ làm write path nặng và khó nhập liệu.

## Decision

Chúng ta sẽ thêm `ProjectScope` như một canonical aggregate additive dưới `Organization` để đại diện cho project hoặc value stream theo nghĩa nghiệp vụ. `ProjectScope` là lớp scope mềm cho phân tích và điều phối, không thay `Organization`, không đổi ownership của `CustomerProfile`, và không trở thành hard permission boundary trong slice đầu. Việc gắn domain records vào `ProjectScope` sẽ đi qua assignment và allocation layers theo rollout từng slice, thay vì ép one-shot `project_scope_id` lên toàn bộ canonical tables.

Trong ADR này, `soft scope` có nghĩa là:
- record có thể hợp lệ ở trạng thái `unassigned` mà không bị chặn write path
- assignment vào `ProjectScope` là additive, không phải FK bắt buộc toàn cục ngay từ đầu
- permission enforcement trong slice đầu áp vào aggregate `ProjectScope` và các action xác nhận nhạy cảm, không tự biến mọi scope thành data-isolation boundary độc lập

## Trade-offs

**Gains:**
- Có trục phân tích và vận hành để tính P&L, theo dõi tác động, tài nguyên dùng chung, và contribution theo dòng giá trị.
- Giữ được write path linh hoạt: record nào chưa biết scope vẫn có thể ở trạng thái `unassigned` thay vì bị chặn nhập liệu.

**Costs:**
- Tăng thêm aggregate, migration, docs, reporting views, và backfill policy mới.
- Một thời gian sẽ tồn tại song song dữ liệu đã được scope rõ và dữ liệu còn `unassigned` hoặc `inferred`.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Chỉ dùng `Organization` để làm mọi phân tích value stream | Quá thô, không tách được nhiều chuỗi giá trị cùng chạy dưới một legal-operating owner. |
| Tách riêng `Project` và `ValueStream` thành hai aggregate ngay | Tăng độ phức tạp quá sớm khi nhu cầu hiện tại vẫn là một lớp scope mềm có `type`. |
| Ép thêm `project_scope_id` vào mọi bảng canonical ngay trong một đợt | Blast radius lớn, làm write path cứng và tạo nhiều dữ liệu gán scope sai chỉ để vượt validation. |

## Migration Impact

**Scope:** High

- Code: thêm aggregate `ProjectScope`, assignment layer, contribution ledger, financial records, và reporting views theo rollout sau.
- Data: thêm bảng mới và rollout nullable/additive associations theo từng domain slice; legacy records có thể ở `unassigned` hoặc `inferred`.
- Contracts: sẽ có route, DTO, event, và read-model mới; không được phá backward compatibility của existing APIs.
- Deployment: docs và ADR đi trước; runtime rollout theo thứ tự ProjectScope -> assignments -> contribution/economics -> reports -> backfill.

## Revisit Conditions

Revisit khi domain cho thấy `ProjectScope` không còn đủ để đại diện cả initiative và value stream, khi permission boundary cần tách per-scope ở runtime, hoặc khi household/actor aggregates độc lập đã đủ rõ để trở thành canonical owners thay vì chỉ đi qua `Organization` và assignment layers.