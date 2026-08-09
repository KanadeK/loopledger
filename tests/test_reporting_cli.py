from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

from loopledger.cli import EXIT_INPUT, EXIT_OK, EXIT_OVERDUE, EXIT_VERIFY, EXIT_WARNINGS, main
from loopledger.engine import ScanConfig, analyze
from loopledger.parsers import load_sources
from loopledger.reporting import result_dict, verify_manifest, write_reports
from loopledger.sample import sample_mbox_bytes, write_sample


def sample_result() -> object:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "demo.mbox"
        path.write_bytes(sample_mbox_bytes())
        parsed = load_sources([path])
    return analyze(
        parsed,
        ScanConfig(
            identities=frozenset({"alex@example.com"}),
            as_of=datetime(2026, 2, 1, tzinfo=UTC),
        ),
    )


def generic_eml(*, include_date: bool = True, include_sent_label: bool = False) -> bytes:
    message = EmailMessage(policy=policy.default)
    message["From"] = "Alex <alex@example.com>"
    message["To"] = "Morgan <morgan@example.net>"
    message["Subject"] = "Please confirm"
    if include_date:
        message["Date"] = format_datetime(datetime(2026, 1, 1, tzinfo=UTC))
    message["Message-ID"] = "<generic@example.com>"
    if include_sent_label:
        message["X-Gmail-Labels"] = "Sent"
    message.set_content("Please confirm this request.")
    return message.as_bytes(policy=policy.default)


