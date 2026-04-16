# Tổng Quan Hệ Thống

## Nói ngắn gọn

AgriOS không phải chỉ là app quản lý đơn hàng hay app quản lý nông trại.

AgriOS là một lõi vận hành dùng để giữ sự thật chung cho nhiều hoạt động:
- tổ chức nào đang vận hành cái gì
- ai đang tham gia hoặc đóng góp vào dòng giá trị nào
- khách nào đã cam kết mua trước
- đơn hàng nào đang được thực hiện
- lô hàng nào còn bao nhiêu
- chi phí, doanh thu và tác động đang được ghi về phạm vi nào
- ai được xem, ai được sửa, ai chỉ được đề xuất

## Câu chuyện nghiệp vụ theo thứ tự dễ hiểu

### 1. Một người tạo Organization

`Organization` là tổ chức hoặc chủ thể vận hành.

Ví dụ thực tế:
- một hộ gia đình có thương hiệu nông sản riêng
- một nhóm khởi nghiệp vận hành chuỗi cung ứng nhỏ
- một hợp tác xã
- một đơn vị đứng ra gom hàng, bán hàng và điều phối sản xuất

Tổ chức này là nơi hệ thống trả lời câu hỏi: “Hoạt động này thuộc về ai về mặt vận hành?”

### 2. Organization khai báo tài sản và nguồn lực

Tổ chức có thể có:
- đất hoặc vùng sản xuất
- vụ trồng
- lô hàng sau thu hoạch
- kho, sân phơi, xe, đội nhân công, ngân sách marketing

Trong runtime hiện tại, một phần tài sản đã có aggregate riêng như plot, crop cycle, lot, shared resource. Một số tài sản khác vẫn còn là lane mở rộng về sau.

### 3. Organization tạo ProjectScope

`ProjectScope` là phạm vi dự án mềm hoặc dòng giá trị mềm.

Ví dụ thực tế:
- dòng giá trị gạo sạch vụ hè thu
- chương trình cải thiện sinh kế cho 20 hộ
- tuyến sản phẩm quà tặng nông sản
- dịch vụ tham quan nông trại cuối tuần

Nó là lớp gom nghĩa kinh doanh, chứ không phải biên cứng toàn hệ thống.

### 4. Actor tham gia hoặc đóng góp

`Actor Identity` là hồ sơ chủ thể mà hệ thống ghi nhận.

Một actor có thể là:
- một người
- một hộ gia đình
- một ghế đại diện cho tổ chức
- một automation principal

Actor có thể có quan hệ mềm với tổ chức hoặc project, và cũng có thể phát sinh đóng góp tại từng sự kiện cụ thể.

### 5. Mỗi action quan trọng được ghi lại thành event

Ví dụ:
- tạo khách hàng mới
- xác nhận preorder
- phân bổ order vào lot
- ghi nhận đóng góp vào project
- kích hoạt organization

Các event này giúp audit, truy vết và dựng read model.

### 6. Contribution ghi nhận ai đóng góp gì

`Contribution Ledger` là lane ghi nhận đóng góp theo project scope.

Đóng góp có thể là:
- công sức
- tài sản dùng chung
- khách hàng mang về
- nội dung
- vốn
- vận hành

Nó không phải là permission, cũng không tự sinh ra quyền.

### 7. Permission quyết định ai được xem hoặc sửa

Runtime hiện tại mới đang enforce theo role và check trong service layer.

`Permission Grant` đầy đủ vẫn là roadmap. Hiện tại không được viết docs như thể engine đó đã chạy rồi.

### 8. ProjectScope dùng để đo tác động, lời lỗ và phân bổ nguồn lực

Trong runtime hiện tại, ProjectScope đã có:
- create, update, activate, pause, close, archive
- assignment cho plot, crop cycle, lot, preorder, order
- contribution ledger
- cost record lane đầu tiên
- revenue record lane đầu tiên
- các view tổng hợp theo project

### 9. Deterministic Core giữ source of truth

Phần lõi xác định sự thật hiện đang nắm các lane chính:
- customer
- preorder
- order
- lot
- allocation
- inventory related facts
- authz checks đang chạy
- audit log
- domain events

### 10. AI chỉ hỗ trợ điều phối

AI có thể:
- đọc
- tóm tắt
- hỏi thiếu dữ liệu
- gợi ý action
- tạo draft

AI không được:
- sửa raw truth trực tiếp
- tự suy quyền từ membership hay contribution
- bypass policy

## Hiện trạng định hướng

AgriOS bây giờ là nền tảng mở cho nhiều organization tự vận hành.

Nó không còn nên được mô tả như một hệ chỉ phục vụ nội bộ một hợp tác xã duy nhất.

## Tài liệu nào giải thích phần nào

- Thuật ngữ: `docs/01-glossary/glossary.md`
- Runtime hiện có: `docs/02-current-runtime/current-runtime-overview.md`
- Mô hình domain: `docs/03-domain-model/`
- Luồng nghiệp vụ: `docs/04-core-workflows/`
- Ranh giới AI: `docs/06-agent-boundary/agent-principles.md`
- Phân biệt hiện tại và tương lai: `docs/07-roadmap/current-vs-future.md`