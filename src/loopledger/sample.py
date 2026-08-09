"""Deterministic, fictional email data for demos and integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path


def _message(
    *,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    when: datetime,
    message_id: str,
    labels: str,
    in_reply_to: str = "",
    references: str = "",
    auto_submitted: str = "",
) -> EmailMessage:
    message = EmailMessage(policy=policy.default)
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Date"] = format_datetime(when)
    message["Message-ID"] = message_id
    message["X-Gmail-Labels"] = labels
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references
    if auto_submitted:
        message["Auto-Submitted"] = auto_submitted
    message.set_content(body)
    return message


def sample_mbox_bytes() -> bytes:
    """Return a stable MBOX with open, closed, low-signal, and automated threads."""

    messages = [
        _message(
            sender="Alex Example <alex@example.com>",
            recipient="Morgan Vendor <morgan@example.net>",
            subject="Quote for the accessibility audit",
            body="Could you send the revised quote by Friday? Please include the workshop option.",
            when=datetime(2026, 1, 10, 9, 0, tzinfo=UTC),
            message_id="<quote-1@example.com>",
            labels="Sent,Project Atlas",
        ),
        _message(
            sender="Alex Example <alex@example.com>",
            recipient="Riley Reviewer <riley@example.org>",
            subject="Review the launch checklist",
            body="Please review the launch checklist and confirm whether section four is ready.",
            when=datetime(2026, 1, 11, 10, 0, tzinfo=UTC),
            message_id="<review-1@example.com>",
            labels="Sent",
        ),
        _message(
            sender="Riley Reviewer <riley@example.org>",
            recipient="Alex Example <alex@example.com>",
            subject="Re: Review the launch checklist",
            body="Confirmed. Section four is ready to ship.",
            when=datetime(2026, 1, 12, 8, 30, tzinfo=UTC),
            message_id="<review-2@example.org>",
            labels="Inbox,Important",
            in_reply_to="<review-1@example.com>",
            references="<review-1@example.com>",
        ),
        _message(
            sender="Alex Example <alex@example.com>",
            recipient="Team List <team@example.net>",
            subject="FYI: office closure",
            body="The office will be closed on Monday. No action is needed.",
            when=datetime(2026, 1, 13, 12, 0, tzinfo=UTC),
            message_id="<fyi-1@example.com>",
            labels="Sent",
        ),
        _message(
            sender="Alex Example <alex@example.com>",
            recipient="Chen Wei <chen@example.cn>",
            subject="请确认采购审批",
            body="麻烦确认采购审批是否可以在本周完成？请回复最终决定。",
            when=datetime(2026, 1, 14, 2, 0, tzinfo=UTC),
            message_id="<approval-1@example.com>",
            labels="Sent,采购",
        ),
        _message(
            sender="Alex Example <alex@example.com>",
            recipient="Taylor Planner <taylor@example.net>",
            subject="Workshop date",
            body="Can you confirm whether 22 January works for the workshop?",
            when=datetime(2026, 1, 15, 15, 0, tzinfo=UTC),
            message_id="<workshop-1@example.com>",
            labels="Sent",
        ),
        _message(
            sender="Taylor Planner <taylor@example.net>",
            recipient="Alex Example <alex@example.com>",
            subject="Re: Workshop date",
            body="The 22nd works for me.",
            when=datetime(2026, 1, 16, 15, 0, tzinfo=UTC),
            message_id="<workshop-2@example.net>",
            labels="Inbox",
            in_reply_to="<workshop-1@example.com>",
            references="<workshop-1@example.com>",
        ),
        _message(
            sender="Alex Example <alex@example.com>",
            recipient="Taylor Planner <taylor@example.net>",
            subject="Re: Workshop date",
            body="Great. Could you send the room capacity and projector details by next week?",
            when=datetime(2026, 1, 17, 16, 0, tzinfo=UTC),
            message_id="<workshop-3@example.com>",
            labels="Sent",
            in_reply_to="<workshop-2@example.net>",
            references="<workshop-1@example.com> <workshop-2@example.net>",
        ),
        _message(
            sender="no-reply@service.example",
            recipient="Alex Example <alex@example.com>",
            subject="Automatic receipt",
            body="This automatic receipt confirms that your upload completed.",
            when=datetime(2026, 1, 18, 7, 0, tzinfo=UTC),
            message_id="<receipt-1@service.example>",
            labels="Inbox",
            auto_submitted="auto-generated",
        ),
    ]
    chunks: list[bytes] = []
    for message in messages:
        when = message["Date"].datetime
        sender = message["From"].addresses[0].addr_spec
        unix_from = f"From {sender} {when.strftime('%a %b %d %H:%M:%S %Y')}\n".encode()
        chunks.append(unix_from + message.as_bytes(policy=policy.default) + b"\n")
    return b"".join(chunks).rstrip(b"\r\n") + b"\n"


def write_sample(path: Path, *, force: bool = False) -> None:
    """Write the sample without silently replacing user data."""

    if path.exists() and not force:
        raise ValueError(f"output already exists: {path} (pass --force to replace the demo file)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(sample_mbox_bytes())
