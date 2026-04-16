# ProjectScope

## Nói ngắn gọn

`ProjectScope` là phạm vi dự án mềm để gom nghĩa kinh doanh.

Nó giúp hệ thống trả lời các câu hỏi như:
- dòng giá trị này đang lời hay lỗ
- dự án này dùng chung nguồn lực nào
- ai đã đóng góp gì
- order, preorder, lot, plot nào đang được quy về phạm vi nào

## 1. Tại sao gọi là soft scope

`ProjectScope` không phải hard global boundary.

Điều đó có nghĩa:
- nó không thay thế `Organization`
- nó không thay thế tenant boundary
- nó không tự quyết định quyền runtime
- nó là lớp gán nghĩa và gom đo lường

## 2. Ví dụ thực tế

- Dòng giá trị gạo sạch vụ hè thu 2026.
- Chương trình sinh kế cho 20 hộ nông dân.
- Tuyến trải nghiệm nông trại cuối tuần.
- Product line quà tặng nông sản.

## 3. Runtime hiện có gì

Theo models, services, routes hiện tại:
- create
- update
- activate
- pause
- close
- archive
- assignment sang plot, crop cycle, lot, preorder, order
- contribution ledger
- cost record lane đầu tiên
- revenue record lane đầu tiên
- reporting views theo project

## 4. Trường dữ liệu chính

- `projectScopeId`
- `organizationId`
- `projectScopeCode`
- `name`
- `projectScopeType`
- `status`
- `seasonYear`
- `ownerActorId`
- `description`
- `parentProjectScopeId`

## 5. Không nên nhầm với

### Task list hoặc PM board

ProjectScope không phải danh sách công việc.

### Organization

Organization là chủ thể vận hành. ProjectScope là lớp gom nghĩa dưới organization.

### Permission boundary

ProjectScope có thể là context cho authority sau này, nhưng runtime hiện tại chưa phải full ABAC engine.

## 6. Source of truth không

Có. Đây là aggregate runtime đã ship.