"""Deterministic JSON, CSV, HTML, iCalendar, and integrity outputs."""

from __future__ import annotations

import csv
import hashlib
import html
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from loopledger.models import LoopItem, LoopStatus, ScanResult

_REASON_LABELS = {
    "question_mark": "question mark",
    "explicit_request": "explicit request",
    "decision_or_review": "decision or review",
    "question_form": "question wording",
    "deadline_language": "deadline language",
    "follow_up_language": "follow-up wording",
    "last_message_is_outbound": "last message is outbound",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _item_dict(item: LoopItem) -> dict[str, Any]:
    return {
        "loop_id": item.loop_id,
        "thread_id": item.thread_id,
        "message_id": item.message_id,
        "status": item.status.value,
        "subject": item.subject,
        "sent_at": _iso(item.sent_at),
        "due_at": _iso(item.due_at),
        "age_seconds": item.age_seconds,
        "recipients": list(item.recipients),
        "participants": list(item.participants),
        "request_score": item.request_score,
        "reasons": list(item.reasons),
        "snippet": item.snippet,
        "previous_external_reply_at": _iso(item.previous_external_reply_at),
        "snoozed_until": _iso(item.snoozed_until),
    }


def result_dict(result: ScanResult) -> dict[str, Any]:
    """Convert the result to the stable public JSON schema."""

    return {
        "schema_version": result.schema_version,
        "tool": {"name": "loopledger", "version": result.tool_version},
        "generated_at": _iso(result.generated_at),
        "configuration": {
            "identities": list(result.identities),
            "min_age_seconds": result.min_age_seconds,
            "overdue_after_seconds": result.overdue_after_seconds,
            "request_threshold": result.request_threshold,
            "include_all_outbound": result.include_all_outbound,
        },
        "sources": [asdict(source) for source in result.sources],
        "warnings": list(result.warnings),
        "summary": asdict(result.metrics),
        "open_loops": [_item_dict(item) for item in result.items],
    }


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _write_json(result: ScanResult, path: Path) -> None:
    path.write_bytes(_json_bytes(result_dict(result)))


def _write_csv(result: ScanResult, path: Path) -> None:
    fields = [
        "loop_id",
        "status",
        "subject",
        "sent_at",
        "due_at",
        "age_days",
        "recipients",
        "request_score",
        "reasons",
        "snippet",
        "message_id",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for item in result.items:
            writer.writerow(
                {
                    "loop_id": item.loop_id,
                    "status": item.status.value,
                    "subject": item.subject,
                    "sent_at": _iso(item.sent_at),
                    "due_at": _iso(item.due_at),
                    "age_days": f"{item.age_seconds / 86400:.2f}",
                    "recipients": ";".join(item.recipients),
                    "request_score": item.request_score,
                    "reasons": ";".join(item.reasons),
                    "snippet": item.snippet,
                    "message_id": item.message_id,
                }
            )


def _ical_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold_ical(value: str, limit: int = 73) -> list[str]:
    chunks: list[str] = []
    current = ""
    current_bytes = 0
    for character in value:
        width = len(character.encode("utf-8"))
        if current and current_bytes + width > limit:
            chunks.append(current)
            current = character
            current_bytes = width
        else:
            current += character
            current_bytes += width
    chunks.append(current)
    return [chunks[0], *(f" {chunk}" for chunk in chunks[1:])]


def _write_ics(result: ScanResult, path: Path) -> None:
    stamp = result.generated_at.strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LoopLedger//Open Loop Report 1.0//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:LoopLedger follow-ups",
    ]
    for item in result.items:
        event_date = (item.snoozed_until or item.due_at).date().strftime("%Y%m%d")
        reason = ", ".join(_REASON_LABELS.get(code, code) for code in item.reasons)
        description = (
            f"Waiting on: {', '.join(item.recipients) or 'external participant'}\n"
            f"Evidence: {reason}\nScore: {item.request_score}\nLoop ID: {item.loop_id}"
        )
        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{item.loop_id}@loopledger.local",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{event_date}",
            f"SUMMARY:{_ical_escape('Follow up: ' + item.subject)}",
            f"DESCRIPTION:{_ical_escape(description)}",
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "TRIGGER;VALUE=DURATION:-PT9H",
            f"DESCRIPTION:{_ical_escape('Follow up: ' + item.subject)}",
            "END:VALARM",
            "END:VEVENT",
        ]
        for line in event_lines:
            lines.extend(_fold_ical(line))
    lines.append("END:VCALENDAR")
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode())


def _status_card(label: str, value: int, tone: str) -> str:
    return (
        f'<div class="metric {tone}"><span>{html.escape(label)}</span>'
        f"<strong>{value}</strong></div>"
    )


