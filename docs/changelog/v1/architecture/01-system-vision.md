# 01. System Vision

## 1. Hệ thống này tồn tại để giải quyết bài toán gì

Hệ thống này không phải chỉ là:
- một app bán nông sản
- một ERP
- một CRM
- hay một chatbot AI

Nó là **Agri OS Core**: lớp điều phối chung cho chuỗi:

**khách hàng → preorder / order → lot / kho → đồng ruộng cơ bản → giao hàng → học lại từ hành vi khách**

Mục tiêu trước mắt không phải làm “đủ mọi thứ”.  
Mục tiêu là làm cho đội vận hành:
- quản lý được khách hàng
- quản lý được preorder và order
- quản lý được lot và tồn khả dụng
- quản lý được plot / crop cycle ở mức đủ dùng
- phân quyền nhìn dữ liệu rõ ràng
- có event log để biết chuyện gì đã xảy ra
- rồi sau đó mới thêm lớp AI/Agent

## 2. Hệ thống này là gì, và không phải là gì

### 2.1 Nó là gì
Nó là một **deterministic operating core**:
- giữ truth liên thông giữa nhiều hệ
- giữ workflow cứng
- giữ state chính
- giữ event log và audit
- giữ role-based views

### 2.2 Nó không phải là gì
Nó không phải là nơi:
- làm nông học sâu như một farm app chuyên biệt
- làm sổ sách kế toán cuối cùng như ERP
- làm toàn bộ inbox, campaign, omnichannel như CRM
- để AI tự do “sửa dữ liệu cho tiện”

## 3. North Star của hệ

Nếu làm đúng, sau 2 năm hệ này sẽ trở thành:

- **một nguồn sự thật vận hành** cho chuỗi nông nghiệp - bán hàng
- **một lớp điều phối chung** giữa LiteFarm, ERP, CRM và các kênh ngoài
- **một bộ dashboard theo role**
- **một nền để cắm AI/Agent an toàn**

Nói dễ hiểu:
- hôm nay build để chạy được công việc thật
- ngày mai mở rộng được mà không đập đi làm lại

## 4. Ba nguyên tắc kiến trúc phải giữ

### 4.1 Deterministic core trước
Những thứ không được sai phải chốt rất chắc:
- customer canonical identity
- preorder
- order
- lot / allocation
- inventory movement
- plot / crop cycle cơ bản
- payment status vận hành
- permission
- event log

### 4.2 AI không được định nghĩa sự thật hệ thống
AI chỉ nên:
- hiểu input mơ hồ
- hỏi thiếu thông tin
- gợi ý việc nên làm tiếp
- gợi ý chăm khách
- tóm tắt, báo cáo, nhắc việc

AI không được tự chốt:
- available quantity cuối cùng
- allocation cuối cùng
- trạng thái đơn hàng cuối cùng
- payment cuối cùng
- permission
- accounting / tax final

### 4.3 Một loại dữ liệu chỉ nên có một nguồn sự thật chính
Ví dụ:
- canonical customer identity: Agri OS Core
- preorder / order / lot / allocation: Agri OS Core
- accounting final: ERP
- field ops sâu: LiteFarm
- omnichannel conversation: CRM

## 5. Các actor chính

### Founder / điều phối trung tâm
Cần thấy:
- khách hàng
- preorder / order
- trạng thái lô
- tồn khả dụng
- tình hình đồng ruộng cơ bản
- cảnh báo tắc nghẽn
- các action nhạy cảm cần duyệt

### Sales / CSKH
Cần thấy:
- customer profile
- lịch sử mua
- preorder còn bao nhiêu
- trạng thái giao hàng
- preference và segment cơ bản

### Ops / kho / đóng gói
Cần thấy:
- đơn cần chuẩn bị
- lot nào đã release
- tồn khả dụng
- trạng thái packing / delivery
- ngoại lệ thiếu hàng hoặc lệch số lượng

### Farm Manager / quản lý vùng trồng
Cần thấy:
- plot
- crop cycle
- growth stage
- expected harvest
- lot đã tạo
- tình trạng lot bị block / chờ release

### Kế toán / tài chính
Cần thấy:
- order đã giao / chưa giao
- payment status vận hành
- dữ liệu nào đã sync ERP
- dữ liệu nào là operational, dữ liệu nào là final accounting

### Agent / automation
Là actor kỹ thuật, không phải user chính.  
Agent chỉ được đọc và đề xuất trong phạm vi role mà nó phục vụ.

## 6. Agri OS Core đứng ở đâu giữa các hệ khác

- **LiteFarm**: giữ dữ liệu field ops và nông học sâu
- **ERP**: giữ accounting final, invoice, journal, stock/accounting chuẩn khi phase đủ chín
- **CRM / Omnichannel**: giữ hội thoại và lifecycle interactions
- **Agri OS Core**: giữ orchestration truth cho chuỗi vận hành

Xem bản vẽ tổng thể ở:
- [System Context Diagram](../agri_diagrams/01-system-context-diagram.md)
- [Domain Ownership / Context Map](../agri_diagrams/02-domain-ownership-context-map.md)

## 7. Workflow đầu tiên phải chứng minh được giá trị

Workflow ưu tiên số 1 là:

1. tạo customer
2. tạo preorder
3. theo dõi quota
4. tạo lot thu hoạch
5. release lot
6. allocate lot vào order
7. pack
8. deliver
9. cập nhật lịch sử mua và preference

Nếu workflow này chạy được end-to-end, team sẽ học ra:
- entity nào thật sự cần
- source of truth nào còn mơ hồ
- state nào đang thiếu
- event nào phải có để debug
- điểm nào nên tích hợp system ngoài
- điểm nào sau này AI có thể hỗ trợ

## 8. Ba giai đoạn phát triển

### Giai đoạn 1 - Core vận hành
Phải chạy được:
- customer
- preorder
- order
- lot
- allocation
- delivery
- plot / crop cycle cơ bản
- permission
- event log

### Giai đoạn 2 - Tích hợp và ổn định
Phải có:
- sync ERP / LiteFarm / CRM
- read models theo role
- dashboard hành vi khách hàng cơ bản
- cảnh báo tắc nghẽn

### Giai đoạn 3 - Agent layer
Mới thêm:
- canonical intake bằng AI
- AI draft / suggest
- AI chăm khách theo policy
- AI tóm tắt vận hành
- supervisor agent điều phối nhiều sub-agent

## 9. Tiêu chí “đúng hướng” khi vibe coding

Một thay đổi được coi là đúng hướng nếu:
- giúp workflow thật chạy tốt hơn
- không tạo thêm source of truth thứ hai
- giữ được event log và audit
- không mở quyền cho AI quá sớm
- vẫn còn đường tiến hóa sau này

## 10. Kết luận

Tài liệu này chỉ làm một việc:
**giữ cho team không quên vì sao hệ thống này tồn tại**.

Nếu sau này code nhanh mà thấy bắt đầu lệch, quay lại hỏi 3 câu:
1. Workflow thật nào đang được phục vụ?
2. Source of truth của dữ liệu này ở đâu?
3. AI đang hỗ trợ hay đang lấn vào lõi?
