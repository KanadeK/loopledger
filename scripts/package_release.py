"""Build deterministic release assets and SHA256SUMS."""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
SOURCE_DATE_EPOCH = "1767225600"
FIXED_EPOCH = int(SOURCE_DATE_EPOCH)


def _version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"[package] {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def _clean_known_assets(version: str) -> None:
    DIST.mkdir(exist_ok=True)
    names = {
        f"loopledger-{version}-examples.zip",
        f"loopledger-{version}-py3-none-any.whl",
        f"loopledger-{version}.tar.gz",
        "SHA256SUMS",
    }
    for name in names:
        path = DIST / name
        if path.is_file():
            path.unlink()


def _example_zip(version: str) -> Path:
    output = DIST / f"loopledger-{version}-examples.zip"
    files = [
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
        ROOT / "examples" / "README.md",
        ROOT / "examples" / "demo.mbox",
        ROOT / "examples" / "state.example.json",
        *(sorted((ROOT / "docs").glob("*.md"))),
    ]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files, key=lambda item: item.relative_to(ROOT).as_posix()):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    return output


def _normalize_wheel(path: Path) -> None:
    temporary = path.with_name(f".{path.name}.normalized")
    with zipfile.ZipFile(path, "r") as source:
        entries = [(info.filename, source.read(info.filename)) for info in source.infolist()]
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name, data in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, data, compresslevel=9)
    temporary.replace(path)


def _normalize_sdist(path: Path) -> None:
    temporary = path.with_name(f".{path.name}.normalized")
    entries: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(path, "r:gz") as source:
        for member in source.getmembers():
            file_handle = source.extractfile(member) if member.isfile() else None
            entries.append((copy.copy(member), file_handle.read() if file_handle else None))
    with (
        temporary.open("wb") as raw_output,
        gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw_output,
            mtime=FIXED_EPOCH,
        ) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        for member, data in sorted(entries, key=lambda item: item[0].name):
            member.mtime = FIXED_EPOCH
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.pax_headers = {}
            member.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
            archive.addfile(member, io.BytesIO(data) if data is not None else None)
    temporary.replace(path)


def _write_checksums(assets: list[Path]) -> Path:
    output = DIST / "SHA256SUMS"
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in sorted(assets)
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return output


def main() -> int:
    version = _version()
    _clean_known_assets(version)
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH
    _run([sys.executable, "-m", "build", "--no-isolation"], env=environment)
    wheel = DIST / f"loopledger-{version}-py3-none-any.whl"
    source = DIST / f"loopledger-{version}.tar.gz"
    if not wheel.is_file() or not source.is_file():
        raise RuntimeError("build did not create the expected wheel and source distribution")
    _normalize_wheel(wheel)
    _normalize_sdist(source)
    examples = _example_zip(version)
    checksums = _write_checksums([wheel, source, examples])
    for path in (wheel, source, examples, checksums):
        print(f"[package] wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
