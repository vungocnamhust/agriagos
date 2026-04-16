from uuid import UUID

from fastapi import HTTPException

from app.core.policy_sets import (
    PROJECT_CONTRIBUTION_BOARD_READ_ROLES,
    PROJECT_ORDER_ALLOCATION_READ_ROLES,
    PROJECT_PNL_READ_ROLES,
    SHARED_RESOURCE_ALLOCATION_READ_ROLES,
)
from app.models.enums import CropCycleStatus, GrowthStage, LotStatus, ProjectContributionStatus
from app.models.farm import CropCycleSummary, FarmView, PlotSummary
from app.models.common import Meta
from app.models.orders import OrderDetail, OrderLine
from app.models.preorders import PreorderDetail
from app.models.views import (
    AvailableLotListResponse,
    AvailableLotView,
    Customer360View,
    CustomerPreferenceItem,
    FarmSummaryBoardItem,
    FarmSummaryBoardResponse,
    PendingFulfillmentListResponse,
    PendingFulfillmentView,
    ProjectContributionLedgerItem,
    ProjectContributionLedgerResponse,
    ProjectImpactedActorSummaryItem,
    ProjectImpactedActorSummaryResponse,
    ProjectContributionSummaryItem,
    ProjectContributionSummaryResponse,
    ProjectOrderAllocationSummaryItem,
    ProjectOrderAllocationSummaryResponse,
    ProjectPnlSummaryItem,
    ProjectPnlSummaryResponse,
    SharedResourceAllocationSummaryItem,
    SharedResourceAllocationSummaryResponse,
)
from app.services.read_authz import authorize_read_surface
from app.services import customers as cust_svc
from app.services import farm as farm_svc
from app.store import postgres_sync
from app.store import views as view_store
from app.store import memory as memory_store
from app.store.memory import (
    list_crop_cycles,
    list_customer_preferences,
    list_customers,
    list_lots,
    list_orders,
    list_plots,
    list_preorders,
)


# Phase 1 board scope follows the gateway-enforced subset of order states.
# "shipped" remains visible until delivery confirmation closes the workflow.
PENDING_FULFILLMENT_STATUSES = frozenset({"confirmed", "allocated", "packed", "shipped"})
FARM_BOARD_ACTIVE_CYCLE_STATUSES = frozenset({"planned", "active", "near_harvest", "harvested"})


def _order_code_desc(record: dict[str, object]) -> str:
    order_code = record.get("orderCode")
    return str(order_code) if order_code is not None else ""


def _preorder_code_desc(record: dict[str, object]) -> str:
    preorder_code = record.get("preorderCode")
    return str(preorder_code) if preorder_code is not None else ""


def _preference_sort_key(record: dict[str, object]) -> tuple[str, str]:
    return (str(record.get("preferenceType") or ""), str(record.get("preferenceValue") or ""))


def _normalize_growth_stage(value: object) -> GrowthStage | None:
    if value == "flowering_or_maturing":
        value = "maturing"
    if isinstance(value, GrowthStage):
        return value
    if isinstance(value, str):
        try:
            return GrowthStage(value)
        except ValueError:
            return None
    return None


