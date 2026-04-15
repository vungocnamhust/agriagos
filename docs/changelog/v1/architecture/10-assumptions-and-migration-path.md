# 10. Assumptions and Migration Path

## 1. Mục tiêu

Tài liệu này giúp team:
- build nhanh nhưng không quên đường tiến hóa
- ghi rõ giả định tạm thời
- tránh tranh cãi kiểu “sao không làm chuẩn từ đầu”
- giảm nỗi sợ refactor mù

Nguyên tắc:
- kiến trúc tốt không phải kiến trúc không đổi
- kiến trúc tốt là kiến trúc **đổi được với chi phí chịu được**

## 2. Cách đọc tài liệu này

Tài liệu này không phải “lời hứa sẽ làm hết”.  
Nó chỉ làm 3 việc:
1. ghi rõ phase đầu đang đơn giản hóa ở đâu
2. ghi rõ khi nào nên nâng cấp
3. giữ cho team không bị ảo tưởng “phải đúng toàn cục ngay lập tức”

---

## 3. Các assumption phase đầu

## 3.1 Monolith modular trước
### Giả định
- phase đầu dùng một app lõi
- module hóa theo domain
- chưa tách microservice

### Vì sao
- team cần tốc độ học nhanh
- nghiệp vụ chưa đủ ổn để phân tán sớm
- cần debug nhanh, sửa nhanh

### Dấu hiệu cần xem xét tách
- ownership domain đã rõ
- deploy một phần ảnh hưởng quá nhiều phần khác
- integration nội bộ phình to
- scale / permission / data scope bắt đầu xung đột mạnh

---

## 3.2 Shared database trước
### Giả định
- dùng chung primary DB cho Agri OS Core
- read model có thể thêm dần
- chưa tách DB theo service

### Vì sao
- giảm độ phức tạp vận hành sớm
- dễ build vertical slice
- dễ lần trace từ workflow đến DB

### Dấu hiệu cần tách
- contention cao
- read load phình to
- domain boundary đã ổn định
- quyền dữ liệu khác nhau quá mạnh

---

## 3.3 Event log ở mức app trước
### Giả định
- event log bắt đầu như bảng hoặc outbox pattern đơn giản
- chưa cần event bus lớn ngay

### Vì sao
- vẫn có audit
- vẫn nuôi được analytics
- vẫn đủ context cho AI phase đầu

### Dấu hiệu cần nâng cấp
- có nhiều consumer realtime
- ordering / retry bắt đầu khó
- cần replay / recovery phức tạp hơn
- số tích hợp tăng nhanh

---

## 3.4 Plot / crop giữ mức vừa đủ
### Giả định
- phase đầu chỉ giữ dữ liệu đồng ruộng cơ bản
- chưa mô hình hóa nông học sâu

### Vì sao
- trọng tâm trước mắt là preorder → lot → delivery
- field ops sâu có thể giao LiteFarm

### Dấu hiệu cần sâu hơn
- đội hiện trường bắt đầu dùng đều
- cần dự báo sản lượng tốt hơn
- cần trace sâu cho QC / chứng nhận

---

## 3.5 CRM không tự build full từ đầu
### Giả định
- dùng CRM / omnichannel ngoài cho conversation nếu cần
- core chỉ giữ canonical customer + purchase truth

### Vì sao
- tự build conversation tooling rất tốn
- lợi thế cạnh tranh nằm ở orchestration, không phải inbox tool

### Dấu hiệu cần đầu tư sâu hơn
- CRM ngoài bắt đầu không đáp ứng workflow đặc thù
- cần role-based customer views quá riêng
- cần policy giữa preorder / order / messaging chặt hơn

---

## 3.6 ERP không nuốt hết logic preorder và lot phase đầu
### Giả định
- ERP giữ accounting final
- Agri OS Core vẫn giữ preorder / lot / allocation truth phase đầu

### Vì sao
- preorder và lot allocation là logic đặc thù của hệ này
- nếu đẩy sớm hết vào ERP, rất dễ lệch workflow thật

### Dấu hiệu cần chuyển ownership bớt sang ERP
- item master / invoice / stock accounting đã ổn định
- team tài chính muốn ERP thành nguồn chính cho nhiều hơn
- mapping không còn gây đau lớn

---

## 3.7 AI chỉ ở mức suggest / draft trước
### Giả định
- phase đầu agent không được auto-execute action nhạy cảm
- phase đầu chừa sẵn mechanism cho bypass lane nhưng chưa enable lane nào

### Vì sao
- cần học từ dữ liệu thật
- cần đo độ đúng
- tránh excessive agency

### Dấu hiệu có thể mở rộng quyền
- suggestion acceptance rate cao ổn định
- false suggestion rate thấp
- guardrails và audit đã đủ tốt
- operator tin hệ thống hơn

---

## 4. Migration path tổng thể

## 4.0 Included / excluded baseline cho phase đầu

