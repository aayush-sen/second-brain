---
name: cold-outreach
description: Draft networking/cold emails in Aayush's voice. Use for "reach out to X", "cold email", "follow up with <person>", or warm-path building to target firms.
---

Read `os/OS.md` and `os/memory/preferences.md` first. Work only inside `os/`.

1. Find or create the thread record in `os/career/outreach/` (from `_template.md`). Check `os/knowledge/network.md` for the relationship's real history — never fabricate familiarity.
2. If the contact needs enrichment (role, recent work), dispatch the **scout** (web reads only, no LinkedIn scraping).
3. Dispatch the **writer** with the thread record, `knowledge/voice.md`, and `knowledge/templates/cold-email.md`. One excellent draft, not variants.
4. Run the **critic** on the draft (adversarial: claims vs `knowledge/`, voice, specificity). On findings: ONE writer fix-loop, then re-attack; findings that survive ship in the draft's **Critic findings:** header line.
5. Run the **redactor**. On FAIL, fix and re-run — the draft cannot proceed on a FAIL.
6. File the draft in `os/outbox/` per `_template.md` with both stamps in frontmatter (`critic:` / `redactor:` — `PASS YYYY-MM-DD`) and `template:` if one was used, then gate it: `python3 os/scripts/oslib.py verify <file>` must PASS. Set the thread record `status: ready`, log both, append one episodic entry.
7. Session-end ritual per OS.md: what am I uncertain about, what would I add unrequested — file material ones.

Aayush sends personally. When he reports it sent, set thread → `sent` and outbox → `sent`.
