# ADR-014: Authority model separates identity, affiliation, contribution, and grant

**Status:** Accepted
**Date:** 2026-04-16
**Deciders:** Architecture team, Founder/Product

---

## Context

Agri OS runtime đã có `Organization`, `ProjectScope`, `ProjectAssignment`, contribution ledger, economics baseline, role-based authz, và AI advisory boundaries. Epic tiếp theo cần thêm semantics cho actor identity, affiliation, contribution, và authority mà không làm membership, contribution role, chat binding, hay `ProjectScope` soft scope bị hiểu nhầm thành runtime permission source. Nếu không chốt decision này trước, code rất dễ trộn context facts với authority facts, làm drift audit, over-grant access, và phá rule AI không được tự suy diễn quyền.

## Decision

Chúng ta sẽ giữ bốn lớp riêng: `Actor Identity`, `Membership/Affiliation`, `Contribution Role`, và `Permission Grant`. Trong current repo, authority runtime tiếp tục đến từ baseline runtime roles và explicit policy checks; membership, stewardship, contribution role, và communication bindings chỉ là context/fact layers, không tự sinh read/write/approve/tool permission. Nếu Agri OS tiến tới canonical `PermissionGrant` runtime lane, decision đó phải có ADR riêng thay vì nhồi vào ADR này.

## Trade-offs

**Gains:**
- Giữ audit, authz, và agent guardrails nhất quán: context không bị dùng như authority ngầm.
- Cho phép rollout additive actor/contribution semantics ngay mà không phải rewrite write path hoặc biến `ProjectScope` thành hard boundary.

**Costs:**
- Phải chịu thêm docs/policy work và một thời gian song song giữa runtime role baseline với future grant model.
- Một số UX như role template, scope picker, permission preview chỉ có thể ship docs-first hoặc policy-first trước khi có grant engine.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Suy quyền trực tiếp từ membership hoặc stewardship | Dễ over-grant access và phá nguyên tắc context != authority. |
| Suy quyền từ contribution role hoặc chat/channel binding | Contribution và communication chỉ là fact/signal, không phải permission source. |
| Biến `ProjectScope` thành hard permission boundary ngay | Blast radius lớn, trái với ADR-013 và rollout additive hiện tại. |

## Migration Impact

**Scope:** Medium

- Code: current slices chỉ được thêm actor/contribution semantics và audit hardening, không được ngầm tạo authority mới.
- Data: future `Actor`, `Affiliation`, `PermissionGrant`, `AgentSessionScope` models phải rollout riêng theo docs/ADR sau.
- Contracts: docs/OpenAPI có thể thêm policy artifacts hoặc future sections, nhưng current runtime contracts phải giữ backward-compatible.
- Deployment: áp dụng theo thứ tự ADR -> architecture docs -> code slices -> future grant ADR nếu lane đó được chốt.

## Revisit Conditions

Revisit khi team chốt canonical `PermissionGrant` runtime lane, agent session scope/tool gateway runtime, hoặc khi org/project-scoped ABAC cần trở thành authority source được enforce thay cho baseline role gates hiện tại.