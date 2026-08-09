from __future__ import annotations

from datetime import UTC, datetime

from loopledger.models import RawMessage


def raw_message(**overrides: object) -> RawMessage:
    values: dict[str, object] = {
        "message_id": "<message@example.com>",
        "source_name": "fixture.eml",
        "source_index": 0,
        "date": datetime(2026, 1, 1, tzinfo=UTC),
        "sender": "alex@example.com",
        "recipients": ("morgan@example.net",),
        "subject": "A request",
        "normalized_subject": "a request",
        "body": "Could you review this by Friday?",
    }
    values.update(overrides)
    return RawMessage(**values)  # type: ignore[arg-type]
