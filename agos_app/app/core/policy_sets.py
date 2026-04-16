from __future__ import annotations

from app.models.enums import ActorRole


FOUNDATION_ADMIN_ROLES = frozenset(
    {
        ActorRole.founder.value,
        ActorRole.super_admin.value,
        ActorRole.admin.value,
    }
)

PROJECT_FINANCE_ROLES = frozenset({*FOUNDATION_ADMIN_ROLES, ActorRole.accountant.value})

LOT_OPERATIONS_ROLES = frozenset(
    {
        *FOUNDATION_ADMIN_ROLES,
        ActorRole.ops.value,
        ActorRole.farm_manager.value,
    }
)

LOT_QC_ROLES = frozenset({*LOT_OPERATIONS_ROLES, ActorRole.qc_reviewer.value})

PROJECT_CONTRIBUTION_BOARD_READ_ROLES = frozenset({*PROJECT_FINANCE_ROLES, ActorRole.viewer.value})

PROJECT_PNL_READ_ROLES = PROJECT_FINANCE_ROLES

PROJECT_ORDER_ALLOCATION_READ_ROLES = frozenset(
    {
        *PROJECT_FINANCE_ROLES,
        ActorRole.sales.value,
        ActorRole.ops.value,
        ActorRole.viewer.value,
    }
)

SHARED_RESOURCE_ALLOCATION_READ_ROLES = frozenset(
    {
        *PROJECT_FINANCE_ROLES,
        ActorRole.ops.value,
        ActorRole.farm_manager.value,
        ActorRole.viewer.value,
    }
)

PROJECT_SCOPED_EVENT_QUERY_ROLES = frozenset(
    {
        ActorRole.admin.value,
        ActorRole.accountant.value,
        ActorRole.viewer.value,
    }
)

UNSCOPED_EVENT_QUERY_ROLES = frozenset({ActorRole.founder.value, ActorRole.super_admin.value})