def _item_html(item: LoopItem) -> str:
    reasons = "".join(
        f'<span class="reason">{html.escape(_REASON_LABELS.get(code, code))}</span>'
        for code in item.reasons
    )
    recipients = ", ".join(item.recipients) or "External participant"
    snooze = (
        f'<p class="snooze">Snoozed until {html.escape(_iso(item.snoozed_until) or "")}</p>'
        if item.status == LoopStatus.SNOOZED
        else ""
    )
    return f"""
    <article class="loop {item.status.value}">
      <div class="loop-top">
        <span class="status">{html.escape(item.status.value)}</span>
        <span class="age">{item.age_seconds / 86400:.1f} days waiting</span>
      </div>
      <h2>{html.escape(item.subject)}</h2>
      <p class="recipient">Waiting on <strong>{html.escape(recipients)}</strong></p>
      <blockquote>{html.escape(item.snippet or "No text snippet available")}</blockquote>
      <div class="reasons">{reasons}</div>
      <dl>
        <div><dt>Sent</dt><dd>{html.escape(_iso(item.sent_at) or "")}</dd></div>
        <div><dt>Follow-up date</dt><dd>{html.escape(_iso(item.due_at) or "")}</dd></div>
        <div><dt>Signal score</dt><dd>{item.request_score}</dd></div>
        <div><dt>Loop ID</dt><dd><code>{html.escape(item.loop_id)}</code></dd></div>
      </dl>
      {snooze}
    </article>"""


