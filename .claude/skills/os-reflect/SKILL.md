---
name: os-reflect
description: Daily self-examination of the OS — improvement ideas, redundancies to eliminate, hygiene fixes — written as a morning briefing. Use for "reflect", "morning briefing", or the scheduled daily run.
---

Read `os/OS.md` and `os/VISION.md` first. Work only inside `os/`. This is the system looking at itself, once a day; the output is the briefing Aayush reads on the dashboard (localhost:8877) — it must answer "what needs me today?" in under two minutes of reading. Spec: `os/specs/2026-07-16-daily-reflection-product-spec.md`.

1. **Sweep — one command.** `python3 os/scripts/oslib.py reflect` emits the deterministic pre-read: WATERMARK (last briefing date), HEALTH (incl. STALLED draft outreach), NEEDS, DUE, EPISODIC since the watermark, AUDIT (the claims to verify), open QUESTIONS, STATS. Open a record only when a finding warrants judgment. Read the newest briefing in `os/briefings/`: don't repeat its unactioned proposals verbatim — escalate, drop, or stay silent; once a proposal has a `questions.md` qid, cite the qid. Triage episodic `idea` lines into proposals or silence.
2. **Trust — verify the AUDIT list.** Every `ingested` line: grep the record it names and confirm the fold actually happened (headless agents misreport their own state; verify, never trust). Every `ingest-pending` line: fold it now. Both are audit catches under Fixes applied.
3. **Hygiene — fix the mechanical, propose the rest.** Allowed without asking: cache rebuild (`python3 os/scripts/build_cache.py`), stale `updated:` corrections, dead cross-references, pruning briefings older than 14 days. Anything that changes behavior, structure, or meaning is a proposal. Decisions Aayush must make go to `os/questions.md` (`- [open] YYYY-MM-DD | id-slug | question`); `[answered]` lines are standing decisions — read them, never re-ask.
4. **Insights — two feeds.** (a) `python3 os/scripts/daily_insights.py` (~1-2 min; every active last30days source over a 24h window; fixed generic queries — no OS content enters a search). It pulls the day's X posts from the prolific AI voices and labs (Altman, Karpathy, LeCun, Hassabis, Ng, Jim Fan, Brockman, Musk, Paul Graham; @OpenAI @AnthropicAI @nvidia @xai) — the engine ranks these low, so dig for them; a quiet top-of-feed does not mean they were silent. On PULSE-UNAVAILABLE or X throttling, fall back to `os/memory/cache/daily-insights-latest.md`. (b) Morning Brew from Gmail: newest `from:crew@morningbrew.com` and `from:brewmarkets@morningbrew.com`; if Gmail fails, WebFetch https://www.morningbrew.com/. If both feeds fail, 1-2 WebSearches; if nothing credible surfaces, write "quiet day" — never fabricate or pad.
5. **Inbox — academic/research only.** Inbox since the watermark (`-category:promotions -category:social`; first run `newer_than:7d`). Surface concrete signal — deadlines, assignment instructions, research direction, advisor/lab email, meeting times — and fold durable facts into the records they touch (course pages, project records, `uni/deadlines.md`). Allowlist = the librarian's: academic/career/research only; NEVER personal (family, health, friends, money). Skip job-board mass mail (Handshake) unless it is a genuine target firm/role. Note folds under Fixes applied.
6. **Briefing — write `os/briefings/YYYY-MM-DD.md`** (frontmatter `type: briefing`, `title: Briefing — YYYY-MM-DD`, `updated:`). Target ≤450 words total — the 2-minute read. Sections in order, all honest, none padded:
   - **State of play** — ≤3 sentences: what moved, what's live today.
   - **Needs you today** — terse bullets; the dashboard shows detail.
   - **Daily insights** — 3-5 stories, ONE line each: what happened + why it matters, markdown-linked to the source, attributed (Morning Brew vs pulse). A sharp community quote may stand in for a headline.
   - **From your inbox** — terse, dated; omit the section entirely on a quiet day.
   - **Improvement proposals** — max 3, each concrete: what + one-line why + rough effort. Zero is valid; never pad.
   - **Redundancies / prune candidates** — what to eliminate and why it is safe.
   - **Fixes applied** — the hygiene, folds, and audit catches actually done this run.
7. **Trail.** `python3 os/scripts/oslib.py log filed "daily reflection YYYY-MM-DD — <n> proposals, <n> fixes"`, then one commit: `os: daily reflection YYYY-MM-DD`.

Quality bar (memory/preferences.md): one sharp observation beats five filler bullets. If the system is genuinely fine, say so in three lines and stop.
