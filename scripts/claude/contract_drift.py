#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_STDIN = 1024 * 1024
ROUTES_DIR = Path("agos_app/app/api/routes")
MODELS_DIR = Path("agos_app/app/models")
DDL_DIR = Path("docs/changelog/v1/ddl")
ARCHITECTURE_DIR = Path("docs/changelog/v1/architecture")
OPENAPI_DIR = Path("docs/changelog/v1/openapi")

ARCHITECTURE_TARGETS = {
    "routes": [
        ARCHITECTURE_DIR / "02-core-workflows.md",
        ARCHITECTURE_DIR / "05-event-catalog.md",
        ARCHITECTURE_DIR / "06-state-transitions.md",
    ],
    "schemas": [
        ARCHITECTURE_DIR / "04-canonical-data-model.md",
        ARCHITECTURE_DIR / "05-event-catalog.md",
        ARCHITECTURE_DIR / "06-state-transitions.md",
    ],
    "migrations": [
        ARCHITECTURE_DIR / "04-canonical-data-model.md",
        ARCHITECTURE_DIR / "10-assumptions-and-migration-path.md",
    ],
}

ROUTE_TO_MODEL = {
    "customers": "customers.py",
    "preorders": "preorders.py",
    "orders": "orders.py",
    "lots": "lots.py",
    "farm": "farm.py",
    "views": "views.py",
    "events": "common.py",
}


@dataclass(frozen=True)
class Surface:
    kind: str
    relative_path: Path
    domain: str | None = None


def read_event() -> tuple[str, bool]:
    truncated = False
    chunks: list[str] = []
    total = 0

    for chunk in sys.stdin:
        if total < MAX_STDIN:
            remaining = MAX_STDIN - total
            accepted = chunk[:remaining]
            chunks.append(accepted)
            total += len(accepted)
            if len(accepted) < len(chunk):
                truncated = True
        else:
            truncated = True

    return "".join(chunks), truncated


def parse_event(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        print(f"[contract-drift] WARNING: failed to parse hook event: {error}", file=sys.stderr)
        return {}


def resolve_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return start.resolve()


def normalize_path(value: str | None, repo_root: Path) -> Path | None:
    if not value:
        return None

    candidate = Path(value)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo_root)
        except ValueError:
            return None

    return Path(str(candidate).replace("\\", "/"))


def classify(relative_path: Path | None) -> Surface | None:
    if relative_path is None:
        return None

    normalized = Path(str(relative_path).replace("\\", "/"))

    try:
        route_tail = normalized.relative_to(ROUTES_DIR)
    except ValueError:
        route_tail = None
    if route_tail and route_tail.suffix == ".py":
        return Surface("route", normalized, route_tail.stem)

    try:
        model_tail = normalized.relative_to(MODELS_DIR)
    except ValueError:
        model_tail = None
    if model_tail and model_tail.suffix == ".py":
        return Surface("schema", normalized, model_tail.stem)

    if normalized.match("alembic/versions/*.py"):
        return Surface("migration", normalized)

    try:
        ddl_tail = normalized.relative_to(DDL_DIR)
    except ValueError:
        ddl_tail = None
    if ddl_tail and ddl_tail.suffix == ".sql":
        return Surface("migration", normalized)

    try:
        architecture_tail = normalized.relative_to(ARCHITECTURE_DIR)
    except ValueError:
        architecture_tail = None
    if architecture_tail and architecture_tail.suffix == ".md":
        return Surface("architecture", normalized)

    try:
        openapi_tail = normalized.relative_to(OPENAPI_DIR)
    except ValueError:
        openapi_tail = None
    if openapi_tail and openapi_tail.suffix in {".yaml", ".yml", ".json"}:
        return Surface("openapi", normalized)

    return None


