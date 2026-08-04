# Second Brain — an LLM-maintained wiki + agentic OS

A personal knowledge and action system built on Claude Code. One repo, two cooperating systems:

1. **The wiki** — a persistent, LLM-maintained personal wiki (Obsidian-compatible). I curate sources and ask questions; the agent does all writing, filing, cross-referencing, and bookkeeping.
2. **The Agentic OS** (`os/`) — a chief-of-staff layer that turns goals into finished work: career pipeline tracking, outreach drafting, project scoping, university deadlines, and a daily self-reflection loop — surfaced on a local dashboard, mirrored to a phone app, and kept running by cloud agents even when the laptop is off.

## How the wiki works

Three layers, three ownership rules (full schema in [CLAUDE.md](CLAUDE.md)):

- **`raw/` is immutable** — source documents (articles, papers, journal entries, transcripts). The agent reads, never modifies.
- **`wiki/` is the agent's** — generated pages with YAML frontmatter, dense prose, and liberal wikilinks. Sources get summary pages; entities, concepts, and projects get their own pages; an index and append-only log track everything.
- **`CLAUDE.md` is co-evolved** — the schema itself changes only by agreement.

Core operations: **ingest** (a new source fans out into 10–15 page updates), **query** (answers synthesized from the wiki, filed if they have lasting value), and **lint** (periodic health checks for contradictions, orphans, and gaps).

## How the OS works

`os/` is self-sufficient by design — OS workflows never read the wiki (a librarian agent ports allowlisted material one way, and personal-life content never crosses). Rules live in `os/OS.md`. Highlights:

- **Records over apps.** Plain markdown + stdlib Python + SQLite. Every opportunity, outreach thread, project, and venture is a file with typed frontmatter.
- **Nothing leaves without approval.** All outbound text (emails, applications) terminates in an outbox with `status: needs-review`. A critic agent attacks every draft's claims, then a redactor runs a leak check — both stamp the frontmatter before it's marked ready.
- **Manager / workers / verifier routing.** The main session plans and judges but never writes outbound prose (writer agent) or bulk-scans (scout agent). Filing belongs to the librarian.
- **Daily reflection.** A scheduled morning run audits yesterday's claims against the records they name, proposes improvements, applies mechanical fixes, and writes a briefing the dashboard serves.
- **A real dashboard.** `python3 os/dashboard/serve.py` → localhost:8877 — deadlines, pipeline, outreach queue, briefings, and open questions, all interactable.

## Off the laptop

The OS no longer needs the Mac open. Three pieces make that work, and none of them uses an API key — all agent compute runs on a Claude subscription:

```
 cloud agents (claude.ai cron) ──push──▶ private mirror repo
        6:20am briefing                       │  ▲
        Friday weekly review          pull ───┘  └── push   (git sync agent, 5 min)
                                              ▼
 phone (PWA) ◀── Vercel functions ◀── Supabase ◀── Mac: the vault + sync agents
     │                                 snapshot
     └── actions / notes / asks ──▶ queue ──▶ applied locally through the same
                                              code paths the desktop uses
```

- **Phone app.** A single-file mobile twin of the dashboard (same design system, Mondwest + Courier Prime on the dashboard teal), deployed on Vercel: Today (briefing + near deadlines), Todo, Notes with voice dictation, and Ask. A sync agent on the Mac pushes a redacted state snapshot to Supabase every two minutes; phone actions queue in Supabase and the same agent applies them via the exact oslib functions the desktop dashboard calls. Supabase runs RLS deny-all — the only way in is a bearer token, checked constant-time.
- **Cloud routines.** The morning briefing and Friday weekly review run as scheduled claude.ai cloud agents against a private mirror of `os/`. A pull-then-push git sync agent reconciles cloud commits with the vault every five minutes, so a briefing written in the cloud at 6:20am is on the phone before the laptop wakes up.
- **Ask pipeline.** Questions typed (or dictated) on the phone queue in Supabase; the Mac picks them up and answers with a headless `claude -p` run over the full vault, usually within a couple of minutes.

The wiki stays local by design — only the OS layer is mirrored, and the mirror carries no personal-life content.

## Repo layout (public subset)

```
├── CLAUDE.md              # wiki schema — how the wiki layer works
├── .claude/
│   ├── agents/            # critic, librarian, redactor, scout, writer
│   └── skills/            # cold-outreach, course-track, interview-prep,
│                          # memory-consolidate, os-reflect, posting-scan,
│                          # project-scope, resume-tailor, venture-brief, weekly-review
└── os/
    ├── OS.md              # the OS rulebook — ground rules, routing, memory design
    ├── dashboard/         # local dashboard (stdlib http.server + single-page app)
    ├── phone/             # mobile twin — static PWA + Vercel functions (no framework)
    └── scripts/           # oslib.py (CLI views), cache builder, daily insights,
                           # phone_sync.py (snapshot/actions/asks), cloud_sync.sh
                           # (two-way mirror to the private cloud repo)
```

## Why

We use AI in nearly every part of life and work and expect it to see the world through our brain — it can't. The problem I kept running into, like everyone else, was re-explaining context every time I came back to something. Projects help; they don't eliminate it. So when I saw Karpathy's LLM-knowledge-base tweet, I had to build it.

The wiki is a digital reconstruction of my brain, stored in the form that makes sense *to the LLM* — the agent does the filing, so it makes its own connections. I might remember a cafe because I went there with a friend; Claude might remember the same cafe because I did some project work there. Letting the agent build and own the graph pays off more than it first appears: I spend far less time prompting, and the work itself got better, because everything that matters — my working style, past projects, all the surrounding context — already lives in the wiki. Querying it also turns out to be much faster than making Claude dig through a chat from a week ago.
