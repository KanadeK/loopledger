"""Typed domain models shared by the parser, engine, and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Direction(StrEnum):
    """A message's direction relative to the configured identities."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    SELF = "self"
    UNKNOWN = "unknown"


class LoopStatus(StrEnum):
    """State of a detected open loop."""

    OPEN = "open"
    OVERDUE = "overdue"
    SNOOZED = "snoozed"


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    """A content fingerprint for one user-supplied source."""

    name: str
    kind: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class RawMessage:
    """The normalized subset of one RFC 5322 message used by LoopLedger."""

    message_id: str
    source_name: str
    source_index: int
    date: datetime
    sender: str
    recipients: tuple[str, ...]
    subject: str
    normalized_subject: str
    body: str
    references: tuple[str, ...] = ()
    in_reply_to: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    auto_submitted: str = ""
    precedence: str = ""
    list_id: str = ""
    content_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Messages and non-fatal evidence gathered while reading sources."""

    messages: tuple[RawMessage, ...]
    fingerprints: tuple[SourceFingerprint, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MailThread:
    """A deterministic group of related messages."""

    thread_id: str
    subject: str
    participants: tuple[str, ...]
    messages: tuple[RawMessage, ...]


@dataclass(frozen=True, slots=True)
class RequestSignal:
    """Explainable evidence that an outbound message expects a response."""

    score: int
    reasons: tuple[str, ...]
    exclusions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LoopItem:
    """One outbound request that is still waiting on an external participant."""

    loop_id: str
    thread_id: str
    message_id: str
    status: LoopStatus
    subject: str
    sent_at: datetime
    due_at: datetime
    age_seconds: int
    recipients: tuple[str, ...]
    participants: tuple[str, ...]
    request_score: int
    reasons: tuple[str, ...]
    snippet: str
    previous_external_reply_at: datetime | None = None
    snoozed_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class ScanMetrics:
    """Counts for decisions made by the engine."""

    total_messages: int = 0
    total_threads: int = 0
    open_count: int = 0
    overdue_count: int = 0
    snoozed_count: int = 0
    closed_by_reply_count: int = 0
    low_signal_count: int = 0
    automated_count: int = 0
    too_recent_count: int = 0
    ignored_by_state_count: int = 0
    unknown_direction_count: int = 0


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Complete deterministic scan result."""

    schema_version: int
    tool_version: str
    generated_at: datetime
    identities: tuple[str, ...]
    min_age_seconds: int
    overdue_after_seconds: int
    request_threshold: int
    include_all_outbound: bool
    sources: tuple[SourceFingerprint, ...]
    warnings: tuple[str, ...]
    metrics: ScanMetrics
    items: tuple[LoopItem, ...] = field(default_factory=tuple)
