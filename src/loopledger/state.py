"""Optional user decisions that suppress or snooze stable loop IDs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from loopledger.utils import parse_datetime


@dataclass(frozen=True, slots=True)
class LoopState:
    ignored: frozenset[str] = frozenset()
    resolved: frozenset[str] = frozenset()
    snoozed_until: dict[str, datetime] = field(default_factory=dict)


def load_state(path: Path | None) -> LoopState:
    """Load a versioned state file with actionable validation errors."""

    if path is None:
        return LoopState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"state file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"state file is not valid JSON: {path}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("state file must be an object with version set to 1")

    def string_set(key: str) -> frozenset[str]:
        value = payload.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"state field {key!r} must be an array of IDs")
        return frozenset(item.strip() for item in value if item.strip())

    snoozed_raw = payload.get("snoozed_until", {})
    if not isinstance(snoozed_raw, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in snoozed_raw.items()
    ):
        raise ValueError("state field 'snoozed_until' must map IDs to ISO dates")
    try:
        snoozed = {key.strip(): parse_datetime(value) for key, value in snoozed_raw.items()}
    except ValueError as exc:
        raise ValueError(f"state contains an invalid snooze date: {exc}") from exc
    return LoopState(
        ignored=string_set("ignored"),
        resolved=string_set("resolved"),
        snoozed_until=snoozed,
    )
