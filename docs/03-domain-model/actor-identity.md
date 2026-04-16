# Actor Identity

## Nói ngắn gọn

`Actor Identity` là hồ sơ chủ thể mà hệ thống ghi nhận. Nó không nên bị đồng nhất với tài khoản đăng nhập.

## 1. Actor Identity khác User Account thế nào

### Actor Identity

- là chủ thể domain
- dùng để ghi contribution, affiliation, ownership context và authority context
- có thể là person, household, organization actor hoặc automation principal

### User Account

- là chủ thể phục vụ đăng nhập hoặc xác thực
- có thể map tới một actor, nhưng không phải lúc nào cũng là cùng một lớp dữ liệu

Ví dụ:
- một người dùng đăng nhập bằng tài khoản nội bộ
- nhưng actor canonical của họ là người đại diện của một hộ sản xuất

## 2. Runtime hiện có gì

Lane baseline hiện có:
- `POST /api/v1/actors`
- `GET /api/v1/actors/{actor_id}`
- `POST /api/v1/affiliations`

Các loại actor hiện có trong enum:
- `person`
- `household`
- `organization_actor`
- `automation_principal`

## 3. Affiliation là gì

Affiliation là fact actor đang có quan hệ mềm với organization hoặc project scope nào đó.

Ví dụ:
- một người là contractor của dự án A từ tháng 4 đến tháng 6
- một household là membership của organization B

## 4. Membership khác Permission Grant thế nào

### Membership hoặc Affiliation

- là context fact
- trả lời câu hỏi “đang gắn với ai hoặc phạm vi nào”
- không tự sinh quyền runtime

### Permission Grant

- là authority fact
- trả lời câu hỏi “được làm gì”
- runtime đầy đủ cho lane này chưa ship

## 5. AI có được suy quyền từ actor affiliation không

Không.

Agent không được suy quyền từ:
- membership
- affiliation
- contribution role
- group chat binding

## 6. Source of truth không

- Actor Identity baseline: Có, ở mức lane runtime đầu tiên.
- User Account canonical aggregate: Chưa có lane runtime đầy đủ.