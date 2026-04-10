# 11. Core Baseline Sign-Off

## 1. Mục tiêu

Tài liệu này gom phần còn thiếu để team chốt baseline kiến trúc cho **Agri OS Core**.

Nó không thay thế:
- [01-system-vision.md](01-system-vision.md)
- [04-canonical-data-model.md](04-canonical-data-model.md)
- [08-integration-contracts.md](08-integration-contracts.md)
- [10-assumptions-and-migration-path.md](10-assumptions-and-migration-path.md)

Nó chỉ làm 4 việc:
- gom deliverables phải hoàn tất
- liệt kê các quyết định phải chốt
- gán owner chịu trách nhiệm chốt
- đưa ra tiêu chí coi baseline là hoàn thành

---

## 2. Deliverables phải có

| Deliverable | Mục tiêu | Tài liệu chính | Owner đề xuất |
|---|---|---|---|
| System vision baseline | Chốt hệ thống giải bài toán gì, cho ai, và workflow nào phải chạy trước | `01-system-vision.md`, `02-core-workflows.md`, `system_v1.md` | Founder/Product + Architect |
| Domain boundary baseline | Chốt domain nào thuộc Core, domain nào thuộc ERP/LiteFarm/CRM | `04-canonical-data-model.md`, `08-integration-contracts.md`, `03-domain-glossary.md` | Architect + Integration lead |
| Deterministic core scope | Chốt phase đầu làm gì, chưa làm gì | `10-assumptions-and-migration-path.md`, `CLAUDE.md` | Architect + Core backend lead |
| Source of truth policy | Mỗi domain có đúng một canonical owner | `04-canonical-data-model.md`, `05-event-catalog.md`, `07-permission-matrix.md` | Architect + domain owners |
| Migration path baseline | Chốt đường tiến hóa từ modular monolith sang integration phase và agent phase | `10-assumptions-and-migration-path.md`, `system_v1.md` | Architect + Founder/Product |

---

## 3. Quyết định phải chốt

### 3.1 System vision
- P0 workflow nào phải chạy end-to-end trước khi nói tới agent layer
- user chính của phase đầu là ai
- workflow nào được coi là bắt buộc, workflow nào defer

### 3.2 Domain boundary
- `customer` canonical identity thuộc Core
- `preorder`, `order`, `lot`, `allocation`, `inventory movement` thuộc Core
- `plot/crop summary` thuộc Core snapshot hay LiteFarm snapshot theo tenant nào
- `field ops sâu` thuộc LiteFarm
- `accounting final` thuộc ERP
- `conversations / campaign activity` thuộc CRM

### 3.3 Deterministic core scope
- phase đầu có cần inventory ledger đầy đủ hay chỉ cần operational movement đủ audit
- projection workers có phải in scope phase đầu hay là phase tích hợp
- auth/RBAC enforcement có phải baseline kỹ thuật hay để phase sau

### 3.4 Source of truth policy
- confirmed preference nằm ở Core; CRM và AI chỉ là nguồn candidate/input
- external systems không được tạo canonical truth riêng cho domain mà Core sở hữu
- state nhạy cảm chỉ đổi qua command + service + event hợp lệ

### 3.5 Migration path
- trigger để bước từ `Core Monolith` sang `Stable Modules + Integrations`
- trigger để bước sang `Read Models + Agent Support`
- điều kiện nào mới cho phép automation nhiều hơn nhưng vẫn không tạo shadow truth

---

## 4. Owner và trách nhiệm

| Vai trò | Chịu trách nhiệm chính |
|---|---|
| Founder / Product | Chốt bài toán hệ thống, user chính, P0 workflow |
| Architect | Chốt domain boundary, source-of-truth policy, migration path |
| Core backend lead | Xác nhận deterministic write path và current implementation reality |
| Integration lead | Chốt boundary và sync direction giữa Core với ERP/LiteFarm/CRM |
| Finance / Ops stakeholder | Chốt accounting boundary, operational payment truth |
| Sales / CRM stakeholder | Chốt conversation ownership và customer-operational summary |

Ghi chú: team nhỏ có thể để một người kiêm nhiều vai trò owner, nhưng trách nhiệm sign-off vẫn phải được nêu rõ theo từng quyết định.

---

## 5. Đầu ra tài liệu bắt buộc

1. `01-system-vision.md` phải trả lời được: hệ này giải bài toán gì, cho ai, và thứ gì phải chạy trước.
2. `04-canonical-data-model.md` phải có matrix source-of-truth theo domain.
3. `08-integration-contracts.md` phải có boundary rõ giữa Core với ERP/LiteFarm/CRM.
4. `10-assumptions-and-migration-path.md` phải có included scope, excluded scope, phase gates.
5. `05-event-catalog.md` và `07-permission-matrix.md` phải khớp với source-of-truth policy đã chốt.
6. Nếu có quyết định kiến trúc mới vượt ngoài ADR hiện có, phải thêm ADR thay vì sửa prose âm thầm.

---

## 6. Tiêu chí hoàn thành baseline

Baseline chỉ được coi là hoàn thành khi:

1. Mỗi domain trong scope có đúng một canonical owner.
2. Core vs ERP/LiteFarm/CRM được mô tả bằng boundary rõ ràng, không bằng câu chữ mơ hồ.
3. Phase đầu có danh sách `in scope`, `out of scope`, `deferred` rõ ràng.
4. P0 workflow được nêu bằng actor, input, rule, output, event tối thiểu.
5. Migration path có phase gate cụ thể thay vì chỉ có định hướng chung.
6. Narrative docs, ADRs, event/state docs và diagrams không mâu thuẫn nhau.
7. Một kỹ sư mới đọc bộ docs này có thể biết ngay thứ gì đang được build, thứ gì chưa build, và dữ liệu nào thuộc hệ nào.

---

## 7. Sign-off checklist

- [ ] Founder/Product chốt bài toán hệ thống và P0 workflow
- [ ] Architect chốt boundary theo domain
- [ ] Integration lead chốt boundary với ERP/LiteFarm/CRM
- [ ] Core backend lead xác nhận scope phase đầu khớp với code reality
- [ ] Finance/Ops/CRM stakeholders chốt accounting và conversations ownership
- [ ] Không còn unresolved item nào ở mức block implementation

## 8. Kết luận

Tài liệu này là gate trước implementation tiếp theo.

Nếu một thay đổi mới làm mờ:
- workflow phải chạy trước
- source of truth theo domain
- boundary Core với external systems
- hoặc phase gate

thì baseline phải được cập nhật lại trước khi mở rộng implementation.