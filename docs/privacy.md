# Privacy and security boundary

## Data flow

LoopLedger is local and single-process:

```text
mail export -> memory -> chosen output directory
```

There is no telemetry, model call, OAuth flow, IMAP connection, remote image load, update check, or
automatic send. Runtime dependencies are empty.

## What is read

For each message, LoopLedger reads headers and the decoded plain-text body, or extracts text from an
HTML body when no plain part exists. It does not extract or execute attachments. Source files are
opened read-only; no labels, read states, or mailbox bytes are changed.

## What is written

The output contains recipient addresses, subjects, short unquoted excerpts, dates, reason codes,
stable IDs, and source hashes. These artifacts remain sensitive because local processing does not
make the content anonymous.

Recommended handling:

- write reports inside an encrypted user directory;
- do not publish a report generated from a real mailbox to GitHub Pages;
- do not sync report folders to a shared drive unless every recipient is authorized;
- delete local output using your normal secure-retention policy after follow-up work is complete;
- use the fictional `examples/demo.mbox` for bug reports and screenshots.

## HTML threat model

Mailbox-controlled values are escaped before insertion. The report has no JavaScript, forms,
iframes, external fonts, analytics, or remote images. It is still safest to open reports locally
and keep the browser updated.

## Integrity is not authenticity

`manifest.json` detects an accidental or malicious byte change after generation. Because the
manifest is not signed, an attacker who can replace both a report and its manifest can forge a new
consistent bundle. Use OS permissions, encrypted storage, or an external signature when provenance
against an active attacker matters.

## Responsible disclosure

Use the repository's private vulnerability-reporting channel described in [SECURITY.md](../SECURITY.md).
Never send a maintainer a real mailbox to demonstrate a parser issue.
