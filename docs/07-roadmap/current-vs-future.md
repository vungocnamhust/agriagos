# Current Runtime Vs Future Roadmap

## Nói ngắn gọn

Đây là file quan trọng nhất để tránh viết docs tương lai như thể đã có trong hệ thống.

## Lớp A: Current Runtime

### Đã có trong code và API

- Organization runtime lane
- ProjectScope runtime lane
- Actor Identity baseline lane
- Actor Affiliation baseline lane
- Shared Resource runtime lane
- Customer runtime lane
- Preorder runtime lane
- Order runtime lane
- Lot runtime lane
- Allocation related write flows
- Project Assignment lane
- Project Contribution lane
- Cost Record lane đầu tiên
- Revenue Record lane đầu tiên
- Financial Allocation lane đầu tiên
- Views cho customer, farm, lots, fulfillment, project summaries
- Shared-resource allocation summary board
- Event query lane
- Audit query lane

### Đã có trong event và authz reality

- dotted lowercase domain events
- audit decision log
- role-based write checks
- protected read surfaces
- deny và audit bypass request
- idempotency check

## Lớp B: Future Roadmap

### Chưa được mô tả như feature đã có

- canonical Actor aggregate mở rộng hơn baseline hiện tại
- ActorIdentityBinding runtime đầy đủ
- Membership hoặc Affiliation runtime lane mở rộng
- full PermissionGrant engine
- role-template expansion engine
- field-level masking engine
- Agent Session Scope runtime
- Tool Gateway runtime
- full org or project aware ABAC
- full delegated permission runtime

## Nguyên tắc viết docs

- Nếu chưa có route, service, store, event hoặc enforcement thật thì không gọi là current runtime.
- Nếu mới có draft doc hoặc draft contract thì phải gắn nhãn future hoặc deferred.
- Nếu current và future cùng được nhắc trong một file, luôn tách thành hai khối riêng.