# Contributing

Thank you for helping make email follow-up safer and less dependent on cloud access.

## Development setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/verify.py
```

The full gate runs formatting checks, linting, strict type checks, 90%+ branch coverage, package
build checks, a clean-wheel smoke test, and a secret scan. It does not need mailbox credentials.

## Fixtures

- Use only fictional names, addresses, subjects, and message bodies.
- Keep dates fixed and pass `--as-of` in tests so results stay deterministic.
- Cover a failure path as well as the happy path.
- Never commit a Gmail Takeout archive, a real `.eml`, access token, or report generated from
  personal data.

## Pull requests

Explain the user-visible change, the reasoning behind any new classification rule, false-positive
and false-negative trade-offs, and the commands you ran. Keep behavior deterministic and offline.

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
