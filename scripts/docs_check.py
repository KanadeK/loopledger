"""Validate local documentation links, pinned Actions, and generated fixtures."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loopledger.sample import sample_mbox_bytes  # noqa: E402

LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
ACTION = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
PINNED_ACTION = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+){1,2}@v\d+\.\d+\.\d+$")


def _markdown_files() -> list[Path]:
    paths = [
        *ROOT.glob("*.md"),
        *(ROOT / "docs").glob("*.md"),
        *(ROOT / "examples").glob("*.md"),
        *(ROOT / ".github").glob("*.md"),
    ]
    return sorted(set(paths))


def _check_links() -> list[str]:
    errors: list[str] = []
    for document in _markdown_files():
        text = document.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            target = target.strip().strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative = unquote(target.split("#", maxsplit=1)[0])
            candidate = (document.parent / relative).resolve()
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                errors.append(f"{document.relative_to(ROOT)}: link escapes repository: {target}")
                continue
            if not candidate.exists():
                errors.append(f"{document.relative_to(ROOT)}: missing local link: {target}")
    return errors


def _check_actions() -> list[str]:
    errors: list[str] = []
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for action in ACTION.findall(text):
            if action.startswith("./") or PINNED_ACTION.fullmatch(action):
                continue
            errors.append(
                f"{workflow.relative_to(ROOT)}: action is not pinned to an exact version: {action}"
            )
    return errors


def _check_required_content() -> list[str]:
    errors: list[str] = []
    required = [
        "README.md",
        "README.zh-CN.md",
        "docs/acceptance.md",
        "docs/algorithm.md",
        "docs/privacy.md",
        "docs/repair.md",
        "docs/research.md",
        "examples/demo.mbox",
    ]
    errors.extend(
        f"missing required release file: {name}" for name in required if not (ROOT / name).is_file()
    )
    demo = ROOT / "examples" / "demo.mbox"
    if demo.is_file() and demo.read_bytes() != sample_mbox_bytes():
        errors.append(
            "examples/demo.mbox is stale; run loopledger sample examples/demo.mbox --force"
        )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    errors.extend(
        f"README is missing required acceptance/repair token: {token}"
        for token in (
            "python scripts/verify.py",
            "docs/repair.md",
            "--fail-on-overdue",
            "SHA256SUMS",
        )
        if token not in readme
    )
    return errors


def main() -> int:
    errors = [*_check_links(), *_check_actions(), *_check_required_content()]
    if errors:
        print("Documentation check failed:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1
    workflows = len(list((ROOT / ".github" / "workflows").glob("*.yml")))
    print(
        f"Documentation check passed: {len(_markdown_files())} Markdown files, "
        f"{workflows} workflows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
