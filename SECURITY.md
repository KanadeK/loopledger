# Security policy

## Supported versions

The latest tagged release receives security fixes. Version 0.1.x is currently supported.

## Data boundary

LoopLedger has no runtime dependencies and makes no network requests. It reads the mail paths
you provide and writes reports only to the output directory you choose. Reports can contain
subjects, addresses, and short message excerpts, so treat the output directory as sensitive.

The parser never opens attachments, executes HTML, loads remote images, or evaluates mailbox
content. The HTML report escapes all mailbox-controlled text and contains no JavaScript.

See [docs/privacy.md](docs/privacy.md) for the threat model and data-flow details.

## Reporting a vulnerability

Please use [GitHub private vulnerability reporting](https://github.com/KanadeK/loopledger/security/advisories/new).
Include a minimal fictional fixture, affected version, impact, and reproduction steps. Do not
attach a real mailbox or paste personal email content into a public issue.

You should receive an acknowledgement within seven days. Confirmed issues will be coordinated
privately until a fix and advisory are ready.
