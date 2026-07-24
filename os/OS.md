# OS.md — Agentic OS v2 Runtime Contract

This directory is Aayush's **action system** — his chief of staff across career, projects, ventures, and university (see `VISION.md` for the full functional spec). v2 built 2026-07-09 after v1 was razed for quality (commit 619d332). Plain markdown + stdlib Python + SQLite are canonical; everything under `.claude/` is a thin regenerable layer.

## Ground rules

1. **Self-sufficiency.** OS workflows read ONLY `os/`. The wiki is never queried at runtime. Knowledge enters via librarian ports only, allowlist = career/academic material; personal-life content (family, health, relationships, friendships, music) never enters `os/`.
2. **Nothing leaves without Aayush.** No skill or agent sends email, submits an application, or posts anywhere. Everything outbound terminates in `outbox/` with `status: needs-review`. Aayush approves and sends; the OS then records the send. LinkedIn is assisted-browsing in his own Chrome only — never scraping.
3. **Redaction gate.** Every outbox draft passes the redactor before it is marked ready: no family, health, finances, relationships, or vault-internal details.
4. **Quality over volume.** One excellent artifact beats five adequate ones (this is why v1 died). Claims in outbound text must be defensible from `knowledge/` — never overstated.
5. **Soft CPT flag.** Opportunities carry `cpt: ok | check | sponsor-needed`. Informational only — CPT internships need no sponsorship; the flag informs, Aayush decides. Nothing is auto-filtered.
6. **Prose is canonical; caches are disposable.** `memory/cache/os.sqlite` (FTS5) is derived — regenerate anytime with `python3 scripts/build_cache.py`. It is gitignored, never committed.
7. **Routing contract (manager / workers / verifier).** The main session is the *manager*: it plans, dispatches, and judges — it never writes outbound prose (writer, Opus) and never bulk-scans (scout, Sonnet; filing = librarian, Sonnet). Every outbound draft is attacked by the **critic** (Opus, read-only) before the redactor (Haiku) leak check: claims must trace to `knowledge/` or a record, voice must match `knowledge/voice.md`. On findings: ONE writer fix-loop, then re-attack; findings that survive ship in the draft header so Aayush reads the critique with the text. Both verdicts are stamped in draft frontmatter (`critic:` / `redactor:` — `PASS YYYY-MM-DD`); `oslib.py verify <file>` is the mechanical gate and `health` flags unstamped drafts (`GATE:`). Nothing below Sonnet except redaction.
8. **Commits.** One commit per logical operation, prefix `os:`. No auto-commit hooks.

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
│   └── prep/            # interview-prep tracks — created on first use
├── ventures/            # one venture record per file (+ _template.md)
├── projects/            # one project record per file (+ _template.md)
├── uni/                 # courses/ (one page per course) + deadlines.md
├── outbox/              # everything awaiting Aayush's approval
├── briefings/           # daily os-reflect output — YYYY-MM-DD.md, shown atop the dashboard
├── memory/              # episodic.md (append-only) · semantic.md (distilled)
│   └── cache/           #   · preferences.md (voice & working style) · os.sqlite
├── dashboard/           # python3 dashboard/serve.py → http://localhost:8877
└── scripts/             # oslib.py (parser/CRUD, single source of truth) · build_cache.py
```

## Dashboard design

`dashboard/PRODUCT.md` and `dashboard/DESIGN.md` (impeccable skill, init 2026-07-10; v3 rework same day) capture the strategic and visual spec for `dashboard/app/index.html`: solo daily-driver tool, register `product`, north star "One ink, quietly lit" — the Hermes-agent-derived system (teal void `#041c1c`, one cream ink `#ffe6cb`, Mondwest display + Courier Prime readouts, flat-not-boxed). Tabs come from `dashboard/areas.json`; fonts are bundled in `dashboard/app/fonts/`. Read both before any `/impeccable` pass on the dashboard.

The dashboard also writes back: record log notes and freeform "Tell the OS" updates are **auto-ingested** — `serve.py` spawns a headless `claude -p` run (Sonnet, acceptEdits, scoped to `os/`) that folds the new information into the records it touches, appends an `ingested` episodic line, and rebuilds the cache. Ingest runs never git-commit; the daily reflect commits. If the CLI is missing or the run fails, the entry stays in episodic as `ingest-pending` for the next reflect to fold manually. List display order is presentation state in `dashboard/order.json` (drag to reorder in the UI), never in the records themselves. The Today masthead carries a one-line outcome-stats strip fed by `oslib.stats()` (same numbers as the CLI view — the evaluation layer's readout).

## Memory ops

- **Episodic** (`memory/episodic.md`): append-only timestamped log — what was drafted, decided, sent, learned. Append via `oslib.py log`; nothing rewrites it.
- **Semantic** (`memory/semantic.md`): durable distilled facts. Updated by `/memory-consolidate` (weekly): read episodic entries since the watermark → merge into semantic → advance watermark. A fact whose canonical home is `knowledge/` or a record is folded THERE, not duplicated here.
- **Preferences** (`memory/preferences.md`): Aayush's standing corrections, voice notes, working style. The writer loads it before drafting anything.
- **Recall**: FTS5 over OS content (records, knowledge, memory, outbox — templates, briefings, and specs are excluded as noise): `python3 scripts/build_cache.py --search "query"`.

## Capabilities (`.claude/skills/`)

`resume-tailor` · `cold-outreach` · `posting-scan` · `venture-brief` · `project-scope` · `course-track` · `interview-prep` · `weekly-review` · `memory-consolidate` · `os-reflect`. Each loads this contract first, works only inside `os/`, terminates outbound work in `outbox/`, and appends to episodic memory.

**Session-end ritual (binds every skill).** Before finishing, answer two questions: *what am I uncertain about?* and *what would I add unrequested?* A material uncertainty becomes an `os/questions.md` line; an improvement idea becomes an episodic `idea` line for os-reflect to triage. Silence is valid when there is genuinely nothing — never manufacture entries.

`os-reflect` runs daily (scheduled ~6:20am via the desktop app's scheduled tasks; catches up on next launch if the app was closed) and writes the morning briefing to `briefings/` — self-improvement proposals, redundancies, applied hygiene. It sweeps via `oslib.py reflect` (one command; also flags outreach drafts stalled ≥5d) and ground-truth audits the headless ingest runs: the view's AUDIT section lists every `ingested`/`ingest-pending` episodic claim since the last briefing, each checked against the record it names (agents misreport their own state; claims are verified, not trusted). The briefing carries **Daily insights** — the day's 3-5 biggest AI/finance stories, combining `scripts/daily_insights.py` (last30days engine, all active sources over a 24h window — X-only until 2026-07-16, when four straight single-source days killed that; AI + finance/investing + prolific AI voices; fixed generic queries so no OS content enters a search) with the two Morning Brew newsletters read from Gmail (`crew@` general, `brewmarkets@` investing; website fallback) — plus a **From your inbox** sweep that folds academic/research email into records (librarian allowlist: never personal). Proposals wait for Aayush; only mechanical fixes are self-applied. Questions needing Aayush's decision are appended to `os/questions.md`; the dashboard surfaces them and records his answers.

## Agents (`.claude/agents/`)

`writer` (Opus — all prose in Aayush's voice) · `scout` (Sonnet — scanning, research, triage) · `librarian` (Sonnet — filing, ports, cache/board hygiene; the only role allowed to read the wiki, during ports) · `redactor` (Haiku, read-only — pre-send leak check).
