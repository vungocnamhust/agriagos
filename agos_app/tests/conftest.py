# pyright: reportMissingImports=false, reportShadowedImports=false
from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import gateway
from app.services import customers as customer_service
from app.services import farm as farm_service
from app.services import financial_allocations as financial_allocation_service
from app.services import actor_authority as actor_authority_service
from app.services import organizations as organization_service
from app.services import project_assignments as project_assignment_service
from app.services import project_contributions as project_contribution_service
from app.services import project_cost_records as project_cost_record_service
from app.services import project_revenue_records as project_revenue_record_service
from app.services import project_scopes as project_scope_service
from app.services import shared_resources as shared_resource_service
from app.services import views as views_service
from app.store import _db
from app.store import farm as farm_store
from app.store import memory
from app.store import postgres_sync
from app.store import views as view_store


@pytest.fixture(autouse=True)
def reset_memory_state() -> None:
    memory.reset_state()
    yield
    memory.reset_state()


@pytest.fixture(autouse=True)
def default_to_memory_store(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("postgres_integration"):
        return
    monkeypatch.setattr(_db, "is_enabled", lambda: False)
    monkeypatch.setattr(postgres_sync, "is_enabled", lambda: False)
    monkeypatch.setattr(gateway, "postgres_enabled", lambda: False)
    monkeypatch.setattr(actor_authority_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(customer_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(organization_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(project_assignment_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(project_contribution_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(project_cost_record_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(financial_allocation_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(project_revenue_record_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(project_scope_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(shared_resource_service, "postgres_enabled", lambda: False)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: False)
    monkeypatch.setattr(farm_service.postgres_sync, "is_enabled", lambda: False)
    monkeypatch.setattr(view_store, "is_enabled", lambda: False)
    monkeypatch.setattr(farm_store, "is_enabled", lambda: False)


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://agriagos:agriagos@127.0.0.1:5436/agriagos",
    )


@pytest.fixture(scope="session")
def migrated_postgres_engine(postgres_database_url: str):
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(alembic_config, "head")

    engine = create_engine(postgres_database_url, future=True, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def postgres_db_session(migrated_postgres_engine) -> Session:
    connection = migrated_postgres_engine.connect()
    transaction = connection.begin()
    local_session = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )()

    try:
        yield local_session
    finally:
        local_session.close()
        transaction.rollback()
        connection.close()