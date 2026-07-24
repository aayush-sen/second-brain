---
name: memory-consolidate
description: Weekly memory maintenance — distill episodic events into durable semantic facts. Use for "consolidate memory" or as part of weekly-review.
---

Read `os/OS.md` first. Work only inside `os/memory/`.

1. Read `episodic.md` entries positioned below the last line whose timestamp matches the `consolidated-through:` watermark in `semantic.md` (file position, not timestamp comparison — the bootstrap-day entries are not in time order).
2. Distill: keep only what stays true and useful in a month (decisions, outcomes, learned preferences, relationship state changes). Drop routine state churn — the records already hold current state.
3. Merge into `semantic.md` under the right domain heading: dedupe, supersede stale facts (delete them — semantic memory is current truth, not history), date each fact. A fact whose canonical home is `knowledge/` or a record gets folded there instead — `semantic.md` never duplicates what another os/ file owns.
4. Standing corrections about how Aayush wants the system to work go to `memory/preferences.md` instead.
5. Advance the watermark. Never rewrite `episodic.md` — it is append-only. Append one episodic entry (`filed | consolidated through <ts>`).