class ReportingTests(unittest.TestCase):
    def test_result_dict_has_public_schema(self) -> None:
        payload = result_dict(sample_result())  # type: ignore[arg-type]
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["tool"]["version"], "0.1.0")
        self.assertEqual(len(payload["open_loops"]), 3)

    def test_write_and_verify_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            paths = write_reports(sample_result(), output)  # type: ignore[arg-type]
            valid, messages = verify_manifest(output / "manifest.json")
            self.assertTrue(valid)
            self.assertEqual(len(paths), 5)
            self.assertEqual(len(messages), 4)
            self.assertTrue((output / "index.html").is_file())

    def test_manifest_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            write_reports(sample_result(), output)  # type: ignore[arg-type]
            (output / "report.csv").write_text("tampered", encoding="utf-8")
            valid, messages = verify_manifest(output / "manifest.json")
        self.assertFalse(valid)
        self.assertTrue(any("mismatch" in message for message in messages))

    def test_verify_rejects_missing_or_malformed_manifest(self) -> None:
        valid, _ = verify_manifest(Path("missing-manifest.json"))
        self.assertFalse(valid)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text('{"schema_version": 2}', encoding="utf-8")
            self.assertFalse(verify_manifest(path)[0])
            path.write_text('{"schema_version": 1, "files": {}}', encoding="utf-8")
            self.assertFalse(verify_manifest(path)[0])

    def test_verify_rejects_unsafe_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "files": {"../escape": {"bytes": 0, "sha256": "x"}},
                    }
                ),
                encoding="utf-8",
            )
            valid, messages = verify_manifest(path)
        self.assertFalse(valid)
        self.assertIn("unsafe", messages[0])

    def test_verify_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            write_reports(sample_result(), output)  # type: ignore[arg-type]
            (output / "report.json").unlink()
            valid, messages = verify_manifest(output / "manifest.json")
        self.assertFalse(valid)
        self.assertIn("missing: report.json", messages)

    def test_html_escapes_mail_content(self) -> None:
        result = sample_result()
        first = replace(result.items[0], subject="<script>alert(1)</script>")  # type: ignore[attr-defined]
        changed = replace(result, items=(first, *result.items[1:]))  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            write_reports(changed, output)
            document = (output / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", document)
        self.assertIn("&lt;script&gt;", document)

    def test_csv_and_ics_contain_real_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            result = sample_result()
            write_reports(result, output)  # type: ignore[arg-type]
            csv_text = (output / "report.csv").read_text(encoding="utf-8")
            ics = (output / "follow-ups.ics").read_bytes()
        self.assertEqual(csv_text.count("\n"), 4)
        self.assertIn(b"BEGIN:VCALENDAR\r\n", ics)
        self.assertEqual(ics.count(b"BEGIN:VEVENT"), 3)

    def test_empty_result_has_useful_html(self) -> None:
        result = sample_result()
        empty = replace(
            result,
            items=(),
            metrics=replace(result.metrics, overdue_count=0, open_count=0),  # type: ignore[attr-defined]
        )
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            write_reports(empty, output)
            document = (output / "index.html").read_text(encoding="utf-8")
        self.assertIn("No open loops found", document)

    def test_parse_warnings_appear_in_html(self) -> None:
        result = replace(sample_result(), warnings=("bad fixture",))  # type: ignore[arg-type]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            write_reports(result, output)
            document = (output / "index.html").read_text(encoding="utf-8")
        self.assertIn("bad fixture", document)


class CliTests(unittest.TestCase):
    def run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_sample_scan_verify_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mailbox = root / "demo.mbox"
            report = root / "report"
            self.assertEqual(self.run_cli(["sample", str(mailbox)])[0], EXIT_OK)
            scan_code, stdout, _ = self.run_cli(
                ["scan", str(mailbox), "--as-of", "2026-02-01", "--output", str(report)]
            )
            verify_code, _, _ = self.run_cli(["verify", str(report / "manifest.json")])
        self.assertEqual(scan_code, EXIT_OK)
        self.assertIn("3 overdue", stdout)
        self.assertEqual(verify_code, EXIT_OK)

    def test_sample_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.mbox"
            write_sample(path)
            code, _, stderr = self.run_cli(["sample", str(path)])
            self.assertEqual(code, EXIT_INPUT)
            self.assertIn("--force", stderr)
            self.assertEqual(self.run_cli(["sample", str(path), "--force"])[0], EXIT_OK)

    def test_doctor_reports_inferred_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.mbox"
            path.write_bytes(sample_mbox_bytes())
            code, stdout, _ = self.run_cli(["doctor", str(path)])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("alex@example.com (inferred)", stdout)

    def test_generic_eml_requires_explicit_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "one.eml"
            path.write_bytes(generic_eml())
            code, _, stderr = self.run_cli(["doctor", str(path)])
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("pass --identity", stderr)

    def test_comma_separated_identities_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "one.eml"
            path.write_bytes(generic_eml())
            code, stdout, _ = self.run_cli(
                ["doctor", str(path), "--identity", "alex@example.com,alias@example.com"]
            )
        self.assertEqual(code, EXIT_OK)
        self.assertIn("alex@example.com, alias@example.com", stdout)

    def test_fail_on_overdue_writes_then_exits_four(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "demo.mbox"
            output = root / "report"
            path.write_bytes(sample_mbox_bytes())
            code, _, stderr = self.run_cli(
                [
                    "scan",
                    str(path),
                    "--as-of",
                    "2026-02-01",
                    "--output",
                    str(output),
                    "--fail-on-overdue",
                ]
            )
            manifest_exists = (output / "manifest.json").is_file()
        self.assertEqual(code, EXIT_OVERDUE)
        self.assertTrue(manifest_exists)
        self.assertIn("reports were written", stderr)

    def test_strict_doctor_returns_three_for_skipped_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "good.eml").write_bytes(generic_eml(include_sent_label=True))
            (root / "bad.eml").write_bytes(generic_eml(include_date=False))
            code, _, stderr = self.run_cli(["doctor", str(root), "--strict"])
        self.assertEqual(code, EXIT_WARNINGS)
        self.assertIn("missing Date", stderr)

    def test_strict_scan_writes_then_returns_three(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "mail"
            source.mkdir()
            (source / "good.eml").write_bytes(generic_eml(include_sent_label=True))
            (source / "bad.eml").write_bytes(generic_eml(include_date=False))
            output = root / "report"
            code, _, _ = self.run_cli(
                [
                    "scan",
                    str(source),
                    "--as-of",
                    "2026-02-01",
                    "--output",
                    str(output),
                    "--strict",
                ]
            )
            exists = (output / "report.json").is_file()
        self.assertEqual(code, EXIT_WARNINGS)
        self.assertTrue(exists)

    def test_verify_command_returns_five_after_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            write_reports(sample_result(), output)  # type: ignore[arg-type]
            (output / "index.html").write_text("tampered", encoding="utf-8")
            code, _, stderr = self.run_cli(["verify", str(output / "manifest.json")])
        self.assertEqual(code, EXIT_VERIFY)
        self.assertIn("mismatch", stderr)

    def test_bad_duration_returns_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.mbox"
            path.write_bytes(sample_mbox_bytes())
            code, _, stderr = self.run_cli(["scan", str(path), "--min-age", "tomorrow"])
        self.assertEqual(code, EXIT_INPUT)
        self.assertIn("duration", stderr)


if __name__ == "__main__":
    unittest.main()
