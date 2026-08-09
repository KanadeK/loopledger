"""Read MBOX, Maildir, and EML sources without network access."""

from __future__ import annotations

import hashlib
import mailbox
from collections.abc import Iterable
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path

from loopledger.models import ParseResult, RawMessage, SourceFingerprint
from loopledger.utils import (
    canonical_message_id,
    normalize_subject,
    parse_addresses,
    parse_email_date,
    parse_message_ids,
    stable_id,
    strip_quoted_reply,
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif tag in {"br", "p", "div", "li", "tr"} and not self._ignored_depth:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in {"p", "div", "li", "tr"} and not self._ignored_depth:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        try:
            return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except LookupError:
            return payload.decode("utf-8", errors="replace")
    raw = part.get_payload()
    return raw if isinstance(raw, str) else ""


def _message_body(message: EmailMessage) -> tuple[str, tuple[str, ...]]:
    plain: list[str] = []
    html: list[str] = []
    content_types: set[str] = set()
    parts: Iterable[Message] = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        content_type = part.get_content_type().casefold()
        content_types.add(content_type)
        disposition = part.get_content_disposition()
        if part.is_multipart() or disposition == "attachment":
            continue
        if content_type == "text/plain":
            plain.append(_decode_part(part))
        elif content_type == "text/html":
            html.append(_decode_part(part))
    if plain:
        return strip_quoted_reply("\n".join(plain)), tuple(sorted(content_types))
    if html:
        parser = _TextExtractor()
        parser.feed("\n".join(html))
        return strip_quoted_reply(parser.text()), tuple(sorted(content_types))
    return "", tuple(sorted(content_types))


def _gmail_labels(message: EmailMessage) -> tuple[str, ...]:
    raw = message.get("X-Gmail-Labels", "")
    labels = {item.strip().strip('"') for item in raw.split(",") if item.strip()}
    return tuple(sorted(labels, key=str.casefold))


def _parse_message(data: bytes, source_name: str, source_index: int) -> RawMessage:
    parsed = BytesParser(policy=policy.default).parsebytes(data)
    if not isinstance(parsed, EmailMessage):
        raise ValueError("parser did not produce an EmailMessage")
    date_header = parsed.get("Date", "")
    if not date_header:
        raise ValueError("missing Date header")
    date = parse_email_date(date_header)
    sender_values = parse_addresses(parsed.get("From", ""), parsed.get("Sender", ""))
    if not sender_values:
        raise ValueError("missing usable From header")
    recipients = parse_addresses(
        parsed.get("To", ""),
        parsed.get("Cc", ""),
        parsed.get("Bcc", ""),
        parsed.get("Delivered-To", ""),
        parsed.get("X-Original-To", ""),
    )
    subject = str(parsed.get("Subject", "")).strip()
    body, content_types = _message_body(parsed)
    raw_id = canonical_message_id(parsed.get("Message-ID", ""))
    if not raw_id:
        generated = stable_id(
            "generated", date.isoformat(), sender_values[0], subject, body, str(source_index)
        )
        raw_id = f"<{generated}@loopledger.local>"
    return RawMessage(
        message_id=raw_id,
        source_name=source_name,
        source_index=source_index,
        date=date,
        sender=sender_values[0],
        recipients=recipients,
        subject=subject,
        normalized_subject=normalize_subject(subject),
        body=body,
        references=parse_message_ids(parsed.get("References", "")),
        in_reply_to=parse_message_ids(parsed.get("In-Reply-To", "")),
        labels=_gmail_labels(parsed),
        auto_submitted=str(parsed.get("Auto-Submitted", "")).strip().casefold(),
        precedence=str(parsed.get("Precedence", "")).strip().casefold(),
        list_id=str(parsed.get("List-Id", "")).strip(),
        content_types=content_types,
    )


def _file_fingerprint(path: Path, name: str, kind: str) -> SourceFingerprint:
    data = path.read_bytes()
    return SourceFingerprint(
        name=name,
        kind=kind,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
    )


def _directory_fingerprint(path: Path, files: list[Path], kind: str) -> SourceFingerprint:
    digest = hashlib.sha256()
    total = 0
    for file_path in files:
        data = file_path.read_bytes()
        relative = file_path.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
        digest.update(b"\0")
        total += len(data)
    return SourceFingerprint(name=path.name, kind=kind, sha256=digest.hexdigest(), size=total)


def _load_mbox(path: Path) -> tuple[list[RawMessage], SourceFingerprint, list[str]]:
    messages: list[RawMessage] = []
    warnings: list[str] = []
    box = mailbox.mbox(path, create=False)
    try:
        for index, message in enumerate(box):
            try:
                data = message.as_bytes(policy=policy.default, unixfrom=False)
                messages.append(_parse_message(data, path.name, index))
            except (OSError, TypeError, ValueError) as exc:
                warnings.append(f"{path.name} message {index}: {exc}")
    finally:
        box.close()
    return messages, _file_fingerprint(path, path.name, "mbox"), warnings


def _load_eml_directory(path: Path) -> tuple[list[RawMessage], SourceFingerprint, list[str]]:
    files = sorted(item for item in path.rglob("*.eml") if item.is_file())
    messages: list[RawMessage] = []
    warnings: list[str] = []
    for index, file_path in enumerate(files):
        relative = file_path.relative_to(path).as_posix()
        try:
            messages.append(_parse_message(file_path.read_bytes(), relative, index))
        except (OSError, TypeError, ValueError) as exc:
            warnings.append(f"{relative}: {exc}")
    return messages, _directory_fingerprint(path, files, "eml-directory"), warnings


def _load_maildir(path: Path) -> tuple[list[RawMessage], SourceFingerprint, list[str]]:
    files = sorted(
        item
        for folder in (path / "cur", path / "new")
        for item in folder.glob("*")
        if item.is_file()
    )
    messages: list[RawMessage] = []
    warnings: list[str] = []
    for index, file_path in enumerate(files):
        relative = file_path.relative_to(path).as_posix()
        try:
            messages.append(_parse_message(file_path.read_bytes(), relative, index))
        except (OSError, TypeError, ValueError) as exc:
            warnings.append(f"{relative}: {exc}")
    return messages, _directory_fingerprint(path, files, "maildir"), warnings


def load_sources(paths: Iterable[Path]) -> ParseResult:
    """Load all supported inputs and retain non-fatal per-message warnings."""

    messages: list[RawMessage] = []
    fingerprints: list[SourceFingerprint] = []
    warnings: list[str] = []
    seen_sources: set[Path] = set()
    for supplied in paths:
        path = supplied.expanduser().resolve()
        if path in seen_sources:
            continue
        seen_sources.add(path)
        if not path.exists():
            raise ValueError(f"input does not exist: {supplied}")
        if path.is_dir():
            is_maildir = (path / "cur").is_dir() and (path / "new").is_dir()
            loaded, fingerprint, source_warnings = (
                _load_maildir(path) if is_maildir else _load_eml_directory(path)
            )
            if not loaded and not source_warnings:
                raise ValueError(f"directory contains no readable .eml messages: {supplied}")
        elif path.suffix.casefold() in {".mbox", ".mbx"}:
            loaded, fingerprint, source_warnings = _load_mbox(path)
        elif path.suffix.casefold() == ".eml":
            data = path.read_bytes()
            try:
                loaded = [_parse_message(data, path.name, 0)]
                source_warnings = []
            except (OSError, TypeError, ValueError) as exc:
                loaded = []
                source_warnings = [f"{path.name}: {exc}"]
            fingerprint = SourceFingerprint(
                name=path.name,
                kind="eml",
                sha256=hashlib.sha256(data).hexdigest(),
                size=len(data),
            )
        else:
            raise ValueError(
                f"unsupported input type: {supplied} (expected .mbox, .eml, or directory)"
            )
        messages.extend(loaded)
        fingerprints.append(fingerprint)
        warnings.extend(source_warnings)
    if not messages:
        details = f" ({'; '.join(warnings)})" if warnings else ""
        raise ValueError(f"no usable email messages were found{details}")
    return ParseResult(
        messages=tuple(messages),
        fingerprints=tuple(fingerprints),
        warnings=tuple(warnings),
    )
