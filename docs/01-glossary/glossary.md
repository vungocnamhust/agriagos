# Từ Điển Thuật Ngữ AgriOS

## Nói ngắn gọn

Mỗi thuật ngữ dưới đây được viết theo cùng một khung:
- tên tiếng Việt dễ hiểu trước
- tên tiếng Anh trong ngoặc
- định nghĩa ngắn
- ví dụ thực tế
- module đang dùng
- có phải source of truth hay không

## 1. Tổ chức vận hành (Organization)

- Định nghĩa ngắn: chủ thể vận hành hoặc pháp lý mà hệ thống ghi nhận để biết hoạt động này thuộc về ai.
- Ví dụ thực tế: một hộ gia đình có thương hiệu nông sản riêng; một startup operator; một hợp tác xã.
- Dùng trong module: `app/models/organizations.py`, `app/services/organizations.py`, `app/api/routes/organizations.py`.
- Source of truth: Có, là aggregate runtime hiện có.

## 2. Loại tổ chức (Organization Type)

- Định nghĩa ngắn: cách phân loại một organization theo bản chất vận hành.
- Ví dụ thực tế: `household_producer`, `family_business`, `solo_founder`, `cooperative`.
- Dùng trong module: `app/models/enums.py`, `app/models/organizations.py`.
- Source of truth: Có, ở enum runtime.

## 3. Phạm vi dự án mềm hoặc dòng giá trị (ProjectScope)

- Định nghĩa ngắn: lớp gom nghĩa kinh doanh dưới organization để theo dõi lời lỗ, tác động, nguồn lực và đóng góp.
- Ví dụ thực tế: dòng giá trị gạo sạch vụ hè thu; chương trình sinh kế cho 20 hộ; dịch vụ farm tour cuối tuần.
- Dùng trong module: `app/models/project_scopes.py`, `app/services/project_scopes.py`, `app/api/routes/project_scopes.py`.
- Source of truth: Có, là aggregate runtime hiện có.

## 4. Dòng giá trị (Value Stream)

- Định nghĩa ngắn: cách gọi nghiệp vụ gần nghĩa với ProjectScope.
- Ví dụ thực tế: toàn bộ dòng từ sản xuất đến bán của một dòng gạo quà tặng.
- Dùng trong module: chủ yếu dùng trong docs, runtime canonical term vẫn là `ProjectScope`.
- Source of truth: Không, đây là tên giải thích nghiệp vụ cho `ProjectScope`.

## 5. Chủ thể được ghi nhận (Actor Identity)

- Định nghĩa ngắn: hồ sơ chủ thể mà hệ thống dùng để nhận diện một người, hộ, ghế đại diện của tổ chức hoặc automation principal.
- Ví dụ thực tế: chị Lan là một actor kiểu person; hộ Nguyễn Văn A là household; bot đồng bộ là automation principal.
- Dùng trong module: `app/models/actor_authority.py`, `app/services/actor_authority.py`, `app/api/routes/actor_authority.py`.
- Source of truth: Có, nhưng runtime hiện mới là lane baseline.

## 6. Loại actor (Actor Identity Type)

- Định nghĩa ngắn: loại chủ thể trong hồ sơ actor.
- Ví dụ thực tế: `person`, `household`, `organization_actor`, `automation_principal`.
- Dùng trong module: `app/models/enums.py`, `app/models/actor_authority.py`.
- Source of truth: Có, ở enum runtime.

## 7. Quan hệ mềm với tổ chức hoặc dự án (Affiliation)

- Định nghĩa ngắn: sự gắn kết theo thời gian giữa actor với organization hoặc project scope.
- Ví dụ thực tế: một người là cộng tác viên của một project trong 3 tháng; một hộ là thành viên quan sát của một chương trình.
- Dùng trong module: `app/models/actor_authority.py`, `app/services/actor_authority.py`, `app/api/routes/actor_affiliations.py`.
- Source of truth: Có, nhưng chỉ cho fact quan hệ. Nó không phải source of truth cho permission.

## 8. Thành viên hoặc quan hệ tham gia (Membership)

