# Failure and repair guide

Start with the read-only diagnostic:

```bash
loopledger doctor path/to/mailbox.mbox --identity you@example.com
```

It does not create a report or modify mail.

## `loopledger` command is not found

Confirm Python and reinstall the local package:

```bash
python --version
python -m pip install .
python -m loopledger --version
```

If `python -m loopledger` works but `loopledger` does not, the Python scripts directory is not on
`PATH`; continue with `python -m loopledger` or add that directory to `PATH`.

## Input does not exist or type is unsupported (exit 2)

1. Quote paths containing spaces.
2. Extract Takeout archives before scanning; do not pass the `.zip` itself.
3. Pass an `.mbox`/`.mbx`, one `.eml`, a Maildir containing `cur` and `new`, or a directory with
   `.eml` files.
4. Rerun `doctor`.

## Identity cannot be inferred (exit 2)

Only explicit Gmail `Sent` labels are trusted for inference. Other exports need:

```bash
loopledger doctor export.eml --identity you@example.com
```

Repeat `--identity` for aliases. If outgoing mail still appears unknown, inspect whether the export
preserved `From`, `To`, and `Cc` headers.

## Strict mode reports skipped messages (exit 3)

The warning names the source and message index/file. Typical causes are a missing or invalid `Date`
or `From` header.

1. Preserve the original export.
2. Re-export the named folder/message from the source client.
3. Run `doctor ... --strict` again.
4. If you knowingly accept partial evidence, remove `--strict`; the warnings remain in JSON/HTML.

Do not edit a real MBOX in place merely to silence a warning.

## Expected thread is absent

Run a recall-first comparison:

```bash
loopledger scan mailbox.mbox \
  --identity you@example.com \
  --include-all-outbound \
  --request-threshold 0 \
  --as-of 2026-08-08 \
  --output audit-report
```

Then check:

- is your final message at least `--min-age` old?
- did a later external message close the thread?
- did the current text contain the request only inside quoted history?
- is the sender in your identity list?
- was the message classified as automated?

Use `report.json` reason codes and summary counts. File a bug only with a fictional minimal fixture.

## Too many FYI messages

Raise `--request-threshold` from `3` to `4` or `5`, and do not use
`--include-all-outbound`. Add stable false positives to `ignored` in a version-1 state file rather
than deleting mail.

## Overdue policy exit (exit 4)

This is an intentional policy result, not a crash. Reports were written before the exit. Open
`index.html`, follow up, and then add the stable loop or Message-ID to `resolved`, `ignored`, or
`snoozed_until` as appropriate.

## Manifest verification fails (exit 5)

Do not trust the affected copied bundle.

1. Read the exact `missing`, `size mismatch`, or `SHA-256 mismatch` line.
2. If the original source and configuration are available, regenerate into a new empty directory.
3. Verify the new `manifest.json` before replacing the damaged bundle.
4. If only one copied output is missing, restore it from the same verified bundle; do not mix files
   from different scan times.

## Development gate fails

Install the locked tool range declared by the project and rerun the one failing stage:

```bash
python -m pip install -e ".[dev]"
ruff check src tests scripts
ruff format --check src tests scripts
mypy src
coverage run -m unittest discover -s tests
coverage report -m
python -m build --no-isolation
python -m twine check dist/*
```

Then rerun `python scripts/verify.py`. Do not bypass coverage, Twine, package smoke, or a failed
secret scan for a release.

## Release recovery

If CI, tag, or asset upload fails:

1. keep the failing tag/release evidence intact;
2. fix on `main` and rerun `python scripts/release_check.py`;
3. publish a new patch version instead of silently moving a public tag;
4. compare local and downloaded `SHA256SUMS`;
5. verify Actions, release assets, default-branch commit, authors, and contributors online before
   announcing completion.
