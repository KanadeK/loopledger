# Acceptance matrix

## One-command local release gate

```bash
python -m pip install -e ".[dev]"
python scripts/verify.py
```

The command must exit `0` and prove all of the following:

| Gate | Evidence |
| --- | --- |
| Syntax/style | Ruff lint and format check over `src`, `tests`, and `scripts` |
| Types | strict MyPy over the package |
| Behavior | 83 unit/integration/CLI tests |
| Coverage | at least 90% branch coverage |
| Documentation | local links, generated demo freshness, and exact Action version pins |
| Packaging | wheel and sdist built without isolation; Twine metadata passes |
| Installed behavior | fresh virtual environment installs only the wheel with `--no-deps` |
| Real data path | installed CLI generates MBOX, scans it, finds three overdue loops, and verifies outputs |
| Secrets | repository text scan finds no common token/private-key patterns |

## Manual happy path

```bash
loopledger sample examples/demo.mbox --force
loopledger doctor examples/demo.mbox --strict
loopledger scan examples/demo.mbox --as-of 2026-02-01 --output demo-output
loopledger verify demo-output/manifest.json
```

Expected: 9 messages, 6 threads, 3 overdue loops, no warnings, and four verified report files.

## Failure-path acceptance

### Overdue policy

```bash
loopledger scan examples/demo.mbox \
  --as-of 2026-02-01 \
  --fail-on-overdue \
  --output policy-output
```

Expected: exit `4`, with all five output files still present.

### Tamper detection

After a successful scan, change one byte in `report.csv`, then:

```bash
loopledger verify demo-output/manifest.json
```

Expected: exit `5` and a `size mismatch` or `SHA-256 mismatch` naming `report.csv`.

### Identity failure

Run `doctor` on an EML without Gmail Sent labels and omit `--identity`.

Expected: exit `2` and repair text showing `--identity you@example.com`.

### Strict parsing failure

Add a fictional `.eml` without a Date header next to a valid EML and run `doctor <dir> --strict`.

Expected: valid mail is counted, the damaged filename is printed, and exit is `3`.

## Release assets

```bash
python scripts/package_release.py
```

Expected under `dist/`:

- `loopledger-0.1.0-py3-none-any.whl`
- `loopledger-0.1.0.tar.gz`
- `loopledger-0.1.0-examples.zip`
- `SHA256SUMS`

Run the package command twice with a deliberately separated start time. Every SHA-256 must remain
identical; inspect ZIP entry timestamps and permissions if it does not.

## Online closure

A public release is complete only after:

- default branch points to the locally verified commit;
- CI, CodeQL, Pages, and tag release-gate workflows pass;
- tag and GitHub Release point to the same commit;
- all release assets download and match `SHA256SUMS`;
- Git author/committer, `git shortlog -sne HEAD`, public contributors, and absence of
  `Co-authored-by` are verified;
- the public Pages report loads and contains only fictional data;
- the release notification includes repository, release, demo, acceptance, and recovery links.
