"""Dependency-free command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from loopledger import __version__
from loopledger.engine import ScanConfig, analyze, infer_identities
from loopledger.models import ParseResult
from loopledger.parsers import load_sources
from loopledger.reporting import verify_manifest, write_reports
from loopledger.sample import write_sample
from loopledger.state import load_state
from loopledger.utils import normalize_address, parse_datetime, parse_duration

EXIT_OK = 0
EXIT_INPUT = 2
EXIT_WARNINGS = 3
EXIT_OVERDUE = 4
EXIT_VERIFY = 5


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loopledger",
        description="Find sent emails still awaiting a reply, entirely offline.",
        epilog="Privacy: LoopLedger reads local exports only and never opens a network connection.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="analyze MBOX, Maildir, or EML inputs")
    scan.add_argument("inputs", nargs="+", type=Path, help="mail source paths")
    scan.add_argument(
        "--identity",
        action="append",
        default=[],
        help=(
            "your email address or comma-separated aliases; inferred from Gmail Sent labels "
            "when omitted"
        ),
    )
    scan.add_argument("--output", type=Path, default=Path("loopledger-report"))
    scan.add_argument("--as-of", help="ISO date/time for reproducible age calculations")
    scan.add_argument("--min-age", default="3d", help="minimum wait before inclusion (default: 3d)")
    scan.add_argument(
        "--overdue-after", default="7d", help="age that marks a loop overdue (default: 7d)"
    )
    scan.add_argument("--request-threshold", type=int, default=3)
    scan.add_argument(
        "--include-all-outbound",
        action="store_true",
        help="include any thread whose last message is outbound, even without request wording",
    )
    scan.add_argument("--state", type=Path, help="optional version-1 JSON ignore/snooze decisions")
    scan.add_argument("--strict", action="store_true", help="exit 3 when any message was skipped")
    scan.add_argument(
        "--fail-on-overdue",
        action="store_true",
        help="write reports, then exit 4 if overdue loops exist",
    )

    doctor = subparsers.add_parser("doctor", help="validate sources and identity inference")
    doctor.add_argument("inputs", nargs="+", type=Path)
    doctor.add_argument("--identity", action="append", default=[])
    doctor.add_argument("--strict", action="store_true")

    sample = subparsers.add_parser("sample", help="write a fictional, deterministic demo MBOX")
    sample.add_argument("output", nargs="?", type=Path, default=Path("loopledger-demo.mbox"))
    sample.add_argument("--force", action="store_true")

    verify = subparsers.add_parser("verify", help="verify a report manifest and its sibling files")
    verify.add_argument("manifest", type=Path)
    return parser


def _identities(values: Sequence[str]) -> tuple[str, ...]:
    found = {
        normalize_address(item) for value in values for item in value.split(",") if item.strip()
    }
    return tuple(sorted(found))


def _load_with_identities(
    inputs: Sequence[Path], supplied: Sequence[str]
) -> tuple[ParseResult, tuple[str, ...], bool]:
    parsed = load_sources(inputs)
    identities = _identities(supplied)
    inferred = False
    if not identities:
        identities = infer_identities(parsed.messages)
        inferred = True
    if not identities:
        raise ValueError(
            "could not infer your address because no Gmail Sent labels were found; "
            "repair: pass --identity you@example.com (repeat for aliases)"
        )
    return parsed, identities, inferred


def _scan(args: argparse.Namespace) -> int:
    parsed, identities, inferred = _load_with_identities(args.inputs, args.identity)
    as_of = parse_datetime(args.as_of) if args.as_of else datetime.now(UTC)
    config = ScanConfig(
        identities=frozenset(identities),
        as_of=as_of,
        min_age=parse_duration(args.min_age),
        overdue_after=parse_duration(args.overdue_after),
        request_threshold=args.request_threshold,
        include_all_outbound=args.include_all_outbound,
        state=load_state(args.state),
    )
    result = analyze(parsed, config)
    paths = write_reports(result, args.output)
    identity_note = " (inferred from Sent labels)" if inferred else ""
    print(f"Identities: {', '.join(identities)}{identity_note}")
    print(
        f"Scanned {result.metrics.total_messages} messages in "
        f"{result.metrics.total_threads} threads: "
        f"{result.metrics.overdue_count} overdue, {result.metrics.open_count} open, "
        f"{result.metrics.snoozed_count} snoozed."
    )
    for path in paths:
        print(f"Wrote {path}")
    if args.strict and result.warnings:
        print(f"Strict mode: {len(result.warnings)} parse warning(s).", file=sys.stderr)
        return EXIT_WARNINGS
    if args.fail_on_overdue and result.metrics.overdue_count:
        print("Overdue loops found; reports were written before exit 4.", file=sys.stderr)
        return EXIT_OVERDUE
    return EXIT_OK


def _doctor(args: argparse.Namespace) -> int:
    parsed, identities, inferred = _load_with_identities(args.inputs, args.identity)
    print(f"OK: {len(parsed.messages)} usable message(s) from {len(parsed.fingerprints)} source(s)")
    print(f"Identity: {', '.join(identities)}{' (inferred)' if inferred else ''}")
    for source in parsed.fingerprints:
        print(f"Source: {source.name} [{source.kind}] {source.size} bytes sha256={source.sha256}")
    for warning in parsed.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    return EXIT_WARNINGS if args.strict and parsed.warnings else EXIT_OK


def _sample(args: argparse.Namespace) -> int:
    write_sample(args.output, force=args.force)
    print(f"Wrote fictional demo mailbox: {args.output}")
    print(
        "Next: loopledger scan "
        f'"{args.output}" --identity alex@example.com --as-of 2026-02-01 --output demo-output'
    )
    return EXIT_OK


def _verify(args: argparse.Namespace) -> int:
    valid, messages = verify_manifest(args.manifest)
    for message in messages:
        print(message, file=sys.stdout if valid else sys.stderr)
    return EXIT_OK if valid else EXIT_VERIFY


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and convert expected failures into documented exit codes."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            return _scan(args)
        if args.command == "doctor":
            return _doctor(args)
        if args.command == "sample":
            return _sample(args)
        if args.command == "verify":
            return _verify(args)
    except (OSError, ValueError) as exc:
        print(f"loopledger: error: {exc}", file=sys.stderr)
        return EXIT_INPUT
    parser.error(f"unknown command: {args.command}")
    return EXIT_INPUT
