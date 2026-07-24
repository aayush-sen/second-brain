---
name: posting-scan
description: Scan for new internship/job postings at target firms. Use for "any new roles", "check if X apps opened", or scheduled scans.
---

Read `os/OS.md` first. Work only inside `os/`.

1. Targets = `python3 os/scripts/oslib.py list pipeline --active`, plus any firm Aayush names.
2. Dispatch the **scout** to check each target's careers page / posting boards for the relevant role and season. Capture per posting: exact title, location, term, open/close dates, process shape, and any work-authorization language **verbatim**.
3. For each finding, update the opportunity record: timeline in body, dated `## Log` entry, `due:` set to the real close date, honest `cpt:` flag (informational only — never drop a firm because of it).
4. New firm worth tracking → new record from `_template.md`, `status: lead`. Nothing found → log that too (a quiet scan is information).
5. Append one episodic entry summarizing the scan. Report to Aayush: what opened, what changed, what's approaching.
