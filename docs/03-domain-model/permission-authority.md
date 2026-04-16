# Permission Và Authority

## Nói ngắn gọn

Runtime hiện tại có authority thật, nhưng chưa phải full permission platform.

Đây là chỗ dễ bị trộn nhất, nên phải tách rất rõ.

## 1. Membership khác Permission Grant thế nào

### Membership hoặc Affiliation

- nói ai đang thuộc về đâu
- là context fact
- không tự cho quyền execute action

### Permission Grant

- nói ai được làm gì
- là authority fact
- hiện mới là roadmap lane, chưa là runtime engine hoàn chỉnh

## 2. Contribution Role khác Authority thế nào

### Contribution Role

- nói actor tham gia theo kiểu gì trong một contribution fact
- ví dụ: người hỗ trợ, người góp vốn, người dẫn khách

### Authority

- nói actor hoặc request context có được đọc, sửa, approve, execute hay không
- runtime hiện enforce chủ yếu qua role và service checks

## 3. Zalo group khác authority thế nào

Một nhóm Zalo có thể là nơi giao tiếp, nhắc việc hoặc phát tín hiệu vận hành.

Nhưng nó không phải source of truth cho quyền.

Việc ở trong group chat không tự động có nghĩa là:
- được sửa order
- được approve release lot
- được xem audit log
- được gọi tool nhạy cảm

## 4. AI Agent có được suy quyền từ membership hoặc contribution không

Không.

Đây là nguyên tắc cứng.

Agent chỉ được dùng lớp authority mà runtime hiện tại đang enforce.

## 5. Runtime authority hiện chạy bằng gì

- enum roles
- role normalization
- service-level checks
- protected read surfaces
- audit deny hoặc escalate

## 6. Roadmap authority sẽ đi về đâu

Tương lai có thể thêm:
- `PermissionGrant` runtime lane
- delegated permission runtime
- field-level masking
- tool gateway
- org or project aware ABAC

Nhưng hiện tại không được viết docs như thể những lane đó đã chạy.