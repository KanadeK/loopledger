"""Final local release audit including Git identity and artifact integrity."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NAME = "KanadeK"
EXPECTED_EMAIL = "121669563+KanadeK@users.noreply.github.com"


def _run(command: list[str], *, capture: bool = False) -> str:
    print(f"[release-check] {' '.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
        encoding="utf-8",
    )
    return completed.stdout if capture else ""


def _version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _verify_checksums() -> None:
    lines = (ROOT / "dist" / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    if len(lines) != 3:
        raise RuntimeError("SHA256SUMS must contain exactly wheel, sdist, and examples ZIP")
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if not match:
            raise RuntimeError(f"malformed checksum line: {line!r}")
        expected, name = match.groups()
        path = ROOT / "dist" / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"checksum mismatch: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-dirty", action="store_true", help="development-only inspection")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    if not args.skip_verify:
        _run([sys.executable, "scripts/verify.py"])
    _run(["git", "diff", "--check"])
    tracked = _run(["git", "ls-files"], capture=True).splitlines()
    if not tracked:
        raise RuntimeError("repository has no tracked files")
    status = _run(["git", "status", "--porcelain"], capture=True)
    if status and not args.allow_dirty:
        raise RuntimeError(f"working tree is not clean:\n{status}")

    version = _version()
    init_text = (ROOT / "src" / "loopledger" / "__init__.py").read_text(encoding="utf-8")
    if f'__version__ = "{version}"' not in init_text:
        raise RuntimeError("pyproject and package versions differ")
    if f"## [{version}]" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        raise RuntimeError("CHANGELOG has no heading for the package version")

    history = _run(["git", "log", "--format=%an%x09%ae%x09%cn%x09%ce"], capture=True)
    if not history.strip():
        raise RuntimeError("repository has no commits")
    expected = f"{EXPECTED_NAME}\t{EXPECTED_EMAIL}\t{EXPECTED_NAME}\t{EXPECTED_EMAIL}"
    invalid = [line for line in history.splitlines() if line != expected]
    if invalid:
        raise RuntimeError(f"unexpected author or committer identity: {invalid}")
    bodies = _run(["git", "log", "--format=%B"], capture=True)
    if re.search(r"^Co-authored-by:", bodies, re.IGNORECASE | re.MULTILINE):
        raise RuntimeError("commit history contains Co-authored-by trailers")
    _run(["git", "shortlog", "-sne", "HEAD"])
    _verify_checksums()
    print(f"[release-check] PASS: version {version}, clean scope, authors, assets, checksums")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