def _crop_cycle_status(value: object) -> CropCycleStatus | None:
    if isinstance(value, CropCycleStatus):
        return value
    if isinstance(value, str):
        try:
            return CropCycleStatus(value)
        except ValueError:
            return None
    return None


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _float_value(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _validate_optional_project_scope_id(project_scope_id: str | None) -> None:
    if project_scope_id is None:
        return
    try:
        UUID(project_scope_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="projectScopeId must be a valid UUID.") from exc


def get_customer_360(customer_id: str) -> Customer360View:
    if postgres_sync.is_enabled():
        try:
            UUID(customer_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Customer not found.") from exc
        data = view_store.fetch_customer_360(customer_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Customer not found.")
        return Customer360View(**data)

    customer = cust_svc.get_customer(customer_id)

    active_preorders = [
        PreorderDetail(**p)
        for p in sorted(list_preorders(), key=_preorder_code_desc, reverse=True)
        if p["customerId"] == customer_id and p["status"] == "active"
    ]

    recent_orders = [
        OrderDetail(**{**o, "lines": [OrderLine(**ln) for ln in o.get("lines", [])]})
        for o in sorted(list_orders(), key=_order_code_desc, reverse=True)
        if o["customerId"] == customer_id
    ][:10]

    preferences = [
        CustomerPreferenceItem(
            preferenceType=p["preferenceType"],
            preferenceValue=p["preferenceValue"],
            confidenceLevel=p["confidenceLevel"],
        )
        for p in sorted(list_customer_preferences(customer_id), key=_preference_sort_key)
    ]

    return Customer360View(
        customer=customer,
        activePreorders=active_preorders,
        recentOrders=recent_orders,
        preferences=preferences,
    )


def get_available_lots_board(product_sku_id: str | None = None) -> AvailableLotListResponse:
    if postgres_sync.is_enabled():
        lots = [AvailableLotView(**row) for row in view_store.fetch_available_lots_board(product_sku_id)]
        return AvailableLotListResponse(items=lots)

    lots = [
        AvailableLotView(
            lotId=lot["lotId"],
            lotCode=lot["lotCode"],
            organizationId=lot.get("organizationId"),
            productSkuId=lot["productSkuId"],
            releasedQty=lot["releasedQty"],
            availableQty=lot["availableQty"],
            status=LotStatus.released,
        )
        for lot in list_lots()
        if lot["status"] == "released" and lot["availableQty"] > 0
        and (product_sku_id is None or lot["productSkuId"] == product_sku_id)
    ]
    return AvailableLotListResponse(items=lots)


def get_pending_fulfillment() -> PendingFulfillmentListResponse:
    if postgres_sync.is_enabled():
        items = [PendingFulfillmentView(**row) for row in view_store.fetch_pending_fulfillment_board()]
        return PendingFulfillmentListResponse(items=items)

    customer_map = {customer["customerId"]: customer["fullName"] for customer in list_customers()}

    items = [
        PendingFulfillmentView(
            orderId=o["orderId"],
            orderCode=o["orderCode"],
            organizationId=_string_value(o.get("organizationId")),
            customerName=customer_map.get(o["customerId"], "Unknown"),
            status=o["status"],
            shippingDeadline=o.get("deliveryDateExpected"),
        )
        for o in list_orders()
        if o["status"] in PENDING_FULFILLMENT_STATUSES
    ]
    items.sort(key=lambda item: (item.shippingDeadline is None, item.shippingDeadline or "", item.orderCode))
    return PendingFulfillmentListResponse(items=items)


def get_farm_view() -> FarmView:
    return FarmView(
        plots=[PlotSummary(**plot) for plot in farm_svc.list_plots()],
        cropCycles=[CropCycleSummary(**cycle) for cycle in farm_svc.list_crop_cycles(None, None)],
    )


def get_farm_summary_board() -> FarmSummaryBoardResponse:
    if postgres_sync.is_enabled():
        items = [FarmSummaryBoardItem(**row) for row in view_store.fetch_farm_summary_board()]
        return FarmSummaryBoardResponse(items=items)

    crop_cycles_by_plot: dict[str, list[dict[str, object]]] = {}
    for cycle in list_crop_cycles():
        if cycle.get("status") not in FARM_BOARD_ACTIVE_CYCLE_STATUSES:
            continue
        crop_cycles_by_plot.setdefault(str(cycle["plotId"]), []).append(cycle)

    items: list[FarmSummaryBoardItem] = []
    for plot in sorted(list_plots(), key=lambda item: item["plotCode"]):
        plot_cycles = sorted(
            crop_cycles_by_plot.get(plot["plotId"], []),
            key=lambda cycle: (
                cycle.get("expectedHarvestFrom") is None,
                str(cycle.get("expectedHarvestFrom") or ""),
                str(cycle.get("cropCycleId") or ""),
            ),
        )
        if not plot_cycles:
            items.append(
                FarmSummaryBoardItem(
                    plotId=plot["plotId"],
                    plotCode=plot["plotCode"],
                    plotOrganizationId=_string_value(plot.get("organizationId")),
                    plotName=plot["name"],
                    locationText=_string_value(plot.get("locationText")),
                    areaValue=plot["areaValue"],
                    areaUnit=plot["areaUnit"],
                    plotStatus=_string_value(plot.get("status")) or "active",
                )
            )
            continue

        for cycle in plot_cycles:
            items.append(
                FarmSummaryBoardItem(
                    plotId=plot["plotId"],
                    plotCode=plot["plotCode"],
                    plotOrganizationId=_string_value(plot.get("organizationId")),
                    plotName=plot["name"],
                    locationText=_string_value(plot.get("locationText")),
                    areaValue=plot["areaValue"],
                    areaUnit=plot["areaUnit"],
                    plotStatus=_string_value(plot.get("status")) or "active",
                    cropCycleId=_string_value(cycle.get("cropCycleId")),
                    cropCycleOrganizationId=_string_value(cycle.get("organizationId")),
                    cropName=_string_value(cycle.get("cropName")),
                    growthStage=_normalize_growth_stage(cycle.get("growthStage")),
                    cropCycleStatus=_crop_cycle_status(cycle.get("status")),
                    expectedHarvestFrom=_string_value(cycle.get("expectedHarvestFrom")),
                    expectedHarvestTo=_string_value(cycle.get("expectedHarvestTo")),
                    estimatedYieldQty=_float_value(cycle.get("estimatedYieldQty")),
                )
            )

    items.sort(
        key=lambda item: (
            item.expectedHarvestFrom is None,
            item.expectedHarvestFrom or "",
            item.plotCode,
            item.cropCycleId or "",
        )
    )
    return FarmSummaryBoardResponse(items=items)


def get_project_contribution_summary(project_scope_id: str | None = None) -> ProjectContributionSummaryResponse:
    _validate_optional_project_scope_id(project_scope_id)
    if postgres_sync.is_enabled():
        items = [ProjectContributionSummaryItem(**row) for row in view_store.fetch_project_contribution_summary(project_scope_id)]
        return ProjectContributionSummaryResponse(items=items)

    scope_records = memory_store.list_project_scopes()
    contribution_records = memory_store.list_project_contributions(project_scope_id)
    scope_map = {record["projectScopeId"]: record for record in scope_records}
    summary_by_scope: dict[str, dict[str, object]] = {}

    for contribution in contribution_records:
        scope_id = contribution["projectScopeId"]
        scope = scope_map.get(scope_id)
        if scope is None:
            continue
        summary = summary_by_scope.setdefault(
            scope_id,
            {
                "projectScopeId": scope_id,
                "projectScopeCode": scope["projectScopeCode"],
                "projectScopeName": scope["name"],
                "proposedCount": 0,
                "confirmedCount": 0,
                "rejectedCount": 0,
                "confirmedQuantity": 0.0,
                "confirmedEstimatedValue": None,
                "currency": None,
            },
        )
        status = contribution["status"]
        if status == ProjectContributionStatus.proposed.value:
            summary["proposedCount"] = int(summary["proposedCount"]) + 1
        elif status == ProjectContributionStatus.confirmed.value:
            summary["confirmedCount"] = int(summary["confirmedCount"]) + 1
            summary["confirmedQuantity"] = float(summary["confirmedQuantity"]) + float(contribution["quantity"])
            if contribution.get("estimatedValue") is not None:
                current_estimated_value = summary.get("confirmedEstimatedValue")
                summary["confirmedEstimatedValue"] = (
                    (float(current_estimated_value) if current_estimated_value is not None else 0.0)
                    + float(contribution["estimatedValue"])
                )
                contribution_currency = contribution.get("currency")
                current_currency = summary.get("currency")
                if current_currency is None:
                    summary["currency"] = contribution_currency
                elif contribution_currency is not None and current_currency != contribution_currency:
                    summary["currency"] = None
        elif status == ProjectContributionStatus.rejected.value:
            summary["rejectedCount"] = int(summary["rejectedCount"]) + 1

    items = [ProjectContributionSummaryItem(**item) for item in sorted(summary_by_scope.values(), key=lambda item: str(item["projectScopeCode"]))]
    return ProjectContributionSummaryResponse(items=items)


def get_project_impacted_actors_summary(
    project_scope_id: str | None = None,
) -> ProjectImpactedActorSummaryResponse:
    _validate_optional_project_scope_id(project_scope_id)
    if postgres_sync.is_enabled():
        items = [
            ProjectImpactedActorSummaryItem(**row)
            for row in view_store.fetch_project_impacted_actors_summary(project_scope_id)
        ]
        return ProjectImpactedActorSummaryResponse(items=items)

    scope_records = memory_store.list_project_scopes()
    scope_map = {record["projectScopeId"]: record for record in scope_records}
    contribution_records = memory_store.list_project_contributions(project_scope_id)
    summary_by_actor: dict[tuple[str, str, str, str], dict[str, object]] = {}

    for contribution in contribution_records:
        scope_id = contribution["projectScopeId"]
        scope = scope_map.get(scope_id)
        if scope is None:
            continue
        actor_id = contribution["actorId"]
        actor_type = contribution["actorType"]
        role = contribution["role"]
        key = (scope_id, actor_id, actor_type, role)
        summary = summary_by_actor.setdefault(
            key,
            {
                "projectScopeId": scope_id,
                "projectScopeCode": scope["projectScopeCode"],
                "projectScopeName": scope["name"],
                "actorId": actor_id,
                "actorType": actor_type,
                "role": role,
                "contributionCount": 0,
                "confirmedContributionCount": 0,
                "proposedContributionCount": 0,
                "rejectedContributionCount": 0,
                "confirmedQuantity": 0.0,
                "confirmedEstimatedValue": None,
                "currency": None,
            },
        )
        summary["contributionCount"] = int(summary["contributionCount"]) + 1
        status = contribution["status"]
        if status == ProjectContributionStatus.confirmed.value:
            summary["confirmedContributionCount"] = int(summary["confirmedContributionCount"]) + 1
            summary["confirmedQuantity"] = float(summary["confirmedQuantity"]) + float(contribution["quantity"])
            if contribution.get("estimatedValue") is not None:
                current_estimated_value = summary.get("confirmedEstimatedValue")
                summary["confirmedEstimatedValue"] = (
                    (float(current_estimated_value) if current_estimated_value is not None else 0.0)
                    + float(contribution["estimatedValue"])
                )
                contribution_currency = contribution.get("currency")
                current_currency = summary.get("currency")
                if current_currency is None:
                    summary["currency"] = contribution_currency
                elif contribution_currency is not None and current_currency != contribution_currency:
                    summary["currency"] = None
        elif status == ProjectContributionStatus.proposed.value:
            summary["proposedContributionCount"] = int(summary["proposedContributionCount"]) + 1
        elif status == ProjectContributionStatus.rejected.value:
            summary["rejectedContributionCount"] = int(summary["rejectedContributionCount"]) + 1

    items = [
        ProjectImpactedActorSummaryItem(**item)
        for item in sorted(
            summary_by_actor.values(),
            key=lambda item: (
                str(item["projectScopeCode"]),
                str(item["actorId"]),
                str(item["role"]),
            ),
        )
    ]
    return ProjectImpactedActorSummaryResponse(items=items)


def get_project_contribution_ledger(
    project_scope_id: str | None = None,
) -> ProjectContributionLedgerResponse:
    _validate_optional_project_scope_id(project_scope_id)
    if postgres_sync.is_enabled():
        items = [ProjectContributionLedgerItem(**row) for row in view_store.fetch_project_contribution_ledger(project_scope_id)]
        return ProjectContributionLedgerResponse(items=items)

    scope_records = memory_store.list_project_scopes()
    scope_map = {record["projectScopeId"]: record for record in scope_records}
    assignment_records = memory_store.list_project_assignments(project_scope_id)
    assignment_map = {record["projectAssignmentId"]: record for record in assignment_records}
    contribution_records = memory_store.list_project_contributions(project_scope_id)

    items: list[ProjectContributionLedgerItem] = []
    for contribution in sorted(
        contribution_records,
        key=lambda item: (
            str(item.get("createdAt") or ""),
            str(item.get("projectContributionEventId") or ""),
        ),
    ):
        scope = scope_map.get(contribution["projectScopeId"])
        assignment = assignment_map.get(contribution["projectAssignmentId"])
        if scope is None or assignment is None:
            continue
        items.append(
            ProjectContributionLedgerItem(
                projectScopeId=contribution["projectScopeId"],
                projectScopeCode=scope["projectScopeCode"],
                projectScopeName=scope["name"],
                projectContributionEventId=contribution["projectContributionEventId"],
                projectAssignmentId=contribution["projectAssignmentId"],
                assignmentTargetType=assignment["targetType"],
                assignmentTargetId=assignment["targetId"],
                actorId=contribution["actorId"],
                actorType=contribution["actorType"],
                subjectType=contribution["subjectType"],
                subjectId=contribution["subjectId"],
                contributionType=contribution["contributionType"],
                role=contribution["role"],
                verificationStatus=contribution["verificationStatus"],
                verificationSource=contribution["verificationSource"],
                quantity=float(contribution["quantity"]),
                unit=contribution["unit"],
                estimatedValue=(
                    float(contribution["estimatedValue"])
                    if contribution.get("estimatedValue") is not None else None
                ),
                currency=contribution.get("currency"),
                status=str(contribution["status"]),
                createdAt=contribution.get("createdAt"),
                confirmedAt=contribution.get("confirmedAt"),
                confirmedBy=contribution.get("confirmedBy"),
            )
        )
    return ProjectContributionLedgerResponse(items=items)


def get_project_pnl_summary(project_scope_id: str | None = None) -> ProjectPnlSummaryResponse:
    _validate_optional_project_scope_id(project_scope_id)
    if postgres_sync.is_enabled():
        items = [ProjectPnlSummaryItem(**row) for row in view_store.fetch_project_pnl_summary(project_scope_id)]
        return ProjectPnlSummaryResponse(items=items)

    scope_records = memory_store.list_project_scopes()
    scope_map = {record["projectScopeId"]: record for record in scope_records}
    cost_records = memory_store.list_project_cost_records(project_scope_id)
    revenue_records = memory_store.list_project_revenue_records(project_scope_id)
    summary_by_scope: dict[str, dict[str, object]] = {}

    def _get_or_create_summary(scope_id: str) -> dict[str, object] | None:
        scope = scope_map.get(scope_id)
        if scope is None:
            return None
        return summary_by_scope.setdefault(
            scope_id,
            {
                "projectScopeId": scope_id,
                "projectScopeCode": scope["projectScopeCode"],
                "projectScopeName": scope["name"],
                "costRecordCount": 0,
                "revenueRecordCount": 0,
                "recognizedCostAmount": 0.0,
                "recognizedRevenueNetAmount": 0.0,
                "marginAmount": 0.0,
                "currency": None,
            },
        )

    def _merge_currency(summary: dict[str, object], currency: str | None) -> None:
        if currency is None:
            return
        existing = summary.get("currency")
        if existing is None:
            summary["currency"] = currency
            return
        if existing != currency:
            summary["currency"] = None

    for cost_record in cost_records:
        summary = _get_or_create_summary(cost_record["projectScopeId"])
        if summary is None:
            continue
        summary["costRecordCount"] = int(summary["costRecordCount"]) + 1
        summary["recognizedCostAmount"] = float(summary["recognizedCostAmount"]) + float(cost_record["amount"])
        _merge_currency(summary, cost_record.get("currency"))

    for revenue_record in revenue_records:
        summary = _get_or_create_summary(revenue_record["projectScopeId"])
        if summary is None:
            continue
        summary["revenueRecordCount"] = int(summary["revenueRecordCount"]) + 1
        summary["recognizedRevenueNetAmount"] = float(summary["recognizedRevenueNetAmount"]) + float(revenue_record["netAmount"])
        _merge_currency(summary, revenue_record.get("currency"))

    items: list[ProjectPnlSummaryItem] = []
    for item in sorted(summary_by_scope.values(), key=lambda item: str(item["projectScopeCode"])):
        item["marginAmount"] = float(item["recognizedRevenueNetAmount"]) - float(item["recognizedCostAmount"])
        items.append(ProjectPnlSummaryItem(**item))
    return ProjectPnlSummaryResponse(items=items)


def get_project_order_allocation_summary(
    project_scope_id: str | None = None,
) -> ProjectOrderAllocationSummaryResponse:
    _validate_optional_project_scope_id(project_scope_id)
    if postgres_sync.is_enabled():
        items = [
            ProjectOrderAllocationSummaryItem(**row)
            for row in view_store.fetch_project_order_allocation_summary(project_scope_id)
        ]
        return ProjectOrderAllocationSummaryResponse(items=items)

    scope_records = memory_store.list_project_scopes()
    scope_map = {record["projectScopeId"]: record for record in scope_records}
    assignment_records = memory_store.list_project_assignments(project_scope_id)
    order_assignments_by_scope: dict[str, set[str]] = {}

    for assignment in assignment_records:
        if assignment.get("targetType") != "order" or assignment.get("endedAt") is not None:
            continue
        scope_id = assignment["projectScopeId"]
        if scope_id not in scope_map:
            continue
        order_assignments_by_scope.setdefault(scope_id, set()).add(assignment["targetId"])

    items: list[ProjectOrderAllocationSummaryItem] = []
    for scope_id in sorted(order_assignments_by_scope, key=lambda item: str(scope_map[item]["projectScopeCode"])):
        scope = scope_map[scope_id]
        assigned_order_ids = order_assignments_by_scope[scope_id]
        allocated_order_ids: set[str] = set()
        allocation_count = 0
        active_allocation_count = 0
        released_allocation_count = 0
        allocated_qty = 0.0
        active_allocated_qty = 0.0
        released_allocated_qty = 0.0
        units: set[str] = set()

        for order_id in assigned_order_ids:
            order = memory_store.get_order(order_id)
            line_unit_by_id = {
                str(line.get("orderLineId")): str(line.get("unit"))
                for line in (order or {}).get("lines", [])
                if line.get("orderLineId") is not None and line.get("unit") is not None
            }
            allocations = memory_store.get_allocations(order_id)
            if allocations:
                allocated_order_ids.add(order_id)
            for allocation in allocations:
                allocation_count += 1
                quantity = float(allocation["allocatedQty"])
                allocated_qty += quantity
                unit = line_unit_by_id.get(str(allocation.get("orderLineId")))
                if unit is not None:
                    units.add(unit)
                status = allocation.get("status")
                if status == "active":
                    active_allocation_count += 1
                    active_allocated_qty += quantity
                elif status == "released":
                    released_allocation_count += 1
                    released_allocated_qty += quantity

        items.append(
            ProjectOrderAllocationSummaryItem(
                projectScopeId=scope_id,
                projectScopeCode=scope["projectScopeCode"],
                projectScopeName=scope["name"],
                assignedOrderCount=len(assigned_order_ids),
                allocatedOrderCount=len(allocated_order_ids),
                allocationCount=allocation_count,
                activeAllocationCount=active_allocation_count,
                releasedAllocationCount=released_allocation_count,
                allocatedQty=allocated_qty,
                activeAllocatedQty=active_allocated_qty,
                releasedAllocatedQty=released_allocated_qty,
                unit=next(iter(units)) if len(units) == 1 else None,
            )
        )

    return ProjectOrderAllocationSummaryResponse(items=items)

def get_shared_resource_allocation_summary(
    organization_id: str | None = None,
    resource_type: str | None = None,
) -> SharedResourceAllocationSummaryResponse:
    if postgres_sync.is_enabled():
        items = [
            SharedResourceAllocationSummaryItem(**row)
            for row in view_store.fetch_shared_resource_allocation_summary(organization_id, resource_type)
        ]
        return SharedResourceAllocationSummaryResponse(items=items)

    allocations_by_resource: dict[str, list[dict[str, object]]] = {}
    for resource in memory_store.list_shared_resources():
        allocations_by_resource[resource["sharedResourceId"]] = memory_store.list_shared_resource_allocations(
            resource["sharedResourceId"]
        )

    items: list[SharedResourceAllocationSummaryItem] = []
    for resource in sorted(memory_store.list_shared_resources(), key=lambda item: str(item["resourceCode"])):
        if organization_id is not None and str(resource.get("organizationId")) != organization_id:
            continue
        if resource_type is not None and str(resource.get("resourceType")) != resource_type:
            continue

        allocations = allocations_by_resource.get(resource["sharedResourceId"], [])
        allocation_count = len(allocations)
        active_allocations = [allocation for allocation in allocations if allocation.get("status") == "active"]
        allocated_capacity_total = sum(float(allocation.get("allocatedCapacity") or 0.0) for allocation in allocations)
        released_capacity_total = sum(float(allocation.get("releasedCapacity") or 0.0) for allocation in allocations)
        active_capacity_total = sum(
            float(allocation.get("allocatedCapacity") or 0.0) - float(allocation.get("releasedCapacity") or 0.0)
            for allocation in active_allocations
        )

        capacity_value = _float_value(resource.get("capacityValue"))
        utilization_pct = None
        if capacity_value is not None and capacity_value > 0:
            utilization_pct = round((active_capacity_total / capacity_value) * 100, 2)

        items.append(
            SharedResourceAllocationSummaryItem(
                sharedResourceId=resource["sharedResourceId"],
                organizationId=resource["organizationId"],
                resourceCode=resource["resourceCode"],
                name=resource["name"],
                resourceType=str(resource["resourceType"]),
                status=str(resource["status"]),
                capacityValue=capacity_value,
                capacityUnit=_string_value(resource.get("capacityUnit")),
                allocationCount=allocation_count,
                activeAllocationCount=len(active_allocations),
                allocatedCapacityTotal=allocated_capacity_total,
                releasedCapacityTotal=released_capacity_total,
                activeCapacityTotal=active_capacity_total,
                utilizationPct=utilization_pct,
            )
        )

    return SharedResourceAllocationSummaryResponse(items=items)


def get_customer_360_for_actor(customer_id: str, meta: Meta | None) -> Customer360View:
    authorize_read_surface(
        meta=meta,
        action_name="view.customer_360",
        target_type="CustomerView",
        target_id=customer_id,
        allowed_roles={"founder", "super_admin", "admin", "sales", "cskh"},
        reason_code="forbidden_customer_360_view",
        detail="Actor is not allowed to read Customer 360 views.",
    )
    return get_customer_360(customer_id)


def get_available_lots_board_for_actor(product_sku_id: str | None, meta: Meta | None) -> AvailableLotListResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.available_lots",
        target_type="LotBoard",
        target_id=product_sku_id or "all",
        allowed_roles={"founder", "super_admin", "admin", "ops", "farm_manager", "qc_reviewer", "viewer"},
        reason_code="forbidden_available_lots_view",
        detail="Actor is not allowed to read available lots boards.",
    )
    return get_available_lots_board(product_sku_id)


def get_pending_fulfillment_for_actor(meta: Meta | None) -> PendingFulfillmentListResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.pending_fulfillment",
        target_type="PendingFulfillmentBoard",
        target_id="default",
        allowed_roles={"founder", "super_admin", "admin", "sales", "cskh", "ops", "accountant", "viewer"},
        reason_code="forbidden_pending_fulfillment_view",
        detail="Actor is not allowed to read pending fulfillment boards.",
    )
    return get_pending_fulfillment()


def get_farm_view_for_actor(meta: Meta | None) -> FarmView:
    authorize_read_surface(
        meta=meta,
        action_name="view.farm",
        target_type="FarmView",
        target_id="default",
        allowed_roles={"founder", "super_admin", "admin", "ops", "farm_manager", "viewer"},
        reason_code="forbidden_farm_view",
        detail="Actor is not allowed to read farm views.",
    )
    return get_farm_view()


def get_farm_summary_board_for_actor(meta: Meta | None) -> FarmSummaryBoardResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.farm_summary_board",
        target_type="FarmSummaryBoard",
        target_id="default",
        allowed_roles={"founder", "super_admin", "admin", "ops", "farm_manager", "viewer"},
        reason_code="forbidden_farm_summary_board_view",
        detail="Actor is not allowed to read farm summary boards.",
    )
    return get_farm_summary_board()


