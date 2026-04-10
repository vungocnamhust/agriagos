#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


TERMINAL_TOOLS = {
    "run_in_terminal",
}

MAX_STDIN = 1024 * 1024
ENV_SEGMENT_PATTERN = re.compile(r"(^|[\\/\s'\"=])\.env(?:\.[^\\/\s'\"]+)?($|[\\/\s'\"])" )
SHELL_READ_COMMAND_PATTERN = re.compile(
    r"\b(cat|head|tail|less|more|sed|awk|grep|rg|find|fd|python|python3|node|perl|ruby|php|xxd|strings|base64)\b"
)
SHELL_INDIRECTION_PATTERN = re.compile(r"(\$\(|`|\$[A-Za-z_][A-Za-z0-9_]*|\*|\?)")


def read_event() -> dict[str, Any]:
    raw = sys.stdin.read(MAX_STDIN)
    if not raw.strip():
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def is_env_path(value: str) -> bool:
    normalized = value.strip().strip("\"'")
    if not normalized:
        return False

    candidate = Path(normalized).name
    if candidate.startswith(".env"):
        return True

    return bool(ENV_SEGMENT_PATTERN.search(normalized))


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        collected: list[str] = []
        for item in value:
            collected.extend(iter_strings(item))
        return collected

    if isinstance(value, dict):
        collected: list[str] = []
        for nested in value.values():
            collected.extend(iter_strings(nested))
        return collected

    return []


def matches_env_reference(tool_name: str, tool_input: dict[str, Any]) -> bool:
    for value in iter_strings(tool_input):
        if is_env_path(value):
            return True

    if tool_name in TERMINAL_TOOLS:
        command = str(tool_input.get("command") or "")
        if SHELL_READ_COMMAND_PATTERN.search(command) and SHELL_INDIRECTION_PATTERN.search(command):
            return True
        return False

    return False


def build_deny_output() -> str:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Access to .env files is blocked for agent tools.",
        },
        "systemMessage": "Reading .env files is blocked by workspace policy.",
    }
    return json.dumps(payload, ensure_ascii=True)


def main() -> int:
    event = read_event()
    if str(event.get("hook_event_name") or "") != "PreToolUse":
        return 0

    tool_name = str(event.get("tool_name") or "")
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}

    if not matches_env_reference(tool_name, tool_input):
        return 0

    sys.stdout.write(build_deny_output())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())