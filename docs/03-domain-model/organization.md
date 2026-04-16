# Organization

## Nói ngắn gọn

`Organization` là chủ thể vận hành của hệ thống, không chỉ là một cái nhãn để gắn record.

Nếu không có organization, hệ thống sẽ khó trả lời câu hỏi cơ bản nhất: hoạt động này thuộc ai về mặt vận hành.

## 1. Organization dùng để làm gì

- giữ danh tính vận hành cơ bản
- gom hoạt động farm và commercial dưới cùng một chủ thể
- làm parent cho `ProjectScope`
- làm mốc để gắn actor affiliation, tài sản, đơn hàng và lô hàng

## 2. Ví dụ thực tế

- Hộ gia đình A có thương hiệu gạo riêng.
- Một startup operator đứng ra tổ chức nguồn hàng và bán lẻ.
- Một hợp tác xã vận hành nhiều hộ thành viên.

## 3. Cái gì thuộc về organization trong runtime hiện tại

Theo models và services hiện có:
- `organizationId`
- `organizationCode`
- `name`
- `organizationType`
- `status`
- `region`
- `localitySummary`
- `representativeName`
- `contactPhone`
- `contactEmail`
- `shortDescription`

## 4. Trạng thái hiện có

Theo `app/models/enums.py`:
- `draft`
- `active`
- `paused`
- `closed`

## 5. Không nên nhầm với

### Tenant

`Tenant` là boundary triển khai hoặc integration concern. Nó không phải business owner aggregate.

### Brand

Brand là hình ảnh kinh doanh người ngoài nhìn thấy. Runtime hiện tại chưa tách brand thành aggregate riêng.

### Customer

Customer là người mua. Organization là chủ thể vận hành.

## 6. Source of truth không

Có. Đây là aggregate runtime đã ship.