### In scope
- canonical customer identity
- preorder quota và link từ preorder sang order
- order vận hành
- lot, release, allocation
- inventory movement mức đủ audit
- plot / crop summary mức đủ dùng
- event log, audit log, external mapping

### Out of scope
- accounting final, journal, tax engine
- CRM conversation tooling đầy đủ
- field ops sâu và field task engine như farm app chuyên biệt
- AI auto-execute trên action nhạy cảm
- microservice tách domain và event bus lớn

### Deferred nhưng phải chừa đường
- projection workers chuẩn
- tenant-scoped RBAC/ABAC hoàn chỉnh vượt ngoài rollout route/service hiện tại
- integration adapters production-grade
- advanced analytics và recommendation layer
- agent bypass lanes hẹp, có explicit allow list + audit, chỉ sau khi guardrails đủ tốt
- organization-aware scoping rollout theo từng domain slice; không one-shot rewrite toàn hệ

### Runtime reality đã được kéo lên sớm trong late Phase 1
- selected role-based read models đã được ship sớm bằng SQL views thay vì đợi projection workers
- current shipped set gồm `customer_360_view`, `available_lots_board`, `pending_fulfillment_board`, và `farm_summary_board`
- `customer_360_view` trên PostgreSQL path đã là nested detail projection; các board còn lại vẫn là operational list views
- validation lane hiện có PostgreSQL integration coverage cho cả `customer_360_view` và sweep `/api/v1/views/*`, bao gồm store-level assertions lẫn HTTP endpoint checks để giữ migration + view contract không drift
- shared actor-context/authz substrate cũng đã ship cho Phase 1 route/service rollout: `/api/v1/events`, `/api/v1/views/*`, raw `/api/v1/farm/*`, `/api/v1/audit`, raw `/api/v1/customers*`, preorder/order/lot surfaces đều đã có explicit role gates ở runtime hiện tại
- bypass mechanism vẫn chỉ là hook kiến trúc; mọi bypass request trong Phase 1 hiện phải bị deny và audit, chưa có lane nào được enable

### Mặc định khi chưa có quyết định theo tenant
- Core giữ `plot/crop summary` mức đủ dùng
- LiteFarm chỉ là nguồn sâu khi snapshot contract đã được chốt rõ
- CRM chỉ gửi summary/candidate, không được trở thành canonical owner của identity hoặc confirmed preference
- ERP chỉ nhận operational sync; accounting final vẫn ở ERP

### Phase 1 - Core Monolith
Mục tiêu:
- customer
- preorder
- order
- lot
- lot evidence / QC review
- allocation
- inventory movement
- plot / crop cycle cơ bản
- event log / audit log
- external mapping / channel identity binding

Thành công khi:
- workflow preorder → lot → QC → allocation chạy thật
- team debug được bằng event log
- role chính dùng được
- team có thể chỉ ra rõ domain nào thuộc Core, domain nào thuộc ERP/LiteFarm/CRM

### Phase 2 - Stable Modules + Integrations
Mục tiêu:
- Organization aggregate baseline đã được đưa vào schema/runtime và bắt đầu rollout association theo domain
- ERP sync
- CRM sync
- LiteFarm sync summary
- dashboards theo role
- retry / error handling integration

Thành công khi:
- source of truth rõ giữa các hệ
- sync không còn lỗi mù
- read model bắt đầu phục vụ team tốt
- boundary theo tenant không còn phải giải thích lại mỗi lần build integration

### Organization rollout path
Baseline cho aggregate `Organization` đi theo thứ tự sau:
1. chốt authority docs + ADR
2. thêm standalone `Organization` schema và CRUD
3. rollout `organization_id` sang farm-side records: `plot`, `crop_cycle`, `lot`
4. rollout `organization_id` sang commercial-side records: `preorder`, `sales_order`
5. nếu cần, thêm customer-organization affinity/read model mà không đổi canonical ownership của `CustomerProfile`; lane này nằm ngoài canonical ownership graph hiện tại và không tự tạo FK ownership mới trên `CustomerProfile`
6. ở phase integration sau, propagate `organization_id` sang integration-facing records và flows

Rule baseline:
- không dùng `tenant_id = "default"` để suy ra organization truth
- không ép mọi bảng phải có `organization_id` trong một migration duy nhất
- backward compatibility của existing APIs phải được giữ cho đến khi slice rollout tương ứng được ship

### ProjectScope rollout path
Baseline cho aggregate `ProjectScope` và các lanes liên quan đi theo thứ tự sau:
1. chốt authority docs + ADR cho `ProjectScope` như lớp soft value-stream scope dưới `Organization`
2. thêm standalone `ProjectScope` schema, CRUD, lifecycle, và read surface tối thiểu
3. thêm `ProjectAssignment` lane để gắn farm-side và commercial-side records vào scope mà không one-shot rewrite toàn bộ canonical tables
4. thêm contribution ledger, shared resources, cost records, revenue records, và financial allocations theo vertical slices riêng
5. thêm reporting views cho P&L, impacted households/actors, shared resources, customer source/repeat, và contribution ledger
6. backfill selected records theo confidence-driven rules; giữ `unassigned` hợp lệ khi chưa có deterministic attribution

