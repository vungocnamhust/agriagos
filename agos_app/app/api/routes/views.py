from fastapi import APIRouter

from app.models.orders import OrderDetail, OrderLine
from app.models.preorders import PreorderDetail
from app.models.views import (
    AvailableLotView,
    Customer360View,
    CustomerPreferenceItem,
    PendingFulfillmentView,
)
from app.services import customers as cust_svc
from app.services import farm as farm_svc
from app.store import memory as store

router = APIRouter()


@router.get("/customer-360/{customer_id}", response_model=Customer360View)
def get_customer_360(customer_id: str) -> Customer360View:
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


@router.get("/available-lots")
def get_available_lots_board(skuId: str | None = None) -> dict:
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
        and (skuId is None or lot["productSkuId"] == skuId)
    ]
    return {"items": [lot.model_dump() for lot in lots]}


@router.get("/pending-fulfillment")
def get_pending_fulfillment() -> dict:
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
    return {"items": [i.model_dump() for i in items]}


@router.get("/farm")
def get_farm_view() -> dict:
    return {
        "plots": farm_svc.list_plots(),
        "cropCycles": farm_svc.list_crop_cycles(None, None),
    }
