---
name: resume-tailor
description: Tailor Aayush's resume for a specific job/firm. Use when he says "tailor my resume for X" or an application package needs a resume variant.
---

Read `os/OS.md` and `os/memory/preferences.md` first. Work only inside `os/`.

1. Read the opportunity record in `os/career/pipeline/` (create one from `_template.md` if missing) and the posting details in its body or `## Log`. If the posting isn't captured yet, dispatch the **scout** to fetch and summarize it into the record.
2. Read `os/knowledge/identity.md` — the only permissible source of claims.
3. Produce `os/career/applications/<firm>/resume-deltas.md`: the specific reorderings, bullet rewrites, and emphasis changes for THIS role, each tied to a line in the posting. No invented experience; if the honest match is weak, say so at the top.
4. Have the **writer** draft any new bullets. Quality bar: every bullet defensible in an interview.
5. Run the **critic** on the deltas file (claims vs `identity.md` only — nothing a skeptical interviewer could puncture). On findings: ONE writer fix-loop, then re-attack; surviving findings stay noted at the top of the file.
6. Set the opportunity `status: drafting`, append to its `## Log`, append one episodic entry (`drafted | resume deltas for <firm>`).
7. Session-end ritual per OS.md: uncertainties → `questions.md`, ideas → episodic `idea` line.

Never submit anything. The finished package is reviewed by Aayush via the outbox/application flow.