Rule baseline:
- không ép mọi canonical table phải có `project_scope_id` trong một migration duy nhất
- không tạo một `default_project` giả để nuốt toàn bộ legacy data chưa rõ attribution
- `unassigned`, `inferred`, và `needs_review` là trạng thái hợp lệ trong rollout project scope
- impact reporting và financially eligible attribution là hai lane khác nhau; rollout phải giữ semantics này rõ ngay từ đầu

### Phase 3 - Read Models + Agent Support
Mục tiêu:
- customer 360
- pending fulfillment board
- available lots board
- AI canonical intake
- AI draft / suggest
- ops summary / CRM summary

Ghi chú cập nhật:
- một phần read-model lane này đã được pull forward vào late Phase 1 bằng direct SQL views và `/api/v1/views/*`
- phase này vẫn còn khác Phase 1 ở chỗ projection workers, agent support, và automation chưa trở thành runtime mặc định

Thành công khi:
- operator tiết kiệm thời gian thật
- AI không phá core truth
- acceptance rate của suggestion ở mức chấp nhận được
- AI vẫn đi qua boundary và policy đã chốt ở phase trước

### Phase 4 - Supervisor Agent + Event-driven Expansion
Mục tiêu:
- supervisor điều phối nhiều role-based agents
- thêm automation workflow
- scale integration và analytics
- có thể tách service nơi thật sự cần

Thành công khi:
- multi-agent vẫn nằm trong kiểm soát
- observability đủ tốt
- không tạo shadow truth

## 4.1 Phase gates phải nhìn thấy được

| Từ phase | Sang phase | Chỉ được đi tiếp khi |
|---|---|---|
| Core Monolith | Stable Modules + Integrations | P0 workflow chạy end-to-end, event log debug được, domain ownership không còn mơ hồ |
| Stable Modules + Integrations | Read Models + Agent Support | sync có idempotency, retry, reconcile; read views phục vụ operator tốt; external mapping ổn định |
| Read Models + Agent Support | Supervisor Agent + Event-driven Expansion | AI suggestion acceptance rate ổn định, false suggestion rate thấp, guardrails và observability đủ tốt |

---

## 5. Những thứ chưa nên làm quá sớm

- microservice hóa mọi domain
- workflow engine quá tổng quát khi workflow thật chưa rõ
- rule engine quá nặng khi rule còn ít
- AI auto-execute trên action nhạy cảm
- dashboard quá đẹp nhưng dữ liệu gốc chưa sạch
- sensor / IoT sâu khi hiện trường chưa dùng ổn

---

## 6. Quy tắc quyết định khi phân vân

Khi team phân vân giữa hai hướng, hỏi 5 câu:

1. Workflow thật nào đang đau nhất?
2. Source of truth của dữ liệu này ở đâu?
3. Nếu quyết định này sai, sửa có đắt không?
4. Cái này là lõi ổn định hay phần biến động?
5. Nếu chưa rõ, có thể hardcode tạm + log assumption không?

---

## 7. Assumption log template

```md
## ASSUMPTION-001
- Mô tả: tạm dùng Agri OS Core là source of truth cho SKU phase đầu
- Lý do: ERP item master chưa ổn định
- Rủi ro: sau này sync 2 chiều phức tạp
- Dấu hiệu cần đổi: ERP team bắt đầu quản SKU chuẩn
- Kế hoạch đổi: thêm mapping table và chuyển ownership sang ERP
```

---

## 8. Ví dụ assumption thật nên ghi

### ASSUMPTION-A
- Plot / crop deep data do LiteFarm giữ
- Core chỉ giữ summary để điều phối

### ASSUMPTION-B
- Delivery phase đầu có thể update bán thủ công
- Chưa phụ thuộc hoàn toàn vào logistics webhook

### ASSUMPTION-C
- Payment status trong core chỉ là operational status
- Accounting final vẫn ở ERP

### ASSUMPTION-D
- AI chỉ tạo draft / suggestion trong phase đầu

---

## 9. Định nghĩa “đủ tốt để đi tiếp”

Một quyết định được coi là đủ tốt nếu:
- giải quyết pain thật
- không khóa chết đường tiến hóa
- có log / audit để sửa sau
- không tạo source of truth thứ hai
- không giao quyền quá sớm cho AI

## 10. Kết luận

Project này không cần hoàn hảo ngay từ đầu.  
Nó cần:
- đúng lõi
- rõ quyền
- rõ dữ liệu
- rõ state
- rõ event
- rõ đường tiến hóa

Nói ngắn:
**đúng lõi trước, mở rộng sau, và luôn chừa đường refactor có chủ đích.**