- Định nghĩa ngắn: một dạng affiliation, thường để mô tả đang thuộc về một tổ chức hoặc scope nào đó.
- Ví dụ thực tế: một hộ là thành viên của tổ chức vận hành A.
- Dùng trong module: xuất hiện chủ yếu trong enum `ActorAffiliationKind.membership`.
- Source of truth: Có, như một loại affiliation fact. Không phải source of truth cho quyền.

## 9. Quyền được cấp riêng (Permission Grant)

- Định nghĩa ngắn: hợp đồng authority rõ ràng cho phép xem, sửa, duyệt hoặc gọi tool.
- Ví dụ thực tế: cấp riêng quyền duyệt release lot cho một vai trò đặc biệt.
- Dùng trong module: hiện mới ở lớp draft contract trong actor authority docs và models định hướng.
- Source of truth: Chưa. Đây là roadmap lane, chưa là runtime authority engine đầy đủ.

## 10. Vai trò đóng góp (Contribution Role)

- Định nghĩa ngắn: vai trò của actor trong một fact đóng góp cụ thể.
- Ví dụ thực tế: người dẫn khách, người cung cấp xe, người đóng góp nội dung, người góp vốn.
- Dùng trong module: xuất hiện theo ngữ nghĩa ở project contribution lane.
- Source of truth: Có cho fact đóng góp. Không phải source of truth cho quyền.

## 11. Sổ cái đóng góp (Contribution Ledger)

- Định nghĩa ngắn: lane append-only ghi nhận ai đã đóng góp gì cho một project scope.
- Ví dụ thực tế: ghi lại chị Lan đóng góp 2 ngày công và một xe tải cho dự án X.
- Dùng trong module: `app/services/project_contributions.py`, `app/api/routes/project_scopes.py`, các view project contribution.
- Source of truth: Có, cho contribution facts của project scope.

## 12. Gán phạm vi dự án (Project Assignment)

- Định nghĩa ngắn: liên kết một record nghiệp vụ với một project scope.
- Ví dụ thực tế: gắn order A vào dòng giá trị gạo sạch; gắn lot B vào chương trình sinh kế C.
- Dùng trong module: `app/models/project_assignments.py`, `app/services/project_assignments.py`.
- Source of truth: Có, cho assignment fact.

## 13. Nguồn lực dùng chung (Shared Resource)

- Định nghĩa ngắn: tài nguyên được nhiều project scope cùng sử dụng.
- Ví dụ thực tế: xe tải, kho chung, sân phơi, labor pool, marketing budget.
- Dùng trong module: `app/models/shared_resources.py`, `app/services/shared_resources.py`, `app/api/routes/shared_resources.py`.
- Source of truth: Có, là runtime lane hiện có.

## 14. Khách hàng chuẩn (Customer Profile)

- Định nghĩa ngắn: hồ sơ khách hàng mà lõi hệ thống dùng để giữ thông tin khách mua.
- Ví dụ thực tế: chị Hằng mua gạo đều mỗi tháng, có lịch sử preorder và order.
- Dùng trong module: `app/models/customers.py`, `app/services/customers.py`, `app/api/routes/customers.py`.
- Source of truth: Có, là aggregate runtime hiện có.

## 15. Cam kết mua trước (Preorder)

- Định nghĩa ngắn: cam kết số lượng của khách trước khi giao hàng thực tế hoàn tất.
- Ví dụ thực tế: khách đặt trước 200 kg gạo cho đợt thu hoạch tháng sau.
- Dùng trong module: `app/models/preorders.py`, `app/services/preorders.py`, `app/api/routes/preorders.py`.
- Source of truth: Có.

## 16. Đơn hàng bán (Sales Order / Order)

- Định nghĩa ngắn: yêu cầu thực hiện giao dịch cụ thể để đóng gói, giao và chốt giao.
- Ví dụ thực tế: đơn giao 50 kg gạo cho khách vào ngày mai.
- Dùng trong module: `app/models/orders.py`, `app/services/orders.py`, `app/api/routes/orders.py`.
- Source of truth: Có.

## 17. Lô hàng (Lot / LotBatch)

