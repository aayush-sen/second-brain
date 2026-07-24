---
name: course-track
description: University deadlines and weekly planning. Use for "what's due", "plan my week", or logging new assignments/dates.
---

Read `os/OS.md` first. Work only inside `os/`.

1. Deadlines live in `os/uni/deadlines.md` (`- YYYY-MM-DD | domain | item | status`); course context in `os/uni/courses/`. Dates are absolute, always.
2. "What's due" → `python3 os/scripts/oslib.py due` (the same merged view the dashboard shows, already date-ordered with days-remaining).
3. New assignments/dates from Aayush (or a synced calendar export he provides) → add table lines; new courses → a page in `uni/courses/`.
4. Weekly plan → lay the next 7 days against deadlines AND career items (application windows count as much as problem sets). Flag collisions early.
5. Mark items done as he reports them; append one episodic entry per session.
