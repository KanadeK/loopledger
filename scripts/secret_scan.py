"""Small dependency-free release scan for accidentally committed credentials."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "demo-output",
}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".cff",
    ".csv",
    ".eml",
    ".html",
    ".ics",
    ".ini",
    ".json",
    ".md",
    ".mbox",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "generic secret key": re.compile(r"\bsk-[A-Za-z0-9]{24,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def _candidate_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode == 0 and completed.stdout:
        return [ROOT / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & SKIP_PARTS)
    ]


def main() -> int:
    findings: list[str] = []
    scanned = 0
    for path in sorted(_candidate_files()):
        relative = path.relative_to(ROOT)
        if relative.as_posix() == "scripts/secret_scan.py":
            continue
        if path.suffix.casefold() not in TEXT_SUFFIXES or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{relative}:{line_number}: possible {label}")
    if findings:
        print("Secret scan failed:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print(f"Secret scan passed: {scanned} text files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