def list_changed_paths(repo_root: Path) -> set[Path]:
    result = subprocess.run(
        ["git", "status", "--porcelain=1", "-z", "--untracked-files=all"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"[contract-drift] WARNING: git status failed with exit code {result.returncode}; skipping sync check.",
            file=sys.stderr,
        )
        return set()

    changed: set[Path] = set()

    entries = result.stdout.decode("utf-8", errors="replace").split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry or len(entry) < 4:
            continue

        status = entry[:2]
        path_text = entry[3:]

        if status[0] in {"R", "C"}:
            if index >= len(entries):
                continue
            path_text = entries[index]
            index += 1

        if path_text:
            changed.add(Path(path_text))

    return changed


def changed_in_directory(changed_paths: set[Path], directory: Path) -> bool:
    for candidate in changed_paths:
        try:
            candidate.relative_to(directory)
            return True
        except ValueError:
            continue
    return False


def openapi_targets(repo_root: Path) -> list[Path]:
    openapi_root = repo_root / OPENAPI_DIR
    if not openapi_root.exists():
        return [OPENAPI_DIR / "openapi.yaml"]

    artifacts = sorted(
        path.relative_to(repo_root)
        for path in openapi_root.rglob("*")
        if path.is_file() and path.suffix in {".yaml", ".yml", ".json"}
    )
    if artifacts:
        return artifacts
    return [OPENAPI_DIR / "openapi.yaml"]


def route_model_path(domain: str | None) -> Path | None:
    if not domain:
        return None
    filename = ROUTE_TO_MODEL.get(domain)
    if not filename:
        return None
    return MODELS_DIR / filename


def route_path(domain: str | None) -> Path | None:
    if not domain:
        return None
    return ROUTES_DIR / f"{domain}.py"


def code_surfaces_changed(changed_paths: set[Path]) -> bool:
    for candidate in changed_paths:
        surface = classify(candidate)
        if surface and surface.kind in {"route", "schema", "migration"}:
            return True
    return False


def missing_items(surface: Surface, changed_paths: set[Path], repo_root: Path) -> list[str]:
    missing: list[str] = []

    architecture_changed = changed_in_directory(changed_paths, ARCHITECTURE_DIR)
    openapi_changed = changed_in_directory(changed_paths, OPENAPI_DIR)

    if surface.kind == "route":
        model_path = route_model_path(surface.domain)
        if model_path and model_path not in changed_paths:
            missing.append(str(model_path))
        if not openapi_changed:
            missing.extend(str(path) for path in openapi_targets(repo_root))
        if not architecture_changed:
            missing.extend(str(path) for path in ARCHITECTURE_TARGETS["routes"])
        return missing

    if surface.kind == "schema":
        route = route_path(surface.domain)
        if route and route not in changed_paths:
            missing.append(str(route))
        if not openapi_changed:
            missing.extend(str(path) for path in openapi_targets(repo_root))
        if not architecture_changed:
            missing.extend(str(path) for path in ARCHITECTURE_TARGETS["schemas"])
        return missing

    if surface.kind == "migration":
        if not architecture_changed:
            missing.extend(str(path) for path in ARCHITECTURE_TARGETS["migrations"])
        if not changed_in_directory(changed_paths, MODELS_DIR):
            missing.append(str(MODELS_DIR))
        return missing

    if surface.kind == "architecture":
        if not code_surfaces_changed(changed_paths):
            return []
        if not changed_in_directory(changed_paths, ROUTES_DIR):
            missing.append(str(ROUTES_DIR))
        if not changed_in_directory(changed_paths, MODELS_DIR):
            missing.append(str(MODELS_DIR))
        if not changed_in_directory(changed_paths, DDL_DIR):
            missing.append(str(DDL_DIR))
        return missing

    return missing


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def build_warning(surface: Surface, missing: list[str]) -> str:
    if not missing:
        return ""

    titles = {
        "route": "Route changed without synced contract artifacts",
        "schema": "DTO changed without synced contract artifacts",
        "migration": "Migration changed without synced contract artifacts",
        "architecture": "Architecture docs changed without synced code artifacts",
    }
    heading = titles.get(surface.kind, "Contract drift warning")
    lines = [
        f"[contract-drift] WARNING: {heading}",
        f"Touched: {surface.relative_path}",
        "Missing sync items:",
    ]
    lines.extend(f"- {item}" for item in unique(missing))
    return "\n".join(lines)


def main() -> int:
    raw, truncated = read_event()
    if truncated:
        print("[contract-drift] WARNING: hook input was truncated; skipping sync check.", file=sys.stderr)
        return 0

    event = parse_event(raw)
    cwd = Path(str(event.get("cwd") or "."))
    repo_root = resolve_repo_root(cwd)

    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    file_path = tool_input.get("file_path") or tool_input.get("file")
    surface = classify(normalize_path(str(file_path) if file_path else None, repo_root))

    if surface is None or surface.kind not in {"route", "schema", "migration", "architecture"}:
        return 0

    changed_paths = list_changed_paths(repo_root)
    missing = missing_items(surface, changed_paths, repo_root)
    warning = build_warning(surface, missing)
    if warning:
        print(warning, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())