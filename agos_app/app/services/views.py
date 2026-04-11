from fastapi import HTTPException

from app.models.farm import FarmView
from app.models.orders import OrderDetail, OrderLine
from app.models.preorders import PreorderDetail
from app.models.views import (
    AvailableLotListResponse,
    AvailableLotView,
    Customer360View,
    CustomerPreferenceItem,
    PendingFulfillmentListResponse,
    PendingFulfillmentView,
)
from app.services import customers as cust_svc
from app.services import farm as farm_svc
from app.store import postgres_sync
from app.store import memory as store
from app.store import views as view_store


def get_customer_360(customer_id: str) -> Customer360View:
    if postgres_sync.is_enabled():
        data = view_store.fetch_customer_360(customer_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Customer not found.")
        return Customer360View(**data)

    customer = cust_svc.get_customer(customer_id)

    active_preorders = [
        PreorderDetail(**p)
        for p in store._preorders.values()
        if p["customerId"] == customer_id and p["status"] == "active"
    ]

    recent_orders = [
        OrderDetail(
            orderId=o["orderId"],
            orderCode=o["orderCode"],
            customerId=o["customerId"],
            channel=o["channel"],
            status=o["status"],
            paymentStatus=o["paymentStatus"],
            deliveryDateExpected=o.get("deliveryDateExpected"),
            lines=[OrderLine(**ln) for ln in o.get("lines", [])],
        )
        for o in store._orders.values()
        if o["customerId"] == customer_id
    ][-10:]

    preferences = [
        CustomerPreferenceItem(
            preferenceType=p["preferenceType"],
            preferenceValue=p["preferenceValue"],
            confidenceLevel=p["confidenceLevel"],
        )
        for p in store._preferences.get(customer_id, [])
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
            productSkuId=lot["productSkuId"],
            releasedQty=lot["releasedQty"],
            availableQty=lot["availableQty"],
            status=lot["status"],
        )
        for lot in store._lots.values()
        if lot["status"] == "released" and lot["availableQty"] > 0
        and (product_sku_id is None or lot["productSkuId"] == product_sku_id)
    ]
    return AvailableLotListResponse(items=lots)


def get_pending_fulfillment() -> PendingFulfillmentListResponse:
    if postgres_sync.is_enabled():
        items = [PendingFulfillmentView(**row) for row in view_store.fetch_pending_fulfillment_board()]
        return PendingFulfillmentListResponse(items=items)

    pending_statuses = {"confirmed", "allocated", "packed"}
    customer_map = {c["customerId"]: c["fullName"] for c in store._customers.values()}

    items = [
        PendingFulfillmentView(
            orderId=o["orderId"],
            orderCode=o["orderCode"],
            customerName=customer_map.get(o["customerId"], "Unknown"),
            status=o["status"],
            shippingDeadline=o.get("deliveryDateExpected"),
        )
        for o in store._orders.values()
        if o["status"] in pending_statuses
    ]
    return PendingFulfillmentListResponse(items=items)


def get_farm_view() -> FarmView:
    return FarmView(
        plots=farm_svc.list_plots(),
        cropCycles=farm_svc.list_crop_cycles(None, None),
    )