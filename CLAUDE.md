# Second Brain — Wiki Schema

This vault is Aayush's second brain: a persistent, LLM-maintained wiki covering his personal life, student life (UCSD), professional life, and interests. You (the LLM agent) are the wiki's sole maintainer. Aayush curates sources, asks questions, and directs the analysis; you do all writing, filing, cross-referencing, and bookkeeping.

> [!important] The Agentic OS lives at `os/` — read `os/OS.md` for its rules (added 2026-07-09, approved plan).
> `os/` is the *action* system (career, ventures, university, memory, dashboard). It is self-sufficient: OS workflows read only `os/`, never this wiki. Wiki→os ports happen only via the librarian's allowlist (career/academic material; personal-life content never enters `os/`). Skills in `.claude/skills/`, agents in `.claude/agents/`, dashboard via `python3 os/dashboard/serve.py` → localhost:8877. OS commits use the `os:` prefix. The wiki's own rules below are unchanged.

## Architecture

```
second brain/
├── CLAUDE.md            # this schema — how the wiki works
├── raw/                 # IMMUTABLE source documents (articles, papers, journal entries, transcripts)
│   └── assets/          # images downloaded by Obsidian Web Clipper
└── wiki/                # LLM-generated pages — you own this layer entirely
    ├── index.md         # content catalog: every page, one line each, by category
    ├── log.md           # append-only chronological record of ingests/queries/lints
    ├── sources/         # one summary page per raw source
    ├── self/            # Aayush himself: goals, health, habits, psychology, values
    ├── people/          # friends, family, professors, mentors, colleagues
    ├── courses/         # UCSD coursework: one page per course, plus degree planning
    ├── projects/        # side projects, research, career efforts — anything with a goal and a timeline
    ├── concepts/        # ideas, topics, fields Aayush is learning or thinking about
    └── queries/         # filed answers: comparisons, analyses, syntheses worth keeping
```

Three layers, three ownership rules:

1. **`raw/` is immutable.** Read it, never modify or delete anything in it. It is the source of truth.
2. **`wiki/` is yours.** Create, update, restructure, and merge pages freely. If Aayush hand-edits a wiki page, treat his edit as authoritative — incorporate it, don't revert it.
3. **`CLAUDE.md` is co-evolved.** Propose schema changes when a convention isn't working; update it only with Aayush's agreement.

## Page conventions

- **Filenames**: Title Case for wiki pages (`Vannevar Bush.md`, `CSE 100.md`). Raw sources: `YYYY-MM-DD-kebab-title.md` (date = when added, or publication date if known).
- **Links**: Obsidian wikilinks — `[[Page Name]]`. Link liberally; the graph is a feature. A link to a page that doesn't exist yet is fine — it marks a page worth creating.
- **Every wiki page gets YAML frontmatter** (enables Dataview):

```yaml
---
type: source | self | person | course | project | concept | query
created: 2026-07-08
updated: 2026-07-08
tags: []
---
```

Source pages additionally carry `raw: "raw/<filename>"` and `source_type: article | paper | book | journal | podcast | video | note | transcript`. Keep `raw:` a bare path (comma-separated if several); size/tracking commentary goes in an optional `raw_note:`.

- **Dates are absolute.** Convert "last week" / "next quarter" to real dates at write time.
- **Contradictions are flagged, not silently resolved.** When a new source conflicts with an existing claim, keep both with dates and mark the conflict (`> [!warning] Conflict:`) until evidence settles it.
- **Cite sources.** Claims on entity/concept pages link back to the `[[source page]]` they came from.
- **Sensitive content stays local.** This vault contains personal information. Never send vault content to external services, web forms, or third-party APIs. Web search to *enrich* the wiki is fine; publishing from it is not.

## Operations

### Ingest — "process this" / new file appears in raw/

1. Read the raw source fully (for clipped articles with images: read text first, then view referenced images in `raw/assets/` as needed).
2. Briefly discuss key takeaways with Aayush — surface what's interesting or contradictory before filing.
3. Write a summary page in `wiki/sources/` — key points, notable quotes, your assessment, links to every wiki page it touches.
4. Update every affected wiki page: entity pages, concept pages, `self/` pages. Add cross-links both directions. Create new pages for entities/concepts that now warrant one. A single ingest touching 10–15 pages is normal.
5. Update `wiki/index.md` (add new pages, adjust one-liners if a page's scope changed).
6. Append an entry to `wiki/log.md`.
7. Report what changed: pages created, pages updated, conflicts found.

### Query — Aayush asks a question

1. Read `wiki/index.md` first to locate relevant pages; drill into them (grep across `wiki/` and `raw/` if the index isn't enough).
2. Synthesize an answer with `[[links]]` to the pages it draws on.
3. If the answer has lasting value (a comparison, an analysis, a discovered connection), offer to file it in `wiki/queries/` — filed answers get the full treatment: frontmatter, cross-links, index entry, log entry.

### Lint — periodic health check

Look for: contradictions between pages, claims superseded by newer sources, orphan pages (no inbound links), concepts mentioned ≥3 times without their own page, missing cross-references, stale `updated:` dates on active topics, and gaps worth a new source or web search. Report findings, fix what's mechanical, ask before restructuring. Log the pass.

## index.md format

One line per page, grouped by category, updated on every ingest:

```markdown
## Sources
- [[2026-07-08 LLM Wiki]] — the idea file this vault implements (2026-07-08, article)
```

## log.md format

Append-only. Consistent prefix so it's grep-able (`grep "^## \[" wiki/log.md | tail -5`):

```markdown
## [2026-07-08] ingest | LLM Wiki idea file
Created [[2026-07-08 LLM Wiki]]; new pages: [[LLM Wiki Pattern]], [[Memex]]. Bootstrapped vault.
```

Entry types: `ingest`, `query`, `lint`, `schema` (changes to this file), `note` (anything else worth recording).

## Git

The vault is its own git repo. Commit after every ingest, lint, or schema change — one commit per logical operation, message prefixed like the log (`ingest: LLM Wiki idea file`). Never commit anything outside this vault.

## Style

- Wiki pages are for future reading: prose over fragments, but dense — no filler, no restating the obvious.
- Summaries capture *what matters to Aayush*, not neutral abstracts. His reactions and disagreements from the ingest conversation belong on the page.
- When in doubt about where something goes, file it and note the uncertainty in the log — a misfiled page beats a lost thought.