def get_project_contribution_summary_for_actor(
    project_scope_id: str | None,
    meta: Meta | None,
) -> ProjectContributionSummaryResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.project_contribution_summary",
        target_type="ProjectContributionSummaryBoard",
        target_id=project_scope_id or "all",
        allowed_roles=PROJECT_CONTRIBUTION_BOARD_READ_ROLES,
        reason_code="forbidden_project_contribution_summary_view",
        detail="Actor is not allowed to read project contribution summary boards.",
    )
    return get_project_contribution_summary(project_scope_id)


def get_project_pnl_summary_for_actor(
    project_scope_id: str | None,
    meta: Meta | None,
) -> ProjectPnlSummaryResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.project_pnl_summary",
        target_type="ProjectPnlSummaryBoard",
        target_id=project_scope_id or "all",
        allowed_roles=PROJECT_PNL_READ_ROLES,
        reason_code="forbidden_project_pnl_summary_view",
        detail="Actor is not allowed to read project P&L summary boards.",
    )
    return get_project_pnl_summary(project_scope_id)


def get_project_order_allocation_summary_for_actor(
    project_scope_id: str | None,
    meta: Meta | None,
) -> ProjectOrderAllocationSummaryResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.project_order_allocation_summary",
        target_type="ProjectOrderAllocationSummaryBoard",
        target_id=project_scope_id or "all",
        allowed_roles=PROJECT_ORDER_ALLOCATION_READ_ROLES,
        reason_code="forbidden_project_order_allocation_summary_view",
        detail="Actor is not allowed to read project order allocation summary boards.",
    )
    return get_project_order_allocation_summary(project_scope_id)


