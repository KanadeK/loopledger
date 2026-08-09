# Research note: why LoopLedger exists

Research date: **2026-08-08**. Counts and product capabilities below are a dated snapshot, not a
permanent market claim.

## Selection constraints

The project had to satisfy all of these at once:

1. solve a recurring productivity problem with real local inputs and failure behavior;
2. avoid the existing workspace's developer-audit, data-workbench, README/release-checking,
   manual-to-maintenance, file-inbox, spreadsheet, game-tooling, and creative-tool projects;
3. occupy a narrower open-source gap instead of cloning a popular repository;
4. remain useful without mailbox credentials, a paid API, or a hosted backend;
5. support a credible first release with tests, packaging, CI, examples, and repair paths.

Three finalist directions were compared:

| Candidate | Demand | Competition/overlap | Decision |
| --- | --- | --- | --- |
| Work-resumption capsule for interrupted coding sessions | Real | Crowded by terminal/session/activity tools and overlaps the workspace's developer tooling | Rejected |
| Commitment extractor for notes and messages | Real | Many AI/cloud assistants; extraction workflow overlaps the existing evidence-linked ManualCare pattern | Rejected |
| Offline outgoing-email open-loop ledger | Repeated, durable | Commercial/client-specific products exist, but the export-first open-source boundary was sparse | Selected |

## Community evidence

Repeated public questions describe the same failure: a user sends an important message, receives
no reply, and forgets to follow up. Examples include:

- [Remembering to follow up on no-reply emails?](https://www.reddit.com/r/productivity/comments/vw3tem/)
- [Email client or Outlook plugin that reminds you if an email has not been replied to?](https://www.reddit.com/r/productivity/comments/11tv05a/)
- [Tool to track Email Followup?](https://www.reddit.com/r/productivity/comments/155bx6e/)
- [Best tool for snoozing and email follow-up reminders?](https://www.reddit.com/r/productivity/comments/1ss6dm2/)

The recurring objections are manual reminder setup, client lock-in, mailbox access, privacy, and
paying a recurring fee for one follow-up feature. These are exactly the constraints an offline
export analyzer can address.

## GitHub and adjacent-product check

Searches included `"waiting for reply" email`, `"unanswered sent" email`, `mbox follow up
tracker`, `gmail takeout follow up`, `email open loops`, and name candidates. The closest results
were inspected rather than dismissed by title:

| Project/product | Snapshot | Why it is adjacent rather than the same boundary |
| --- | --- | --- |
| [weekly-follow-up-reminder-n8n](https://github.com/speltonenn/weekly-follow-up-reminder-n8n) | 0 stars | Gmail OAuth plus n8n workflow; Gmail-only and no offline export/evidence bundle |
| [ReplyDebt](https://github.com/Freixanet/replydebt) | 0 stars | Messaging screenshots, Gemini API, Next.js/Tauri; not email threading or MBOX/EML |
| [Gmail-ReplyDebt-Automation](https://github.com/CSDennyS/Gmail-ReplyDebt-Automation) | 0 stars | Gmail Apps Script plus Gemini, and primarily finds mail where the user owes a response |
| [gmail-mbox-analyzer](https://github.com/chadaustin/gmail-mbox-analyzer) | 16 stars | Excellent MBOX storage-usage analyzer; no request/response open-loop detection |
| [Labnol awaiting-reply script](https://www.labnol.org/code/19696-emails-awaiting-reply) | Hosted article/script | Gmail Apps Script tied to a live account; no cross-client export, reports, state, or package |
| Gmail/Outlook extensions and SaaS products | Commercial or closed distribution | Validate demand, but require a mailbox integration, a specific client, or cloud processing |

The `LoopLedger` repository name returned no GitHub repository result, and
`KanadeK/loopledger` returned 404 before creation.

## Precise novelty claim

It is not possible to prove that nobody, anywhere, has ever written a similar script. The honest
claim is narrower: **in the dated searches above, no maintained open-source project was found that
combined offline MBOX/Maildir/EML input, outbound-request detection, RFC thread reconstruction,
explainable evidence, persistent review decisions, four useful report formats, and output
integrity verification without account access or a model API.**

That complete boundary—rather than the general idea of email follow-up—is LoopLedger's gap.

## Why it may earn attention

Stars cannot be guaranteed. The project is designed for discoverability and trust through:

- a universal, instantly understandable failure mode;
- no OAuth setup, server, database, JavaScript runtime, or paid model;
- a one-command fictional proof and a live static report;
- useful output even if the user deletes the tool afterward;
- transparent heuristics and limitations rather than hidden AI classification;
- English and Chinese documentation;
- package/release integrity, cross-platform CI, repair instructions, and privacy guidance.

Future research should repeat the searches before major scope expansion and treat new competitors
as design evidence, not as a reason to make unsupported uniqueness claims.
