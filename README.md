# LoopLedger

[![CI](https://github.com/KanadeK/loopledger/actions/workflows/ci.yml/badge.svg)](https://github.com/KanadeK/loopledger/actions/workflows/ci.yml)
[![CodeQL](https://github.com/KanadeK/loopledger/actions/workflows/security.yml/badge.svg)](https://github.com/KanadeK/loopledger/actions/workflows/security.yml)
[![Release](https://img.shields.io/github/v/release/KanadeK/loopledger)](https://github.com/KanadeK/loopledger/releases/latest)
[![Python](https://img.shields.io/badge/python-3.11%2B-315b7d)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-075e54)](LICENSE)

**Find the emails still waiting on someone else—offline, from MBOX, Maildir, or EML exports.**

[Live fictional report](https://kanadek.github.io/loopledger/) ·
[中文说明](README.zh-CN.md) · [How it works](docs/algorithm.md) ·
[Repair guide](docs/repair.md)

You send a quote request, approval question, or review request. The recipient never replies, the
thread sinks, and a week later the open loop is invisible. Most follow-up products need mailbox
OAuth, a browser extension, a specific email client, or a cloud service. LoopLedger instead reads
an export on your machine and produces an evidence-linked follow-up ledger.

It is a real parser and thread analyzer, not a mailbox-shaped dashboard. The runtime uses only the
Python standard library, opens no network connections, never sends email, and works with exports
from Gmail Takeout, Thunderbird, and other RFC-compatible clients.

## What it actually does

- Parses MBOX, Maildir, one `.eml`, or a directory of `.eml` files.
- Rebuilds conversations from `Message-ID`, `In-Reply-To`, and `References`, with a conservative
  normalized-subject plus participant fallback.
- Finds threads whose last meaningful message is yours and still appears to request a reply.
- Explains each score with signals such as `explicit_request`, `question_mark`,
  `decision_or_review`, and `deadline_language`; English and Chinese wording is supported.
- Filters list mail, delivery failures, receipts, no-reply senders, and other automated traffic.
- Applies stable ignore, resolve, and snooze decisions from a versioned JSON file.
- Writes a standalone HTML report, machine-readable JSON, spreadsheet-ready CSV, iCalendar
  reminders, and a SHA-256 integrity manifest.
- Offers strict and policy exit codes so scheduled jobs can fail on skipped mail or overdue loops.

## Two-minute proof

```bash
git clone https://github.com/KanadeK/loopledger.git
cd loopledger
python -m pip install -e .

loopledger sample examples/demo.mbox --force
loopledger doctor examples/demo.mbox
loopledger scan examples/demo.mbox \
  --as-of 2026-02-01 \
  --output demo-output
loopledger verify demo-output/manifest.json
```

PowerShell uses the same commands; replace the `\` line continuations with backticks or put the
scan command on one line. The fictional mailbox deterministically reports:

```text
Scanned 9 messages in 6 threads: 3 overdue, 0 open, 0 snoozed.
verified: follow-ups.ics
verified: index.html
verified: report.csv
verified: report.json
```

Open `demo-output/index.html`, or inspect the public
[fictional report](https://kanadek.github.io/loopledger/). No sample row is a fixed UI response:
delete a reply, alter a date, change request wording, or tamper with an output and the analysis,
exit code, or manifest verification changes.

## Install

Python 3.11 or newer is required. The runtime has zero third-party dependencies.

From the tagged wheel:

```bash
python -m pip install \
  https://github.com/KanadeK/loopledger/releases/download/v0.1.0/loopledger-0.1.0-py3-none-any.whl
```

From a checkout:

```bash
python -m pip install .
```

For development and the complete release gate:

```bash
python -m pip install -e ".[dev]"
python scripts/verify.py
```

## Scan your own export

### Gmail Takeout MBOX

Export Mail with [Google Takeout](https://takeout.google.com/), extract the archive locally, then:

```bash
loopledger doctor "Takeout/Mail/All mail Including Spam and Trash.mbox"
loopledger scan "Takeout/Mail/All mail Including Spam and Trash.mbox" \
  --output follow-up-report
```

Gmail's `Sent` labels normally let LoopLedger infer your address. Pass every alias explicitly if
needed:

```bash
loopledger scan mailbox.mbox \
  --identity you@example.com \
  --identity your.alias@example.org \
  --output follow-up-report
```

### Maildir or EML

```bash
loopledger doctor path/to/Maildir --identity you@example.com
loopledger scan path/to/eml-directory --identity you@example.com --output follow-up-report
```

`doctor` is read-only. It reports usable message counts, inferred identities, source type, byte
size, full SHA-256, and any skipped messages before you generate a report.

## Output contract

| File | Real use |
| --- | --- |
| `index.html` | Standalone, responsive review report with escaped mailbox text and no JavaScript |
| `report.json` | Versioned evidence schema for scripts, audits, and downstream integrations |
| `report.csv` | One row per open loop for spreadsheets and task imports |
| `follow-ups.ics` | All-day follow-up reminders importable into common calendar clients |
| `manifest.json` | SHA-256 and byte count for every output plus source fingerprints |

Run `loopledger verify follow-up-report/manifest.json` after copying or archiving a report. It exits
`5` when a file is missing, altered, or unsafe to resolve.

Reports contain subjects, addresses, and short current-message excerpts. Keep them private even
though processing is local. See [docs/privacy.md](docs/privacy.md).

## How a loop is decided

For each rebuilt thread, LoopLedger:

1. removes automated messages from the conversational tail;
2. determines direction relative to your configured identities;
3. requires the last meaningful message to be outbound;
4. scores only its unquoted current text for questions, requests, decisions, deadlines, and
   follow-up wording;
5. waits for `--min-age` (default `3d`) and marks it overdue at `--overdue-after` (default `7d`);
6. applies ignore, resolve, or snooze state without mutating the mailbox.

The default request threshold is `3`. `--include-all-outbound` is an explicit recall-first mode
that includes every last-outbound thread and explains weak matches with
`last_message_is_outbound`. Full rules and limitations are in [docs/algorithm.md](docs/algorithm.md).

## Remember decisions without touching email

Copy stable IDs from `report.json` into a state file:

```json
{
  "version": 1,
  "ignored": ["loop-25ec08de8aa043cf"],
  "resolved": ["<quote-1@example.com>"],
  "snoozed_until": {
    "loop-e8459aa1bba30ab2": "2026-09-01T09:00:00Z"
  }
}
```

Then scan with `--state path/to/state.json`. A loop ID or its final outbound Message-ID can be
used, so decisions survive report regeneration as long as the source thread remains the same.

## Automation and exit codes

```bash
loopledger scan mailbox.mbox \
  --identity you@example.com \
  --strict \
  --fail-on-overdue \
  --output follow-up-report
```

| Exit | Meaning | Repair |
| ---: | --- | --- |
| `0` | Scan or verification succeeded | None |
| `2` | Bad input, identity, duration, or state | Run `doctor`; follow the printed repair text |
| `3` | `--strict` saw one or more skipped messages | Fix/export the named message, or rerun without strict mode knowingly |
| `4` | `--fail-on-overdue` found overdue loops | Reports were still written; review `index.html` |
| `5` | Manifest verification failed | Restore/regenerate the named output; do not trust the copied bundle |

The detailed, symptom-driven procedure is [docs/repair.md](docs/repair.md).

## Acceptance gate

The repository's local and CI acceptance command is:

```bash
python scripts/verify.py
```

It runs Ruff lint and format checks, strict MyPy, 83 unit/integration tests with a 90% branch
coverage floor, documentation and pinned-Action checks, wheel and sdist builds, Twine metadata
checks, a clean virtual-environment wheel smoke test, real sample analysis, manifest verification,
and a secret scan. The exact manual
acceptance matrix and expected failures are in [docs/acceptance.md](docs/acceptance.md).

Release assets are built with:

```bash
python scripts/package_release.py
```

This produces a wheel, source distribution, deterministic fictional-example ZIP, and
`SHA256SUMS` under `dist/`.

## Honest scope

LoopLedger is deliberately not an email client, CRM, AI reply writer, IMAP daemon, or Gmail
extension. It never logs in, labels a thread, sends a reminder, or decides that an external
promise was fulfilled. A human reply closes the current request even when the reply merely says
"I'll do it"; tracking promised deliverables is a different problem. Threading damaged exports
and interpreting indirect prose can also produce false positives or negatives—every result keeps
its evidence so you can review it.

The dated [research note](docs/research.md) records the GitHub and community gap analysis behind
this boundary and distinguishes it from adjacent tools instead of claiming that no similar idea
has ever existed.

## Project map

```text
src/loopledger/       parser, threader, signals, state, engine, reports, CLI
tests/                fictional unit, integration, CLI, and tamper tests
examples/             deterministic MBOX and state-file example
scripts/              release gate, package builder, secret scanner
docs/                 algorithm, privacy, research, repair, acceptance
.github/workflows/    cross-platform CI, CodeQL, Pages demo, tag gate
```

Contributions are welcome; start with [CONTRIBUTING.md](CONTRIBUTING.md). Please never post a real
mailbox or private report in an issue. LoopLedger is released under the [MIT License](LICENSE).
