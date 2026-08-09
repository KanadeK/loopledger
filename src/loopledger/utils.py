"""Pure normalization and parsing helpers."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from email.utils import getaddresses, parsedate_to_datetime

_REPLY_PREFIX = re.compile(r"^(?:(?:re|fw|fwd|答复|回复|转发)\s*:\s*)+", re.IGNORECASE)
_MESSAGE_ID = re.compile(r"<[^<>\s]+>")
_DURATION = re.compile(r"^(?P<value>\d+)(?P<unit>[smhdw])$", re.IGNORECASE)
_QUOTED_BOUNDARY = (
    re.compile(r"^On .+ wrote:$", re.IGNORECASE),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}$", re.IGNORECASE),
    re.compile(r"^_{5,}$"),
    re.compile(r"^From:\s+.+$", re.IGNORECASE),
)


def normalize_address(value: str) -> str:
    """Return a case-insensitive mailbox address without display-name noise."""

    return value.strip().strip("<>").casefold()


def parse_addresses(*values: str) -> tuple[str, ...]:
    """Parse, normalize, and deduplicate one or more address headers."""

    # HeaderRegistry objects behave like strings individually, but Python's strict
    # getaddresses parser expects a concrete list of plain strings when headers are mixed.
    header_values = [str(value) for value in values if str(value).strip()]
    found = {
        normalize_address(address) for _, address in getaddresses(header_values) if address.strip()
    }
    return tuple(sorted(found))


def canonical_message_id(value: str) -> str:
    """Normalize a Message-ID while preserving its recognizable angle-bracket form."""

    token = value.strip().casefold()
    if not token:
        return ""
    if token.startswith("<") and token.endswith(">"):
        return token
    return f"<{token.strip('<>')}>"


def parse_message_ids(value: str) -> tuple[str, ...]:
    """Extract canonical IDs from References or In-Reply-To."""

    matches = _MESSAGE_ID.findall(value)
    if not matches and value.strip():
        matches = value.split()
    return tuple(dict.fromkeys(canonical_message_id(item) for item in matches if item.strip()))


def normalize_subject(value: str) -> str:
    """Normalize reply prefixes and whitespace for fallback thread grouping."""

    subject = " ".join(value.split())
    previous = None
    while previous != subject:
        previous = subject
        subject = _REPLY_PREFIX.sub("", subject).strip()
    return subject.casefold()


def parse_email_date(value: str) -> datetime:
    """Parse an RFC email date and normalize it to UTC."""

    parsed = parsedate_to_datetime(value)
    if parsed is None:
        raise ValueError(f"unparseable Date header: {value!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_datetime(value: str) -> datetime:
    """Parse an ISO date or datetime and normalize it to UTC."""

    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_duration(value: str) -> timedelta:
    """Parse compact durations such as 12h, 3d, or 2w."""

    match = _DURATION.fullmatch(value.strip())
    if not match:
        raise ValueError("duration must be an integer followed by s, m, h, d, or w")
    amount = int(match.group("value"))
    unit = match.group("unit").casefold()
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return timedelta(seconds=amount * seconds_per_unit[unit])


def strip_quoted_reply(value: str) -> str:
    """Remove common quoted-history blocks before scoring the current message."""

    kept: list[str] = []
    for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if any(pattern.match(stripped) for pattern in _QUOTED_BOUNDARY):
            break
        if stripped.startswith(">"):
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


def compact_snippet(value: str, limit: int = 240) -> str:
    """Collapse whitespace and cap report evidence without cutting surrogate pairs."""

    compact = " ".join(strip_quoted_reply(value).split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: max(0, limit - 1)].rstrip()}…"


def stable_id(prefix: str, *parts: str, length: int = 16) -> str:
    """Create a deterministic, non-secret identifier."""

    payload = "\x1f".join(parts).encode("utf-8", errors="surrogatepass")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:length]}"
