from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from loopledger.engine import ScanConfig, analyze, direction_of
from loopledger.models import Direction, LoopStatus, ParseResult
from loopledger.parsers import load_sources
from loopledger.sample import sample_mbox_bytes
from loopledger.state import LoopState
from tests.helpers import raw_message


def parsed_sample() -> ParseResult:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "demo.mbox"
        path.write_bytes(sample_mbox_bytes())
        return load_sources([path])


def config(**overrides: object) -> ScanConfig:
    values: dict[str, object] = {
        "identities": frozenset({"alex@example.com"}),
        "as_of": datetime(2026, 2, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return ScanConfig(**values)  # type: ignore[arg-type]


class EngineTests(unittest.TestCase):
    def test_sample_finds_three_real_open_loops(self) -> None:
        result = analyze(parsed_sample(), config())
        self.assertEqual(result.metrics.total_messages, 9)
        self.assertEqual(result.metrics.total_threads, 6)
        self.assertEqual(result.metrics.overdue_count, 3)
        self.assertEqual(result.metrics.closed_by_reply_count, 1)
        self.assertEqual(result.metrics.low_signal_count, 1)
        self.assertEqual(result.metrics.automated_count, 1)
        self.assertTrue(all(item.status == LoopStatus.OVERDUE for item in result.items))

    def test_earlier_as_of_separates_open_and_overdue(self) -> None:
        result = analyze(
            parsed_sample(),
            config(as_of=datetime(2026, 1, 19, tzinfo=UTC)),
        )
        self.assertEqual(result.metrics.overdue_count, 1)
        self.assertEqual(result.metrics.open_count, 1)
        self.assertEqual(result.metrics.too_recent_count, 1)

    def test_include_all_outbound_surfaces_fyi(self) -> None:
        result = analyze(parsed_sample(), config(include_all_outbound=True))
        self.assertEqual(len(result.items), 4)
        fyi = next(item for item in result.items if item.subject.startswith("FYI"))
        self.assertEqual(fyi.request_score, 0)
        self.assertEqual(fyi.reasons, ("last_message_is_outbound",))

    def test_ignore_state_accepts_loop_id(self) -> None:
        parsed = parsed_sample()
        baseline = analyze(parsed, config())
        ignored_id = baseline.items[0].loop_id
        result = analyze(parsed, config(state=LoopState(ignored=frozenset({ignored_id}))))
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.metrics.ignored_by_state_count, 1)

    def test_resolved_state_accepts_message_id(self) -> None:
        parsed = parsed_sample()
        baseline = analyze(parsed, config())
        message_id = baseline.items[0].message_id
        result = analyze(parsed, config(state=LoopState(resolved=frozenset({message_id}))))
        self.assertEqual(len(result.items), 2)

    def test_future_snooze_changes_status(self) -> None:
        parsed = parsed_sample()
        baseline = analyze(parsed, config())
        loop_id = baseline.items[0].loop_id
        until = datetime(2026, 2, 10, tzinfo=UTC)
        state = LoopState(snoozed_until={loop_id: until})
        result = analyze(parsed, config(state=state))
        snoozed = next(item for item in result.items if item.loop_id == loop_id)
        self.assertEqual(snoozed.status, LoopStatus.SNOOZED)
        self.assertEqual(snoozed.snoozed_until, until)

    def test_expired_snooze_returns_to_age_based_status(self) -> None:
        parsed = parsed_sample()
        baseline = analyze(parsed, config())
        loop_id = baseline.items[0].loop_id
        state = LoopState(snoozed_until={loop_id: datetime(2026, 1, 20, tzinfo=UTC)})
        result = analyze(parsed, config(state=state))
        item = next(item for item in result.items if item.loop_id == loop_id)
        self.assertEqual(item.status, LoopStatus.OVERDUE)

    def test_follow_up_after_reply_preserves_previous_reply_evidence(self) -> None:
        result = analyze(parsed_sample(), config())
        workshop = next(item for item in result.items if item.subject.startswith("Re: Workshop"))
        self.assertEqual(
            workshop.previous_external_reply_at,
            datetime(2026, 1, 16, 15, tzinfo=UTC),
        )

    def test_direction_classification(self) -> None:
        identities = frozenset({"alex@example.com"})
        self.assertEqual(direction_of(raw_message(), identities), Direction.OUTBOUND)
        self.assertEqual(
            direction_of(
                raw_message(sender="morgan@example.net", recipients=("alex@example.com",)),
                identities,
            ),
            Direction.INBOUND,
        )
        self.assertEqual(
            direction_of(raw_message(recipients=("alex@example.com",)), identities),
            Direction.SELF,
        )
        self.assertEqual(
            direction_of(
                raw_message(sender="other@example.net", recipients=("third@example.org",)),
                identities,
            ),
            Direction.UNKNOWN,
        )

    def test_inbox_label_is_inbound_when_recipient_header_is_missing(self) -> None:
        message = raw_message(
            sender="morgan@example.net",
            recipients=(),
            labels=("Inbox",),
        )
        self.assertEqual(direction_of(message, frozenset({"alex@example.com"})), Direction.INBOUND)

    def test_aliases_are_normalized(self) -> None:
        parsed = ParseResult(
            messages=(raw_message(sender="alias@example.com"),),
            fingerprints=(),
            warnings=(),
        )
        result = analyze(
            parsed,
            config(identities=frozenset({" ALIAS@EXAMPLE.COM "})),
        )
        self.assertEqual(len(result.items), 1)

    def test_future_dated_outbound_is_not_included(self) -> None:
        parsed = ParseResult(
            messages=(raw_message(date=datetime(2026, 3, 1, tzinfo=UTC)),),
            fingerprints=(),
            warnings=(),
        )
        result = analyze(parsed, config())
        self.assertEqual(result.items, ())
        self.assertEqual(result.metrics.too_recent_count, 1)

    def test_empty_parse_result_is_valid(self) -> None:
        result = analyze(ParseResult(messages=(), fingerprints=(), warnings=()), config())
        self.assertEqual(result.metrics.total_threads, 0)
        self.assertEqual(result.items, ())

    def test_config_requires_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity"):
            config(identities=frozenset())

    def test_config_rejects_negative_thresholds(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            config(min_age=timedelta(days=-1))
        with self.assertRaisesRegex(ValueError, "greater than or equal"):
            config(min_age=timedelta(days=4), overdue_after=timedelta(days=3))
        with self.assertRaisesRegex(ValueError, "request threshold"):
            config(request_threshold=-1)

    def test_naive_as_of_is_assumed_utc(self) -> None:
        value = config(as_of=datetime(2026, 2, 1))
        self.assertEqual(value.as_of.tzinfo, UTC)

    def test_result_keeps_parse_warnings(self) -> None:
        parsed = replace(parsed_sample(), warnings=("fixture warning",))
        self.assertEqual(analyze(parsed, config()).warnings, ("fixture warning",))


if __name__ == "__main__":
    unittest.main()