def _write_html(result: ScanResult, path: Path) -> None:
    items = "\n".join(_item_html(item) for item in result.items)
    if not items:
        items = '<section class="empty"><h2>No open loops found</h2><p>Try a lower request threshold or <code>--include-all-outbound</code> if you expected results.</p></section>'
    warnings = ""
    if result.warnings:
        warning_items = "".join(f"<li>{html.escape(item)}</li>" for item in result.warnings)
        warnings = (
            f'<aside class="warnings"><h2>Parse warnings</h2><ul>{warning_items}</ul></aside>'
        )
    sources = "".join(
        f"<li><strong>{html.escape(source.name)}</strong> · {html.escape(source.kind)} · "
        f"{source.size:,} bytes · <code>{html.escape(source.sha256[:16])}…</code></li>"
        for source in result.sources
    )
    metrics = result.metrics
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>LoopLedger · Open email loops</title>
  <style>
    :root {{ --ink:#17211d; --muted:#607069; --paper:#f4f1e9; --card:#fffdf8; --line:#d9d3c5; --accent:#075e54; --hot:#a73b24; --open:#b56a08; --quiet:#5d6670; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--ink); background:var(--paper); }}
    main {{ width:min(1080px,calc(100% - 32px)); margin:auto; padding:56px 0 80px; }}
    header {{ display:grid; grid-template-columns:1fr auto; gap:24px; align-items:end; border-bottom:2px solid var(--ink); padding-bottom:28px; }}
    .eyebrow {{ margin:0 0 8px; color:var(--accent); font-weight:800; letter-spacing:.12em; text-transform:uppercase; font-size:.78rem; }}
    h1 {{ margin:0; max-width:760px; font:700 clamp(2.4rem,7vw,5.8rem)/.92 ui-serif,Georgia,serif; letter-spacing:-.055em; }}
    .generated {{ color:var(--muted); text-align:right; }} .generated strong {{ display:block; color:var(--ink); }}
    .metrics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:22px 0 42px; }}
    .metric {{ min-height:112px; padding:18px; border:1px solid var(--line); background:var(--card); display:flex; flex-direction:column; justify-content:space-between; }}
    .metric span {{ color:var(--muted); font-weight:700; text-transform:uppercase; letter-spacing:.08em; font-size:.75rem; }} .metric strong {{ font-size:2.5rem; line-height:1; }}
    .metric.hot {{ border-top:5px solid var(--hot); }} .metric.open-tone {{ border-top:5px solid var(--open); }} .metric.quiet {{ border-top:5px solid var(--quiet); }}
    .lede {{ max-width:720px; color:var(--muted); margin:0 0 24px; }} .loop-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }}
    .loop {{ background:var(--card); border:1px solid var(--line); border-top:6px solid var(--open); padding:22px; min-width:0; }} .loop.overdue {{ border-top-color:var(--hot); }} .loop.snoozed {{ border-top-color:var(--quiet); opacity:.82; }}
    .loop-top {{ display:flex; justify-content:space-between; gap:12px; color:var(--muted); font-size:.82rem; }} .status {{ font-weight:850; text-transform:uppercase; letter-spacing:.1em; color:var(--hot); }}
    .loop.open .status {{ color:var(--open); }} .loop.snoozed .status {{ color:var(--quiet); }} h2 {{ margin:14px 0 4px; font-size:1.35rem; line-height:1.2; }}
    .recipient {{ margin:0 0 18px; color:var(--muted); overflow-wrap:anywhere; }} blockquote {{ margin:0 0 18px; padding:12px 14px; border-left:3px solid var(--line); background:color-mix(in srgb,var(--paper) 65%,transparent); }}
    .reasons {{ display:flex; flex-wrap:wrap; gap:6px; }} .reason {{ border:1px solid var(--line); border-radius:999px; padding:3px 9px; font-size:.75rem; color:var(--muted); }}
    dl {{ margin:20px 0 0; display:grid; gap:8px; }} dl div {{ display:grid; grid-template-columns:120px 1fr; gap:12px; }} dt {{ color:var(--muted); }} dd {{ margin:0; overflow-wrap:anywhere; }} code {{ font: .88em ui-monospace,SFMono-Regular,Consolas,monospace; }}
    .warnings,.provenance,.empty {{ margin-top:28px; padding:20px; border:1px solid var(--line); background:var(--card); }} .warnings {{ border-left:6px solid var(--hot); }} .provenance ul {{ padding-left:20px; }}
    footer {{ margin-top:40px; border-top:1px solid var(--line); padding-top:20px; color:var(--muted); }}
    @media (max-width:760px) {{ header {{ grid-template-columns:1fr; }} .generated {{ text-align:left; }} .metrics,.loop-grid {{ grid-template-columns:1fr; }} }}
    @media (prefers-color-scheme:dark) {{ :root {{ --ink:#ecf2ed; --muted:#a7b3ac; --paper:#111714; --card:#17201c; --line:#36423c; --accent:#78d8c5; --hot:#ff8b70; --open:#f2b35f; --quiet:#aab3bc; }} }}
  </style>
</head>
<body><main>
  <header><div><p class="eyebrow">Private, offline email follow-up</p><h1>Open loops, made visible.</h1></div><p class="generated">Report time<strong>{html.escape(_iso(result.generated_at) or "")}</strong></p></header>
  <section class="metrics">
    {_status_card("Overdue", metrics.overdue_count, "hot")}
    {_status_card("Open", metrics.open_count, "open-tone")}
    {_status_card("Snoozed", metrics.snoozed_count, "quiet")}
  </section>
  <p class="lede">LoopLedger rebuilt {metrics.total_threads} threads from {metrics.total_messages} messages. Every card below ends with one of your outbound requests and no later external reply.</p>
  <section class="loop-grid">{items}</section>
  {warnings}
  <section class="provenance"><h2>Source provenance</h2><ul>{sources}</ul><p>Full SHA-256 values and machine-readable evidence are in <code>report.json</code>; output hashes are in <code>manifest.json</code>.</p></section>
  <footer>Generated locally by LoopLedger {html.escape(result.tool_version)}. No mailbox data was uploaded.</footer>
</main></body></html>
"""
    path.write_text(document, encoding="utf-8", newline="\n")


def _hash_file(path: Path) -> dict[str, int | str]:
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def write_reports(result: ScanResult, output_dir: Path) -> tuple[Path, ...]:
    """Write every supported artifact plus a manifest that detects tampering."""

    output_dir.mkdir(parents=True, exist_ok=True)
    writers = {
        "report.json": _write_json,
        "report.csv": _write_csv,
        "index.html": _write_html,
        "follow-ups.ics": _write_ics,
    }
    written: list[Path] = []
    for name, writer in writers.items():
        path = output_dir / name
        writer(result, path)
        written.append(path)
    manifest = {
        "schema_version": 1,
        "tool": {"name": "loopledger", "version": result.tool_version},
        "generated_at": _iso(result.generated_at),
        "files": {path.name: _hash_file(path) for path in written},
        "sources": [asdict(source) for source in result.sources],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(_json_bytes(manifest))
    written.append(manifest_path)
    return tuple(written)


def verify_manifest(path: Path) -> tuple[bool, tuple[str, ...]]:
    """Verify output byte counts and SHA-256 values without trusting report content."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return False, (f"cannot read manifest: {exc}",)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return False, ("manifest schema_version must be 1",)
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        return False, ("manifest files must be a non-empty object",)
    messages: list[str] = []
    valid = True
    for name, expected in sorted(files.items()):
        if not isinstance(name, str) or Path(name).name != name or not isinstance(expected, dict):
            valid = False
            messages.append(f"unsafe or malformed manifest entry: {name!r}")
            continue
        candidate = path.parent / name
        if not candidate.is_file():
            valid = False
            messages.append(f"missing: {name}")
            continue
        actual = _hash_file(candidate)
        if actual.get("bytes") != expected.get("bytes"):
            valid = False
            messages.append(f"size mismatch: {name}")
        elif actual.get("sha256") != expected.get("sha256"):
            valid = False
            messages.append(f"SHA-256 mismatch: {name}")
        else:
            messages.append(f"verified: {name}")
    return valid, tuple(messages)