def get_project_contribution_ledger_for_actor(
    project_scope_id: str | None,
    meta: Meta | None,
) -> ProjectContributionLedgerResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.project_contribution_ledger",
        target_type="ProjectContributionLedgerBoard",
        target_id=project_scope_id or "all",
        allowed_roles=PROJECT_CONTRIBUTION_BOARD_READ_ROLES,
        reason_code="forbidden_project_contribution_ledger_view",
        detail="Actor is not allowed to read project contribution ledger boards.",
    )
    return get_project_contribution_ledger(project_scope_id)


def get_project_impacted_actors_summary_for_actor(
    project_scope_id: str | None,
    meta: Meta | None,
) -> ProjectImpactedActorSummaryResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.project_impacted_actors_summary",
        target_type="ProjectImpactedActorsSummaryBoard",
        target_id=project_scope_id or "all",
        allowed_roles=PROJECT_CONTRIBUTION_BOARD_READ_ROLES,
        reason_code="forbidden_project_impacted_actors_summary_view",
        detail="Actor is not allowed to read project impacted actors summary boards.",
    )
    return get_project_impacted_actors_summary(project_scope_id)

def get_shared_resource_allocation_summary_for_actor(
    organization_id: str | None,
    resource_type: str | None,
    meta: Meta | None,
) -> SharedResourceAllocationSummaryResponse:
    authorize_read_surface(
        meta=meta,
        action_name="view.shared_resource_allocation_summary",
        target_type="SharedResourceAllocationSummaryBoard",
        target_id=organization_id or resource_type or "all",
        allowed_roles=SHARED_RESOURCE_ALLOCATION_READ_ROLES,
        reason_code="forbidden_shared_resource_allocation_summary_view",
        detail="Actor is not allowed to read shared resource allocation summary boards.",
    )
    return get_shared_resource_allocation_summary(organization_id, resource_type)