# OS.md — Agentic OS v2 Runtime Contract

This directory is Aayush's **action system** — his chief of staff and daily cockpit across career, projects, ventures, and university: the one-stop shop he views *and executes* from (see `VISION.md` for the full functional spec). Current balance, re-grounded 2026-07-28: research + academics + job applications; ventures deliberately background (never pushed unless asked). v2 built 2026-07-09 after v1 was razed for quality (commit 619d332). Plain markdown + stdlib Python + SQLite are canonical; everything under `.claude/` is a thin regenerable layer.

## Ground rules

1. **Self-sufficiency.** OS workflows read ONLY `os/`. The wiki is never queried at runtime. Knowledge enters via librarian ports only, allowlist = career/academic material; personal-life content (family, health, relationships, friendships, music) never enters `os/`. One standing exception (Aayush, 2026-07-28): the daily `/brain-lint` routine lints the wiki under librarian rules; its report (`memory/lint-latest.md`) names personal-life pages never — at most a count pointing at `wiki/log.md`.
2. **Nothing leaves without Aayush.** No skill or agent sends email, submits an application, or posts anywhere. Everything outbound terminates in `outbox/` with `status: needs-review`. Aayush approves and sends; the OS then records the send. LinkedIn is assisted-browsing in his own Chrome only — never scraping.
3. **Redaction gate.** Every outbox draft passes the redactor before it is marked ready: no family, health, finances, relationships, or vault-internal details.
4. **Quality over volume.** One excellent artifact beats five adequate ones (this is why v1 died). Claims in outbound text must be defensible from `knowledge/` — never overstated.
5. **Soft CPT flag.** Opportunities carry `cpt: ok | check | sponsor-needed`. Informational only — CPT internships need no sponsorship; the flag informs, Aayush decides. Nothing is auto-filtered.
6. **Prose is canonical; caches are disposable.** `memory/cache/os.sqlite` (FTS5) is derived — regenerate anytime with `python3 scripts/build_cache.py`. It is gitignored, never committed.
7. **Routing contract (manager / workers / verifier).** The main session is the *manager*: it plans, dispatches, and judges — it never writes outbound prose (writer, Opus) and never bulk-scans (scout, Sonnet; filing = librarian, Sonnet). Every outbound draft is attacked by the **critic** (Opus, read-only) before the redactor (Haiku) leak check: claims must trace to `knowledge/` or a record, voice must match `knowledge/voice.md`. On findings: ONE writer fix-loop, then re-attack; findings that survive ship in the draft header so Aayush reads the critique with the text. Both verdicts are stamped in draft frontmatter (`critic:` / `redactor:` — `PASS YYYY-MM-DD`); `oslib.py verify <file>` is the mechanical gate and `health` flags unstamped drafts (`GATE:`). Nothing below Sonnet except redaction.
8. **Commits.** One commit per logical operation, prefix `os:`. No auto-commit hooks.
9. **NEVER fabricate a source.** Hard rule, Aayush 2026-07-29, applies to all coursework and any citation-bearing artifact. Never invent, guess, or reconstruct-from-memory an author, title, journal, volume, issue, page range, DOI, or quotation. A citation is *unverified* until it has been fetched and its metadata confirmed against the source itself; unverified candidates are labeled as such or left as explicit `[NEED #n]` gaps, never dressed up as ready. For MMW specifically, **prefer publicly available / open-access sources** (open-access journals, Iowa Research Online, Whitman Archive, Project Gutenberg, HathiTrust, Internet Archive, public-domain primary texts) over paywalled ones even where UCSD proxy access exists, because MMW requires uploading highlighted PDF scans that match the bibliography exactly and everything runs through Turnitin with AIO referral. Also: walk Aayush through the reasoning before drafting prose, never hand him a draft he has not agreed to the logic of.

## The record format (the v2 rule that matters most)

**Every actionable item is one markdown file with YAML frontmatter.** One schema, one parser (`scripts/oslib.py`), every domain. No bespoke block formats.

```yaml
---
type: opportunity | outreach | venture | project | draft
title: Jane Street — Quantitative Trading Intern
status: lead            # enum depends on type, see below
priority: 1             # 1 highest, 3 lowest
due: 2026-08-31         # optional ISO date
cpt: ok                 # opportunity only
updated: 2026-07-09
---

Prose body: what it is, why it matters, current thinking. Dense, honest.

## Log
- 2026-07-09 — event, decision, or state change (append-only)
```

Status enums (`oslib.py` is the enforcement point):

