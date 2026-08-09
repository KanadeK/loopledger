"""Explainable, deterministic request and automation signals."""

from __future__ import annotations

import re

from loopledger.models import RawMessage, RequestSignal
from loopledger.utils import strip_quoted_reply

_COURTESY_ONLY = re.compile(
    r"^(?:thanks|thank you|thx|got it|received|noted|great|perfect|okay|ok|sounds good|"
    r"谢谢|感谢|收到|好的|好)$",
    re.IGNORECASE,
)
_EXPLICIT_REQUEST = re.compile(
    r"\b(?:please|could you|can you|would you|will you|let me know|"
    r"get back to me|reply|respond|send me|share with me|need your)\b|"
    r"(?:请|麻烦|劳烦|能否|可否|是否|请问|回复|答复|反馈|发给我|提供)",
    re.IGNORECASE,
)
_DECISION_REQUEST = re.compile(
    r"\b(?:approve|approval|confirm|confirmation|review|feedback|sign[ -]?off|decision)\b|"
    r"(?:批准|审批|确认|审核|评审|意见|决定)",
    re.IGNORECASE,
)
_QUESTION_FORM = re.compile(
    r"\b(?:who|what|when|where|why|how|which|are you|do you|did you|have you)\b|"
    r"(?:谁|什么|何时|什么时候|哪里|为何|为什么|怎么|如何|哪一|吗|么)[？?]?",
    re.IGNORECASE,
)
_DEADLINE = re.compile(
    r"\b(?:by|before|due|deadline|eod|eow|today|tomorrow|this week|next week)\b|"
    r"(?:截止|之前|今天|明天|本周|下周|月底|尽快)",
    re.IGNORECASE,
)
_FOLLOW_UP = re.compile(
    r"\b(?:follow(?:ing)? up|checking in|circling back|waiting for|pending)\b|"
    r"(?:跟进|再确认|等待|尚未|未收到)",
    re.IGNORECASE,
)
_AUTOMATED_SENDER = re.compile(
    r"(?:^|[._+-])(?:no-?reply|do-?not-?reply|mailer-daemon|postmaster)(?:@|[._+-])",
    re.IGNORECASE,
)
_AUTOMATED_SUBJECT = re.compile(
    r"\b(?:automatic reply|out of office|delivery status notification|undeliverable|"
    r"newsletter|receipt|password reset|verify your email)\b|"
    r"(?:自动回复|外出回复|投递失败|退信|电子报|收据|验证码)",
    re.IGNORECASE,
)


def request_signal(message: RawMessage) -> RequestSignal:
    """Score whether the current, unquoted body asks the recipient to act or reply."""

    text = strip_quoted_reply(message.body or message.subject).strip()
    compact = " ".join(text.split())
    if not compact:
        return RequestSignal(score=0, reasons=(), exclusions=("empty_content",))
    if _COURTESY_ONLY.fullmatch(compact.rstrip(".!。！")):
        return RequestSignal(score=0, reasons=(), exclusions=("courtesy_only",))

    score = 0
    reasons: list[str] = []
    if "?" in compact or "？" in compact:
        score += 2
        reasons.append("question_mark")
    if _EXPLICIT_REQUEST.search(compact):
        score += 3
        reasons.append("explicit_request")
    if _DECISION_REQUEST.search(compact):
        score += 2
        reasons.append("decision_or_review")
    if _QUESTION_FORM.search(compact):
        score += 1
        reasons.append("question_form")
    if _DEADLINE.search(compact):
        score += 2
        reasons.append("deadline_language")
    if _FOLLOW_UP.search(compact):
        score += 2
        reasons.append("follow_up_language")
    return RequestSignal(score=score, reasons=tuple(reasons))


def automation_reasons(message: RawMessage) -> tuple[str, ...]:
    """Return deterministic reasons why a message is machine-generated or bulk mail."""

    reasons: list[str] = []
    if message.auto_submitted and message.auto_submitted != "no":
        reasons.append("auto_submitted")
    if message.precedence in {"bulk", "junk", "list"}:
        reasons.append("bulk_precedence")
    if message.list_id:
        reasons.append("list_id")
    if _AUTOMATED_SENDER.search(message.sender):
        reasons.append("automated_sender")
    if _AUTOMATED_SUBJECT.search(message.subject):
        reasons.append("automated_subject")
    if "message/delivery-status" in message.content_types:
        reasons.append("delivery_status")
    return tuple(dict.fromkeys(reasons))


def is_automated(message: RawMessage) -> bool:
    return bool(automation_reasons(message))
