#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from collections import deque
from pathlib import Path
from typing import Any


MODE_TO_CONTEXT = {
    "dev": "dev.md",
    "review": "review.md",
    "research": "research.md",
}

TOKEN_LIMIT = 380
STATE_DIR = Path(tempfile.gettempdir()) / "agriagos-session-context"
TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
SESSION_ID_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
STATE_TTL_SECONDS = 7 * 24 * 60 * 60
TRANSCRIPT_LINE_WINDOW = 200

KEYWORDS = {
    "review": (
        "review",
        "code review",
        "findings",
        "audit",
        "critique",
        "regression",
        "pr review",
        "security review",
        "look for bugs",
    ),
    "research": (
        "research",
        "investigate",
        "explore",
        "understand",
        "trace",
        "analyze",
        "analysis",
        "how does",
        "why does",
        "what is",
        "impact",
        "debug",
        "recon",
        "reconnaissance",
    ),
    "dev": (
        "implement",
        "implementation",
        "fix",
        "add",
        "update",
        "change",
        "create",
        "refactor",
        "wire",
        "build",
        "patch",
        "write",
        "scaffold",
    ),
}


def read_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def estimate_tokens(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def trim_to_token_limit(text: str, limit: int = TOKEN_LIMIT) -> str:
    matches = list(TOKEN_PATTERN.finditer(text))
    if len(matches) <= limit:
        return text.strip()

    cutoff = matches[limit - 1].end()
    trimmed = text[:cutoff].rstrip()
    return trimmed.strip()


def normalize_prompt(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def classify_mode(prompt: str) -> str:
    normalized = normalize_prompt(prompt)
    if not normalized:
        return "dev"

    scores = {mode: 0 for mode in MODE_TO_CONTEXT}
    for mode, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized:
                scores[mode] += 1

    if scores["review"] > 0 and scores["review"] >= scores["research"]:
        return "review"
    if scores["research"] > 0 and scores["research"] > scores["dev"]:
        return "research"
    if scores["dev"] > 0:
        return "dev"
    return "dev"


def project_dir() -> Path:
    configured_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if configured_root:
        return Path(configured_root).resolve()
    return Path(__file__).resolve().parents[2]


def contexts_dir() -> Path:
    return project_dir() / ".claude" / "contexts"


def sanitize_session_id(value: str | None) -> str:
    if not value:
        return ""

    sanitized = SESSION_ID_PATTERN.sub("_", value).strip("_")
    return sanitized[:128]


def state_file(session_id: str) -> Path:
    sanitized = sanitize_session_id(session_id)
    if not sanitized:
        raise ValueError("session_id is required")
    return STATE_DIR / f"{sanitized}.json"


def purge_stale_state_files() -> None:
    if not STATE_DIR.exists():
        return

    cutoff = int(__import__("time").time()) - STATE_TTL_SECONDS
    for candidate in STATE_DIR.glob("*.json"):
        try:
            if int(candidate.stat().st_mtime) < cutoff:
                candidate.unlink()
        except OSError:
            continue


def load_state(session_id: str) -> str | None:
    sanitized = sanitize_session_id(session_id)
    if not sanitized:
        return None

    try:
        target = state_file(sanitized)
    except ValueError:
        return None

    if not target.exists():
        return None

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    mode = payload.get("mode")
    if mode in MODE_TO_CONTEXT:
        return mode
    return None


def save_state(session_id: str, mode: str) -> None:
    sanitized = sanitize_session_id(session_id)
    if not sanitized or mode not in MODE_TO_CONTEXT:
        return

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        purge_stale_state_files()
        target = state_file(sanitized)
        temp_target = target.with_suffix(".tmp")
        temp_target.write_text(
            json.dumps({"mode": mode}, ensure_ascii=True),
            encoding="utf-8",
        )
        temp_target.replace(target)
    except OSError:
        return


def extract_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        collected: list[str] = []
        for item in value:
            collected.extend(extract_text(item))
        return collected

    if isinstance(value, dict):
        collected: list[str] = []
        content_type = str(value.get("type", "")).lower()
        if content_type == "text" and isinstance(value.get("text"), str):
            return [value["text"]]
        for nested in value.values():
            collected.extend(extract_text(nested))
        return collected

    return []


def extract_prompt_candidates(payload: Any) -> list[str]:
    candidates: list[str] = []
    if isinstance(payload, dict):
        role = str(payload.get("role") or payload.get("speaker") or payload.get("type") or "").lower()
        if isinstance(payload.get("prompt"), str):
            candidates.append(payload["prompt"])
        if role == "user":
            candidates.extend(extract_text(payload.get("content")))
            if isinstance(payload.get("text"), str):
                candidates.append(payload["text"])
        for value in payload.values():
            candidates.extend(extract_prompt_candidates(value))
    elif isinstance(payload, list):
        for item in payload:
            candidates.extend(extract_prompt_candidates(item))
    return candidates


def transcript_prompt(event: dict[str, Any]) -> str | None:
    transcript_path = event.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None

    target = Path(transcript_path)
    if not target.exists():
        return None

    try:
        with target.open("r", encoding="utf-8") as handle:
            lines = deque(handle, maxlen=TRANSCRIPT_LINE_WINDOW)
    except OSError:
        return None

    prompts: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        prompts.extend(extract_prompt_candidates(payload))

    for prompt in reversed(prompts):
        if normalize_prompt(prompt):
            return prompt
    return None


def load_context(mode: str) -> str:
    context_name = MODE_TO_CONTEXT.get(mode)
    if not context_name:
        return ""

    target = contexts_dir() / context_name
    if not target.exists():
        return ""

    try:
        content = target.read_text(encoding="utf-8")
    except OSError:
        return ""

    trimmed = trim_to_token_limit(content)
    return trimmed


def should_inject_for_user_prompt(event: dict[str, Any]) -> bool:
    session_id = sanitize_session_id(str(event.get("session_id") or ""))
    if load_state(session_id):
        return False
    return isinstance(event.get("prompt"), str)


def determine_mode(event: dict[str, Any]) -> str | None:
    session_id = sanitize_session_id(str(event.get("session_id") or ""))
    existing_mode = load_state(session_id)
    if existing_mode:
        return existing_mode

    prompt = event.get("prompt")
    if isinstance(prompt, str) and normalize_prompt(prompt):
        mode = classify_mode(prompt)
        save_state(session_id, mode)
        return mode

    previous_prompt = transcript_prompt(event)
    if previous_prompt:
        mode = classify_mode(previous_prompt)
        save_state(session_id, mode)
        return mode

    return None


def build_output(event_name: str, additional_context: str) -> str:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": additional_context,
        }
    }
    return json.dumps(payload, ensure_ascii=True)


def main() -> int:
    event = read_event()
    event_name = str(event.get("hook_event_name") or "")
    if event_name not in {"SessionStart", "UserPromptSubmit"}:
        return 0

    if event_name == "UserPromptSubmit" and not should_inject_for_user_prompt(event):
        return 0

    mode = determine_mode(event)
    if not mode:
        return 0

    additional_context = load_context(mode)
    if not additional_context:
        return 0

    if estimate_tokens(additional_context) > TOKEN_LIMIT:
        additional_context = trim_to_token_limit(additional_context)

    sys.stdout.write(build_output(event_name, additional_context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())