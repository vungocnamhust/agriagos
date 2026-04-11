# pyright: reportMissingImports=false
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from app.store import views as view_store


class FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self) -> "FakeResult":
        return self

    def first(self):
        return self._row


class FakeSession:
    def __init__(self, row):
        self._row = row
        self.statements: list[str] = []

    def execute(self, statement, _params=None):  # noqa: ANN001
        self.statements.append(str(statement))
        return FakeResult(self._row)


@contextmanager
def fake_session_scope(row) -> Iterator[FakeSession]:  # noqa: ANN001
    yield FakeSession(row)


def test_fetch_customer_360_reads_materialized_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {
        "customer_id": "customer-1",
        "customer": {
            "customerId": "customer-1",
            "customerCode": "KH-001",
            "fullName": "Alice Nguyen",
            "phone": "0900000001",
            "status": "active",
            "tags": ["vip"],
        },
        "active_preorders": [{"preorderId": "preorder-1", "status": "active"}],
        "recent_orders": [{"orderId": "order-1", "lines": []}],
        "preferences": [{"preferenceType": "pack_size", "preferenceValue": "5kg", "confidenceLevel": 0.9}],
    }

    monkeypatch.setattr(view_store, "is_enabled", lambda: True)
    monkeypatch.setattr(view_store, "SessionLocal", lambda: fake_session_scope(row))

    result = view_store.fetch_customer_360("customer-1")

    assert result == {
        "customer": row["customer"],
        "activePreorders": row["active_preorders"],
        "recentOrders": row["recent_orders"],
        "preferences": row["preferences"],
    }


def test_fetch_customer_360_tolerates_string_and_invalid_json_projection_values(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {
        "customer_id": "customer-1",
        "customer": '{"customerId": "customer-1"}',
        "active_preorders": "[]",
        "recent_orders": "not-json",
        "preferences": None,
    }

    monkeypatch.setattr(view_store, "is_enabled", lambda: True)
    monkeypatch.setattr(view_store, "SessionLocal", lambda: fake_session_scope(row))

    result = view_store.fetch_customer_360("customer-1")

    assert result == {
        "customer": {"customerId": "customer-1"},
        "activePreorders": [],
        "recentOrders": [],
        "preferences": [],
    }