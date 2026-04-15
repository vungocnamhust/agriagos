from __future__ import annotations

from datetime import datetime, timezone

from app.core import codegen


def test_generate_organization_code_uses_org_prefix_and_sequence() -> None:
    generated_code = codegen.generate_organization_code(datetime(2030, 1, 15, tzinfo=timezone.utc))

    assert generated_code == "ORG-203001-0001"


def test_generate_organization_code_increments_sequence_within_month() -> None:
    first_code = codegen.generate_organization_code(datetime(2030, 4, 15, tzinfo=timezone.utc))
    second_code = codegen.generate_organization_code(datetime(2030, 4, 15, tzinfo=timezone.utc))

    assert first_code == "ORG-203004-0001"
    assert second_code == "ORG-203004-0002"


def test_generate_organization_code_resets_sequence_by_month_bucket() -> None:
    february_code = codegen.generate_organization_code(datetime(2030, 2, 15, tzinfo=timezone.utc))
    march_code = codegen.generate_organization_code(datetime(2030, 3, 1, tzinfo=timezone.utc))

    assert february_code == "ORG-203002-0001"
    assert march_code == "ORG-203003-0001"


def test_generate_project_scope_code_uses_prj_prefix_and_sequence() -> None:
    generated_code = codegen.generate_project_scope_code(datetime(2030, 1, 15, tzinfo=timezone.utc))

    assert generated_code == "PRJ-203001-0001"


def test_generate_project_scope_code_increments_sequence_within_month() -> None:
    first_code = codegen.generate_project_scope_code(datetime(2030, 4, 15, tzinfo=timezone.utc))
    second_code = codegen.generate_project_scope_code(datetime(2030, 4, 15, tzinfo=timezone.utc))

    assert first_code == "PRJ-203004-0001"
    assert second_code == "PRJ-203004-0002"