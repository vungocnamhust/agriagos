# pyright: reportAttributeAccessIssue=false, reportMissingImports=false
from __future__ import annotations

import importlib
from logging.config import fileConfig
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import engine_from_config, pool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

settings = importlib.import_module("app.core.config").settings


alembic_context: Any = importlib.import_module("alembic.context")
config = alembic_context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def run_migrations_offline() -> None:
    alembic_context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with alembic_context.begin_transaction():
        alembic_context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        alembic_context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with alembic_context.begin_transaction():
            alembic_context.run_migrations()


if alembic_context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()