| type | statuses |
|---|---|
| opportunity | `lead → researching → drafting → ready → applied → interviewing → offer \| closed` |
| outreach | `draft → ready → sent → replied → meeting \| dormant` |
| venture | `spark → brief → building → live \| killed` |
| project | `active \| paused \| shelved \| done` |
| draft (outbox) | `needs-review → approved → sent \| discarded` |
| course (uni) | `active \| done` |

Outbox drafts carry three extra frontmatter fields: `critic:` and `redactor:` (gate stamps, `PASS YYYY-MM-DD`, both required — see ground rule 7) and optional `template:` (which `knowledge/templates/` file was used, so template performance is measurable). `ready` means the package/draft sits in `outbox/` awaiting Aayush. Uni deadlines are the one exception to file-per-item: a table in `uni/deadlines.md` (`- YYYY-MM-DD | domain | item | open|in-progress|done`), because assignments churn too fast for files. The dashboard merges that table with every record's `due:` into one deadline view.

**Read views — sweep with one command, then open only the records that need judgment:**

```
python3 os/scripts/oslib.py list [collection] [--active]   # every record, one line each
python3 os/scripts/oslib.py due                            # merged deadline view (table + record due:)
python3 os/scripts/oslib.py needs                          # what genuinely needs Aayush today
python3 os/scripts/oslib.py reflect                        # one-shot daily pre-read (health+needs+due+episodic delta+audit list+questions+stats)
python3 os/scripts/oslib.py health                         # overdue/stale/cold/enum/outbox/gate findings
python3 os/scripts/oslib.py stats                          # outcomes: reply rate, pipeline funnel, outbox throughput
python3 os/scripts/oslib.py verify <file>                  # mechanical gate on an outbox draft (exit 1 on findings)
python3 os/scripts/oslib.py log <type> "<line>"            # append episodic — never edit the file to append
python3 os/scripts/canvas_sync.py status|request|refresh   # Canvas mirror state / queue refresh / bounded wait
```

**The job feed (the one thing that is not a record).** Discovery is a firehose — a few hundred live internship postings — and one markdown file per posting would drown `list`, `health`, and the FTS cache in noise. So `career/jobs.json` is a *feed*, not a collection: postings Aayush is shopping, refreshed daily by `scripts/jobs.py scan` from two public community sources, each scored 0-100 against `career/job-search.json` (term, role keywords, preferred cities, followed companies — edit that file to change what the search looks for). Records stay canonical for anything he *pursues*: the dashboard's "track" button promotes a posting into a real `career/pipeline/` opportunity and links back to it. Nothing is ever deleted — postings that close upstream are marked closed, and any posting he saved, hid, or tracked keeps that status forever.

```
python3 os/scripts/jobs.py scan                            # pull both sources, merge, rescore
python3 os/scripts/jobs.py list [--new] [--needs-desc]     # feed, one line per posting
python3 os/scripts/jobs.py annotate <id> --desc "…"        # the scout's write path (also --why/--score)
python3 os/scripts/jobs.py follow|unfollow <company>       # follow = surface every role they post, +20 score
```

## Layout

```
os/
├── VISION.md            # what the system should do (functional spec)
├── OS.md                # this contract
├── questions.md         # open questions for Aayush — one line each; dashboard surfaces & records answers
├── knowledge/           # ported self-contained context: identity.md, network.md,
│   └── templates/       #   voice.md, templates/ (cover-letter, cold-email)
├── career/
│   ├── pipeline/        # one opportunity record per file
│   ├── outreach/        # one relationship thread per file
│   ├── applications/    # per-firm artifact packages — created on first use
│   ├── prep/            # interview-prep tracks — created on first use
│   ├── jobs.json        # the discovery feed (see above) — scanned daily, not a collection
│   └── job-search.json  # what the scan looks for: term, role weights, cities, followed companies
├── ventures/            # one venture record per file (+ _template.md)
├── projects/            # one project record per file (+ _template.md)
├── uni/                 # courses/ (one page per course) + deadlines.md
│   ├── CANVAS.md        #   Canvas mirror ops manual (login flow, commands, trust rules)
│   ├── submissions/     #   gitignored Claude submission drafts, one file per course — he uploads
│   └── private/         #   gitignored local-only Canvas mirror: canvas.sqlite + sources/
├── integrations/
│   └── canvas-extension/ # unpacked Chrome MV3 bridge — reads canvas.ucsd.edu via the
│                        #   existing SSO session, posts credential-free snapshots to :8877
├── outbox/              # everything awaiting Aayush's approval
├── briefings/           # daily os-reflect output — YYYY-MM-DD.md, shown atop the dashboard
├── memory/              # episodic.md (append-only) · semantic.md (distilled)
│   └── cache/           #   · preferences.md (voice & working style) · os.sqlite
├── dashboard/           # python3 dashboard/serve.py → http://localhost:8877
└── scripts/             # oslib.py (parser/CRUD, single source of truth) · build_cache.py
                         #   · jobs.py (discovery feed) · daily_insights.py
```

