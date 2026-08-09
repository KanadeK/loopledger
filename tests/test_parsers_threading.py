from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

from loopledger.engine import infer_identities
from loopledger.parsers import load_sources
from loopledger.sample import sample_mbox_bytes
from loopledger.threading import build_threads


def email_bytes(*, html: bool = False, message_id: bool = True, date: bool = True) -> bytes:
    message = EmailMessage(policy=policy.default)
    message["From"] = "Alex <alex@example.com>"
    message["To"] = "Morgan <morgan@example.net>"
    message["Subject"] = "Status request"
    if date:
        message["Date"] = format_datetime(datetime(2026, 1, 1, tzinfo=UTC))
    if message_id:
        message["Message-ID"] = "<status@example.com>"
    message["X-Gmail-Labels"] = "Sent"
    message.set_content(
        "<p>Please <strong>confirm</strong> status.</p>" if html else "Please confirm status.",
        subtype="html" if html else "plain",
    )
    return message.as_bytes(policy=policy.default)


class ParserThreadingTests(unittest.TestCase):
    def test_sample_mbox_loads_real_recipients_and_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.mbox"
            data = sample_mbox_bytes()
            path.write_bytes(data)
            parsed = load_sources([path])
        self.assertEqual(len(parsed.messages), 9)
        self.assertEqual(parsed.messages[0].recipients, ("morgan@example.net",))
        self.assertEqual(parsed.fingerprints[0].sha256, hashlib.sha256(data).hexdigest())

    def test_identity_is_inferred_only_from_sent_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.mbox"
            path.write_bytes(sample_mbox_bytes())
            parsed = load_sources([path])
        self.assertEqual(infer_identities(parsed.messages), ("alex@example.com",))

    def test_reference_threading_rebuilds_sample_threads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.mbox"
            path.write_bytes(sample_mbox_bytes())
            parsed = load_sources([path])
        threads = build_threads(parsed.messages, frozenset({"alex@example.com"}))
        self.assertEqual(len(threads), 6)
        workshop = next(thread for thread in threads if "Workshop date" in thread.subject)
        self.assertEqual(len(workshop.messages), 3)

    def test_html_only_eml_is_converted_to_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "one.eml"
            path.write_bytes(email_bytes(html=True))
            parsed = load_sources([path])
        self.assertIn("Please confirm status.", parsed.messages[0].body)
        self.assertIn("text/html", parsed.messages[0].content_types)

    def test_directory_reads_eml_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nested = root / "nested"
            nested.mkdir()
            (nested / "one.eml").write_bytes(email_bytes())
            parsed = load_sources([root])
        self.assertEqual(len(parsed.messages), 1)
        self.assertEqual(parsed.fingerprints[0].kind, "eml-directory")

    def test_maildir_reads_cur_and_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("cur", "new", "tmp"):
                (root / name).mkdir()
            (root / "new" / "message-1").write_bytes(email_bytes())
            parsed = load_sources([root])
        self.assertEqual(len(parsed.messages), 1)
        self.assertEqual(parsed.fingerprints[0].kind, "maildir")

    def test_invalid_eml_is_a_warning_when_other_messages_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "good.eml").write_bytes(email_bytes())
            (root / "bad.eml").write_bytes(email_bytes(date=False))
            parsed = load_sources([root])
        self.assertEqual(len(parsed.messages), 1)
        self.assertIn("missing Date header", parsed.warnings[0])

    def test_missing_message_id_gets_deterministic_generated_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "one.eml"
            path.write_bytes(email_bytes(message_id=False))
            first = load_sources([path]).messages[0].message_id
            second = load_sources([path]).messages[0].message_id
        self.assertEqual(first, second)
        self.assertIn("@loopledger.local", first)

    def test_duplicate_input_path_is_loaded_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "one.eml"
            path.write_bytes(email_bytes())
            parsed = load_sources([path, path])
        self.assertEqual(len(parsed.messages), 1)
        self.assertEqual(len(parsed.fingerprints), 1)

    def test_missing_input_has_repairable_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "input does not exist"):
            load_sources([Path("definitely-missing.mbox")])

    def test_unsupported_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "mail.txt"
            path.write_text("not mail", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported input type"):
                load_sources([path])

    def test_empty_directory_is_rejected(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp,
            self.assertRaisesRegex(ValueError, "no readable .eml"),
        ):
            load_sources([Path(temp)])

    def test_empty_thread_input(self) -> None:
        self.assertEqual(build_threads((), frozenset({"alex@example.com"})), ())


if __name__ == "__main__":
    unittest.main()
