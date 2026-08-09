"""Rebuild mail threads from RFC references with a conservative fallback."""

from __future__ import annotations

from collections import defaultdict

from loopledger.models import MailThread, RawMessage
from loopledger.utils import stable_id


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            parent = self.parent[item]
            self.parent[item] = root
            item = parent
        return root

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def _external_participants(message: RawMessage, identities: frozenset[str]) -> tuple[str, ...]:
    values = {message.sender, *message.recipients} - identities
    return tuple(sorted(item for item in values if item))


def build_threads(
    messages: tuple[RawMessage, ...], identities: frozenset[str]
) -> tuple[MailThread, ...]:
    """Group messages using Message-ID edges, then subject plus external participants."""

    if not messages:
        return ()
    union_find = _UnionFind(len(messages))
    id_to_index = {message.message_id: index for index, message in enumerate(messages)}
    referenced: set[int] = set()
    for index, message in enumerate(messages):
        for reference in (*message.references, *message.in_reply_to):
            other = id_to_index.get(reference)
            if other is not None:
                union_find.union(index, other)
                referenced.add(index)
                referenced.add(other)

    fallback: dict[tuple[str, tuple[str, ...]], int] = {}
    for index, message in enumerate(messages):
        participants = _external_participants(message, identities)
        if not message.normalized_subject or not participants:
            continue
        key = (message.normalized_subject, participants)
        first = fallback.get(key)
        if first is None:
            fallback[key] = index
        elif index not in referenced or first not in referenced:
            union_find.union(first, index)

    groups: dict[int, list[RawMessage]] = defaultdict(list)
    for index, message in enumerate(messages):
        groups[union_find.find(index)].append(message)

    threads: list[MailThread] = []
    for group in groups.values():
        ordered = tuple(
            sorted(group, key=lambda item: (item.date, item.source_name, item.source_index))
        )
        participants = tuple(
            sorted(
                {
                    participant
                    for message in ordered
                    for participant in _external_participants(message, identities)
                }
            )
        )
        subject = next((item.subject for item in reversed(ordered) if item.subject), "(no subject)")
        thread_id = stable_id("thread", *(item.message_id for item in ordered))
        threads.append(
            MailThread(
                thread_id=thread_id,
                subject=subject,
                participants=participants,
                messages=ordered,
            )
        )
    return tuple(sorted(threads, key=lambda item: item.thread_id))