- Định nghĩa ngắn: lô vật lý có số lượng hữu hạn để phân bổ cho order.
- Ví dụ thực tế: lô gạo thành phẩm từ vụ hè thu 2026 còn 320 kg khả dụng.
- Dùng trong module: `app/models/lots.py`, `app/services/lots.py`, `app/api/routes/lots.py`.
- Source of truth: Có.

## 18. Phân bổ (Allocation)

- Định nghĩa ngắn: bản ghi nối giữa order line và lot để giữ chỗ hoặc tiêu thụ số lượng.
- Ví dụ thực tế: lấy 40 kg từ lô LOT-001 để phục vụ order ORD-001.
- Dùng trong module: `app/models/orders.py`, `app/services/orders.py`, `app/store/orders.py`.
- Source of truth: Có.

## 19. Kiểm định chất lượng (QC Review)

- Định nghĩa ngắn: quyết định kiểm chất lượng cho một lot.
- Ví dụ thực tế: reviewer xác nhận lô đủ chứng cứ và cho phép release.
- Dùng trong module: `app/models/lots.py`, `app/services/lots.py`.
- Source of truth: Có cho quyết định QC. Không đồng nghĩa với toàn bộ trạng thái lot.

## 20. Sự kiện miền nghiệp vụ (Domain Event)

- Định nghĩa ngắn: fact đã xảy ra, được ghi append-only để truy vết và dựng read model.
- Ví dụ thực tế: `order.confirmed`, `preorder.activated`, `lot.released`.
- Dùng trong module: `app/core/events.py`, `app/services/*`, `app/api/routes/events.py`.
- Source of truth: Có, cho lane event log.

## 21. Nhật ký audit (Audit Log)

- Định nghĩa ngắn: nhật ký quyết định cho phép, từ chối, leo thang hoặc thất bại của các action nhạy cảm.
- Ví dụ thực tế: từ chối bypass request; yêu cầu approval khi cancel order đã packed.
- Dùng trong module: `app/services/audit.py`, `app/api/routes/audit.py`, `app/store/audit.py`.
- Source of truth: Có, cho audit facts.

## 22. Quyền hạn đang enforce (Authority)

- Định nghĩa ngắn: tập điều kiện mà runtime hiện tại thật sự dùng để cho hoặc chặn hành động.
- Ví dụ thực tế: chỉ `qc_reviewer` mới được ra quyết định QC; một số write lane chỉ cho founder, super admin, admin hoặc ops.
- Dùng trong module: `app/core/authz.py`, `app/services/read_authz.py`, service layer của orders, lots, preorders, projects.
- Source of truth: Có, nhưng hiện chủ yếu là role-based enforcement trong service layer.

## 23. Tài khoản đăng nhập (User Account)

- Định nghĩa ngắn: chủ thể phục vụ đăng nhập hoặc xác thực, không nhất thiết trùng hoàn toàn với Actor Identity canonical.
- Ví dụ thực tế: một nhân viên dùng tài khoản đăng nhập riêng nhưng actor record của họ là hồ sơ chủ thể trong domain.
- Dùng trong module: hiện chưa là aggregate canonical đầy đủ trong runtime app.
- Source of truth: Chưa có lane canonical đầy đủ trong runtime hiện tại.

## 24. Ràng buộc kênh giao tiếp (Communication Binding)

- Định nghĩa ngắn: liên kết với kênh như Zalo group, Facebook chat hoặc công cụ ngoài để nhận tín hiệu giao tiếp.
- Ví dụ thực tế: một nhóm Zalo dùng để điều phối vận hành giữa các thành viên dự án.
- Dùng trong module: hiện chủ yếu là integration concern hoặc future lane.
- Source of truth: Không. Đây không phải source of truth cho quyền.

## 25. Lõi xác định sự thật (Deterministic Core)

- Định nghĩa ngắn: phần hệ thống giữ write path chuẩn, state transition, event, audit và idempotency.
- Ví dụ thực tế: order chỉ được chuyển trạng thái qua service và gateway thay vì sửa trực tiếp database.
- Dùng trong module: `app/core/`, `app/services/`, `app/store/`.
- Source of truth: Có, đây là nguyên tắc kiến trúc và là runtime lane đang chạy.