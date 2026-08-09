"""Core open-loop analysis with no I/O or network calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from loopledger import __version__
from loopledger.models import (
    Direction,
    LoopItem,
    LoopStatus,
    ParseResult,
    RawMessage,
    ScanMetrics,
    ScanResult,
)
from loopledger.signals import is_automated, request_signal
from loopledger.state import LoopState
from loopledger.threading import build_threads
from loopledger.utils import compact_snippet, normalize_address, stable_id


@dataclass(frozen=True, slots=True)
class ScanConfig:
    identities: frozenset[str]
    as_of: datetime
    min_age: timedelta = timedelta(days=3)
    overdue_after: timedelta = timedelta(days=7)
    request_threshold: int = 3
    include_all_outbound: bool = False
    state: LoopState = field(default_factory=LoopState)

    def __post_init__(self) -> None:
        normalized = frozenset(normalize_address(item) for item in self.identities if item.strip())
        object.__setattr__(self, "identities", normalized)
        as_of = self.as_of if self.as_of.tzinfo else self.as_of.replace(tzinfo=UTC)
        object.__setattr__(self, "as_of", as_of.astimezone(UTC))
        if not normalized:
            raise ValueError("at least one email identity is required")
        if self.min_age < timedelta(0) or self.overdue_after < timedelta(0):
            raise ValueError("age thresholds cannot be negative")
        if self.overdue_after < self.min_age:
            raise ValueError("overdue-after must be greater than or equal to min-age")
        if self.request_threshold < 0:
            raise ValueError("request threshold cannot be negative")


def infer_identities(messages: tuple[RawMessage, ...]) -> tuple[str, ...]:
    """Infer account aliases only from explicit Sent labels in exported mail."""

    identities = {
        message.sender
        for message in messages
        if any(label.casefold() in {"sent", "sent mail", "\\sent"} for label in message.labels)
    }
    return tuple(sorted(identities))


def direction_of(message: RawMessage, identities: frozenset[str]) -> Direction:
    sender_is_self = message.sender in identities
    external_recipients = set(message.recipients) - identities
    self_is_recipient = bool(set(message.recipients) & identities)
    inbox_label = any(label.casefold() in {"inbox", "\\inbox"} for label in message.labels)
    if sender_is_self and external_recipients:
        return Direction.OUTBOUND
    if sender_is_self:
        return Direction.SELF
    if self_is_recipient or inbox_label:
        return Direction.INBOUND
    return Direction.UNKNOWN


def _state_value(state: LoopState, loop_id: str, message_id: str) -> tuple[str, datetime | None]:
    keys = (loop_id, message_id)
    if any(key in state.ignored or key in state.resolved for key in keys):
        return "ignored", None
    for key in keys:
        if key in state.snoozed_until:
            return "snoozed", state.snoozed_until[key]
    return "active", None


def analyze(parsed: ParseResult, config: ScanConfig) -> ScanResult:
    """Analyze parsed messages and return every decision needed by reporters."""

    threads = build_threads(parsed.messages, config.identities)
    items: list[LoopItem] = []
    counters = {
        "closed": 0,
        "low_signal": 0,
        "automated": 0,
        "too_recent": 0,
        "ignored": 0,
        "unknown": 0,
    }

    for thread in threads:
        automated = [message for message in thread.messages if is_automated(message)]
        counters["automated"] += len(automated)
        meaningful = [message for message in thread.messages if not is_automated(message)]
        if not meaningful:
            continue
        latest = meaningful[-1]
        latest_direction = direction_of(latest, config.identities)
        if latest_direction == Direction.INBOUND:
            counters["closed"] += 1
            continue
        if latest_direction != Direction.OUTBOUND:
            counters["unknown"] += 1
            continue

        signal = request_signal(latest)
        if signal.score < config.request_threshold and not config.include_all_outbound:
            counters["low_signal"] += 1
            continue
        age = config.as_of - latest.date
        if age < config.min_age:
            counters["too_recent"] += 1
            continue
        if age < timedelta(0):
            counters["too_recent"] += 1
            continue

        loop_id = stable_id("loop", thread.thread_id, latest.message_id)
        state_value, snoozed_until = _state_value(config.state, loop_id, latest.message_id)
        if state_value == "ignored":
            counters["ignored"] += 1
            continue

        due_at = latest.date + config.overdue_after
        if state_value == "snoozed" and snoozed_until and snoozed_until > config.as_of:
            status = LoopStatus.SNOOZED
        elif age >= config.overdue_after:
            status = LoopStatus.OVERDUE
        else:
            status = LoopStatus.OPEN
        previous_external_reply = next(
            (
                message.date
                for message in reversed(meaningful[:-1])
                if direction_of(message, config.identities) == Direction.INBOUND
            ),
            None,
        )
        recipients = tuple(sorted(set(latest.recipients) - config.identities))
        reasons = signal.reasons or (
            ("last_message_is_outbound",) if config.include_all_outbound else ()
        )
        items.append(
            LoopItem(
                loop_id=loop_id,
                thread_id=thread.thread_id,
                message_id=latest.message_id,
                status=status,
                subject=thread.subject,
                sent_at=latest.date,
                due_at=due_at,
                age_seconds=int(age.total_seconds()),
                recipients=recipients,
                participants=thread.participants,
                request_score=signal.score,
                reasons=tuple(reasons),
                snippet=compact_snippet(latest.body or latest.subject),
                previous_external_reply_at=previous_external_reply,
                snoozed_until=snoozed_until,
            )
        )

    status_order = {LoopStatus.OVERDUE: 0, LoopStatus.OPEN: 1, LoopStatus.SNOOZED: 2}
    ordered = tuple(
        sorted(items, key=lambda item: (status_order[item.status], item.due_at, item.loop_id))
    )
    metrics = ScanMetrics(
        total_messages=len(parsed.messages),
        total_threads=len(threads),
        open_count=sum(item.status == LoopStatus.OPEN for item in ordered),
        overdue_count=sum(item.status == LoopStatus.OVERDUE for item in ordered),
        snoozed_count=sum(item.status == LoopStatus.SNOOZED for item in ordered),
        closed_by_reply_count=counters["closed"],
        low_signal_count=counters["low_signal"],
        automated_count=counters["automated"],
        too_recent_count=counters["too_recent"],
        ignored_by_state_count=counters["ignored"],
        unknown_direction_count=counters["unknown"],
    )
    return ScanResult(
        schema_version=1,
        tool_version=__version__,
        generated_at=config.as_of,
        identities=tuple(sorted(config.identities)),
        min_age_seconds=int(config.min_age.total_seconds()),
        overdue_after_seconds=int(config.overdue_after.total_seconds()),
        request_threshold=config.request_threshold,
        include_all_outbound=config.include_all_outbound,
        sources=parsed.fingerprints,
        warnings=parsed.warnings,
        metrics=metrics,
        items=ordered,
    )
