---
name: posting-scan
description: Scan for new internship/job postings — the daily discovery feed plus target-firm checks. Use for "any new roles", "check if X apps opened", or the scheduled daily scan.
---

Read `os/OS.md` first. Work only inside `os/`. Two halves: the **feed** (broad discovery, mechanical) and the **targets** (the pipeline records Aayush is actually working). The daily reflection runs this; he also triggers step 1 from the dashboard's Career page ("scan now").

## 1. Feed — mechanical, always first

```
python3 os/scripts/jobs.py scan
```

Pulls both community sources (config: `os/career/job-search.json`), filters to the configured term and role keywords, keeps every posting from a **followed company** regardless of role, scores each 0-100, and merges into `os/career/jobs.json`. Non-destructive: postings that vanish upstream are closed, not deleted, and anything Aayush saved or tracked keeps its status. A source that fails to fetch prints `SOURCE-FAILED` and closes nothing — report the failure, never paper over it.

## 2. Describe what's new — the part only you can do

```
python3 os/scripts/jobs.py list --new --needs-desc
```

Take the top **8-10 by score** (not all of them — quality over volume) and write one line each:

```
python3 os/scripts/jobs.py annotate <id> --desc "…" [--why "…"] [--score N]
```

A good `--desc`: what the firm actually does, what that role family touches, and one honest sentence of fit against `knowledge/identity.md` — including when the fit is *poor* ("low fit, listed because he follows the firm") or the bar looks wrong ("posted at master's level"). 25-40 words. If the posting URL is worth reading, WebFetch it; otherwise stay at firm level. **Never invent posting specifics** — no invented deadlines, comp, team names, or process details. "The board carries no date" is a fine thing to say.

Only pass `--score` when the mechanical score is visibly wrong; it stamps `scored_by: agent` and freezes that score against future scans. Scores are explainable by construction — read `score()` in `scripts/jobs.py` before overriding one.

## 3. Followed companies the lists missed

`python3 os/scripts/jobs.py following` shows each followed company's open count. For any showing **none open**, dispatch the **scout** to check that firm's own careers page — the community lists lag official postings by days, and "I want to know about everything they post" is the whole point of following. Found something? Say so in the report; if it's worth pursuing it belongs in the pipeline (step 4), not just the feed.

## 4. Targets — the pipeline records

1. Targets = `python3 os/scripts/oslib.py list pipeline --active`, plus any firm Aayush names.
2. Dispatch the **scout** to check each target's careers page / posting boards for the relevant role and season. Capture per posting: exact title, location, term, open/close dates, process shape, and any work-authorization language **verbatim**.
3. For each finding, update the opportunity record: timeline in body, dated `## Log` entry, `due:` set to the real close date, honest `cpt:` flag (informational only — never drop a firm because of it). Records created from the feed's "track" button start with no `due:` and no `cpt:` — filling those in is this step's job.
4. New firm worth tracking → new record from `_template.md`, `status: lead`. Nothing found → log that too (a quiet scan is information).

## 5. Trail

`python3 os/scripts/oslib.py log scanned "postings — <n> new in feed, <n> described, <what changed in pipeline>"`. Report to Aayush: what opened, what changed, what's approaching, and any source that failed.