## Dashboard design

`dashboard/PRODUCT.md` and `dashboard/DESIGN.md` (impeccable skill, init 2026-07-10; v3 rework same day) capture the strategic and visual spec for `dashboard/app/index.html`: solo daily-driver tool, register `product`, north star "One ink, quietly lit" — the Hermes-agent-derived system (teal void `#041c1c`, one cream ink `#ffe6cb`, Mondwest display + Courier Prime readouts, flat-not-boxed). Tabs come from `dashboard/areas.json`; fonts are bundled in `dashboard/app/fonts/`. Read both before any `/impeccable` pass on the dashboard.

**Career page** (reworked 2026-07-25, Simplify-shaped in the Hermes system): the pipeline board scrolls sideways with each status column scrolling its own stack, so the whole funnel stays reachable without cramming; below it the **Interview prep** strip (2026-07-28): `career/prep/plan.md` holds a weekly-block table (`- YYYY-MM-DD | block | focus | open|done`, base conditioning sized 30-60 min/day, mental math daily regardless) rendered as the current week + a daily time-slider check-in (1-120 min, `- YYYY-MM-DD | 45m` lines under `## Daily`, `log_prep_day()` replaces on re-log) with a current-month calendar whose fill brightens with minutes spent, streak + hours-logged counts, and a week-done button (`oslib.py prep_plan()`/`set_prep()`, `/api/prep`); firm-specific depth stays in `/interview-prep` tracks; below that the **Jobs for you** feed (searchable, filterable by following/new/saved, sortable by match or recency) renders each posting as match score + meter, company/role, term/location/posted date, and the scout's one-line description — the row itself opens the application page, `track` promotes it to a pipeline record, `save`/`✕` are his triage; below that, **Followed companies** as chips with live open counts that double as feed filters. `scan now` runs `jobs.py scan` synchronously.

