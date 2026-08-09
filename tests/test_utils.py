from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from loopledger.utils import (
    canonical_message_id,
    compact_snippet,
    normalize_address,
    normalize_subject,
    parse_addresses,
    parse_datetime,
    parse_duration,
    parse_email_date,
    parse_message_ids,
    stable_id,
    strip_quoted_reply,
)


class UtilsTests(unittest.TestCase):
    def test_normalize_address(self) -> None:
        self.assertEqual(normalize_address(" <Alex@Example.COM> "), "alex@example.com")

    def test_parse_addresses_handles_multiple_headers(self) -> None:
        self.assertEqual(
            parse_addresses("Morgan <morgan@example.net>", "Riley <riley@example.org>"),
            ("morgan@example.net", "riley@example.org"),
        )

    def test_parse_addresses_deduplicates(self) -> None:
        self.assertEqual(
            parse_addresses("Alex <ALEX@example.com>, alex@example.com"),
            ("alex@example.com",),
        )

    def test_canonical_message_id(self) -> None:
        self.assertEqual(canonical_message_id(" ID@Example.COM "), "<id@example.com>")
        self.assertEqual(canonical_message_id(""), "")

    def test_parse_message_ids(self) -> None:
        self.assertEqual(
            parse_message_ids("<one@EXAMPLE> <two@example> <one@example>"),
            ("<one@example>", "<two@example>"),
        )

    def test_parse_message_ids_falls_back_to_tokens(self) -> None:
        self.assertEqual(
            parse_message_ids("one@example two@example"),
            ("<one@example>", "<two@example>"),
        )

    def test_normalize_subject_removes_nested_prefixes(self) -> None:
        self.assertEqual(normalize_subject(" Re: FWD:  Project   Plan "), "project plan")
        self.assertEqual(normalize_subject("回复: 答复: 采购审批"), "采购审批")

    def test_parse_email_date_normalizes_to_utc(self) -> None:
        self.assertEqual(
            parse_email_date("Thu, 1 Jan 2026 09:00:00 +0100"),
            datetime(2026, 1, 1, 8, tzinfo=UTC),
        )

    def test_parse_email_date_assumes_utc_when_naive(self) -> None:
        self.assertEqual(
            parse_email_date("Thu, 1 Jan 2026 09:00:00"),
            datetime(2026, 1, 1, 9, tzinfo=UTC),
        )

    def test_parse_datetime_date_and_zulu(self) -> None:
        self.assertEqual(parse_datetime("2026-02-01"), datetime(2026, 2, 1, tzinfo=UTC))
        self.assertEqual(
            parse_datetime("2026-02-01T02:00:00Z"), datetime(2026, 2, 1, 2, tzinfo=UTC)
        )

    def test_parse_duration_units(self) -> None:
        self.assertEqual(parse_duration("90m"), timedelta(minutes=90))
        self.assertEqual(parse_duration("2W"), timedelta(weeks=2))

    def test_parse_duration_rejects_ambiguous_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer followed"):
            parse_duration("1.5d")

    def test_strip_quoted_reply(self) -> None:
        body = "Please confirm.\n\nOn Monday, Morgan wrote:\n> Old question"
        self.assertEqual(strip_quoted_reply(body), "Please confirm.")

    def test_strip_quoted_reply_drops_quote_lines(self) -> None:
        self.assertEqual(
            strip_quoted_reply("New answer\n> prior text\nThanks"),
            "New answer\nThanks",
        )

    def test_compact_snippet_caps_content(self) -> None:
        self.assertEqual(compact_snippet("one   two\nthree", 20), "one two three")
        self.assertEqual(compact_snippet("abcdefghij", 6), "abcde…")

    def test_stable_id_is_deterministic_and_namespaced(self) -> None:
        self.assertEqual(stable_id("loop", "a", "b"), stable_id("loop", "a", "b"))
        self.assertTrue(stable_id("loop", "a").startswith("loop-"))
        self.assertNotEqual(stable_id("loop", "a"), stable_id("loop", "b"))


if __name__ == "__main__":
    unittest.main()
