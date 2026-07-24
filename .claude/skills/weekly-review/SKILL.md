---
name: weekly-review
description: The Friday heartbeat — cross-domain digest and next-week setup. Use for "weekly review" or scheduled Friday runs.
---

Read `os/OS.md` first. Work only inside `os/`.

1. Sweep in three commands — `python3 os/scripts/oslib.py list`, `oslib.py due`, and `oslib.py stats` — plus the week's episodic entries. Open a record file only when the one-liner isn't enough to digest it.
2. Digest for Aayush, outcomes first (VISION.md: measured by what moved): applications advanced, threads warmed/cooled, deadlines hit/missed, projects progressed, what stalled and why. Lead with the stats deltas vs last week's digest (reply rate, pipeline funnel, outbox throughput) — trends, not just counts.
3. Hygiene pass: start from `python3 os/scripts/oslib.py health` (overdue, stale `updated:`, cold outreach threads, unreviewed outbox, enum drift, pipeline without timelines). Fix the mechanical, flag the judgment calls.
4. Propose next week: the 3–5 moves that matter most, each tied to a record.
5. Run `/memory-consolidate`. Rebuild the cache (`python3 os/scripts/build_cache.py`). Append one episodic entry. Commit (`os: weekly review YYYY-MM-DD`).