**Academics page** (Canvas-powered, 2026-07-28): a mini-Canvas in the Hermes system — masthead connection truth (`connected | refreshing | partial | login_required | failed | never_synced | stale`, last attempt/success, `refresh now` / `open Canvas` / `log into Canvas`), a four-column hairline pulse (due next / overdue·missing / submitted recently / changed), a horizontal active-course strip, a unified assignment queue (course/status/horizon/search filters, exact due times with zone abbreviations, Canvas links), groups, and the merged deadline view (Canvas + manual, source-labeled, no duplicates — Canvas rows never get a local "mark done"). `#academics/course/<id>` opens a course workspace (work, announcements, modules, syllabus summary + immutable source downloads, groups without member emails). An assignment dialog carries instructions, dates, submission/grade/feedback facts, attachments, and a local note that syncs never touch. Claude actions (summaries, plans, course questions) run as background jobs over policy-filtered mirror context and render labeled `Claude guidance`, facts separated from recommendation. **Submission drafting** (2026-07-28, the page's headline execute-from-here feature): the assignment dialog's `draft submission` action writes the actual work product — drafted from the assignment's instructions in his voice (`knowledge/voice.md` + preferences in-prompt) — into `uni/submissions/<course>.md`, one `##` section per assignment, newest draft replacing the old. That directory is gitignored local-only, and the boundary is absolute: **Aayush is the only one who uploads anything to Canvas**; the bridge has no write path and never will unless he reverses it. Data comes from `scripts/canvas_store.py` (private SQLite mirror at `uni/private/`, stable-ID reconciliation, soft removal, change history) fed by the Chrome bridge (`integrations/canvas-extension/`); `scripts/canvas_sync.py` owns refresh requests and the one-per-transition login notification; ops manual at `uni/CANVAS.md`. Pure render logic lives in `dashboard/app/academics.js` (Node-testable), styles in `academics.css`.

The dashboard also writes back: record log notes and freeform "Tell the OS" updates are **auto-ingested** — `serve.py` spawns a headless `claude -p` run (Sonnet, acceptEdits, scoped to `os/`) that folds the new information into the records it touches, patches the current briefing when the update resolves or contradicts a line in it (2026-07-31, Aayush's ask), appends an `ingested` episodic line, and rebuilds the cache. Ingest runs are **live** (2026-07-28): each gets a job id the page polls (`/api/ingest?id=`), so the dashboard refreshes the moment the fold-in lands (~30-90s) instead of waiting for the next poll; concurrent runs are serialized server-side so typing more mid-run is safe. Ingest runs never git-commit; the daily reflect commits. If the CLI is missing or the run fails, the entry stays in episodic as `ingest-pending` for the next reflect to fold manually. List display order is presentation state in `dashboard/order.json` (drag to reorder in the UI), never in the records themselves. The Today masthead carries a one-line outcome-stats strip fed by `oslib.stats()` (same numbers as the CLI view — the evaluation layer's readout).

## Memory ops

- **Episodic** (`memory/episodic.md`): append-only timestamped log — what was drafted, decided, sent, learned. Append via `oslib.py log`; nothing rewrites it.
- **Semantic** (`memory/semantic.md`): durable distilled facts. Updated by `/memory-consolidate` (weekly): read episodic entries since the watermark → merge into semantic → advance watermark. A fact whose canonical home is `knowledge/` or a record is folded THERE, not duplicated here.
- **Preferences** (`memory/preferences.md`): Aayush's standing corrections, voice notes, working style. The writer loads it before drafting anything.
- **Recall**: FTS5 over OS content (records, knowledge, memory, outbox — templates, briefings, and specs are excluded as noise): `python3 scripts/build_cache.py --search "query"`.

## Capabilities (`.claude/skills/`)

`resume-tailor` · `cold-outreach` · `posting-scan` · `venture-brief` · `project-scope` · `course-track` · `interview-prep` · `weekly-review` · `memory-consolidate` · `os-reflect` · `brain-lint`. Each loads this contract first, works only inside `os/` (brain-lint alone also lints the wiki — ground rule 1's standing exception), terminates outbound work in `outbox/`, and appends to episodic memory.

**Session-end ritual (binds every skill).** Before finishing, answer two questions: *what am I uncertain about?* and *what would I add unrequested?* A material uncertainty becomes an `os/questions.md` line; an improvement idea becomes an episodic `idea` line for os-reflect to triage. Silence is valid when there is genuinely nothing — never manufacture entries.

`/brain-lint` runs daily (~5:45am, scheduled) and lints the whole second brain — OS and wiki both — fixing the mechanical and writing `memory/lint-latest.md` for the reflection to work off. `os-reflect` runs daily (scheduled ~6:20am via the desktop app's scheduled tasks; catches up on next launch if the app was closed) and writes the morning briefing to `briefings/` — self-improvement proposals, redundancies, and the **self-fix mandate** (2026-07-28): implementation-level repairs to scripts/skills/dashboard internals are applied without asking (limits: look+functions frozen, no record deletion, no `raw/`, no schema edits; noticeable behavior changes stay proposals), and the briefing's *Fixes applied* section is the OS's own self-maintenance receipt, never Aayush's fixes. The reflection also **gap-hunts**: what the OS doesn't know that would genuinely help becomes a `questions.md` line — no quota, zero is valid. It sweeps via `oslib.py reflect` (one command; also flags outreach drafts stalled ≥5d) and ground-truth audits the headless ingest runs: the view's AUDIT section lists every `ingested`/`ingest-pending` episodic claim since the last briefing, each checked against the record it names (agents misreport their own state; claims are verified, not trusted). The briefing carries **Daily insights** — the day's 3-5 biggest AI/finance stories, combining `scripts/daily_insights.py` (last30days engine, all active sources over a 24h window — X-only until 2026-07-16, when four straight single-source days killed that; AI + finance/investing + prolific AI voices; fixed generic queries so no OS content enters a search) with the two Morning Brew newsletters read from Gmail (`crew@` general, `brewmarkets@` investing; website fallback) — plus a **From your inbox** sweep that folds academic/research email into records (librarian allowlist: never personal). Proposals wait for Aayush; only mechanical fixes are self-applied. Questions needing Aayush's decision are appended to `os/questions.md`; the dashboard surfaces them and records his answers.

## Agents (`.claude/agents/`)

`writer` (Opus — all prose in Aayush's voice) · `scout` (Sonnet — scanning, research, triage) · `librarian` (Sonnet — filing, ports, cache/board hygiene; the only role allowed to read the wiki, during ports) · `redactor` (Haiku, read-only — pre-send leak check).
