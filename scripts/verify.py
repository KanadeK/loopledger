"""Run the complete local acceptance and package smoke gate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"[verify] {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _venv_python(root: Path) -> Path:
    windows = root / "Scripts" / "python.exe"
    return windows if windows.is_file() else root / "bin" / "python"


def _package_smoke() -> None:
    wheels = sorted((ROOT / "dist").glob("loopledger-*-py3-none-any.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one release wheel, found {len(wheels)}")
    with tempfile.TemporaryDirectory(prefix="loopledger-package-smoke-") as temp:
        temp_root = Path(temp)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        venv.create(temp_root / "venv", with_pip=True, clear=True)
        python = _venv_python(temp_root / "venv")
        mailbox = temp_root / "demo.mbox"
        output = temp_root / "report"
        _run([str(python), "-m", "pip", "install", "--no-deps", str(wheels[0])], env=environment)
        _run([str(python), "-m", "loopledger", "sample", str(mailbox)], env=environment)
        _run([str(python), "-m", "loopledger", "doctor", str(mailbox), "--strict"], env=environment)
        _run(
            [
                str(python),
                "-m",
                "loopledger",
                "scan",
                str(mailbox),
                "--as-of",
                "2026-02-01",
                "--output",
                str(output),
            ],
            env=environment,
        )
        _run(
            [str(python), "-m", "loopledger", "verify", str(output / "manifest.json")],
            env=environment,
        )
        payload = json.loads((output / "report.json").read_text(encoding="utf-8"))
        summary = payload["summary"]
        if summary["total_messages"] != 9 or summary["overdue_count"] != 3:
            raise RuntimeError(f"installed-package demo produced unexpected summary: {summary}")


def main() -> int:
    source_environment = os.environ.copy()
    existing_pythonpath = source_environment.get("PYTHONPATH")
    source_environment["PYTHONPATH"] = str(ROOT / "src") + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    _run([sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"])
    _run([sys.executable, "-m", "ruff", "format", "--check", "src", "tests", "scripts"])
    _run([sys.executable, "-m", "mypy", "src"])
    _run([sys.executable, "-m", "coverage", "erase"])
    _run(
        [sys.executable, "-m", "coverage", "run", "-m", "unittest", "discover", "-s", "tests"],
        env=source_environment,
    )
    _run([sys.executable, "-m", "coverage", "report", "-m"])
    _run([sys.executable, "-m", "coverage", "xml"])
    _run([sys.executable, "scripts/docs_check.py"])
    _run([sys.executable, "scripts/package_release.py"])
    distributions = sorted(
        path
        for path in (ROOT / "dist").iterdir()
        if path.suffix == ".whl" or path.name.endswith(".tar.gz")
    )
    _run([sys.executable, "-m", "twine", "check", *(str(path) for path in distributions)])
    _package_smoke()
    _run([sys.executable, "scripts/secret_scan.py"])
    print(
        "[verify] PASS: lint, format, types, tests, coverage, docs, packages, "
        "smoke, integrity, secrets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
