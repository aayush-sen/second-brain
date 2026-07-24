#!/usr/bin/env python3
"""Self-check for oslib's reflection helpers — stall detection + reflect view.
Stdlib only; builds a throwaway vault in tmp and asserts. Run:
    python3 os/scripts/test_oslib.py
"""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oslib


def make_vault(tmp: Path):
    for d in ("career/pipeline", "career/outreach", "ventures", "projects",
              "outbox", "uni/courses", "memory", "briefings"):
        (tmp / d).mkdir(parents=True)
    d6 = (date.today() - timedelta(days=6)).isoformat()
    (tmp / "career/outreach/stalled-thread.md").write_text(
        f"---\ntype: outreach\ntitle: Stalled Thread\nstatus: draft\n"
        f"priority: 1\nupdated: {d6}\n---\n\nBody.\n\n## Log\n- {d6} — drafted\n")
    d1 = (date.today() - timedelta(days=1)).isoformat()
    d3 = (date.today() - timedelta(days=3)).isoformat()
    (tmp / "briefings" / f"{d1}.md").write_text(
        f"---\ntype: briefing\ntitle: B\nupdated: {d1}\n---\n\nbody\n")
    (tmp / "memory" / "episodic.md").write_text(
        f"# Episodic\n\n"
        f"## [{d3} 09:00] ingested | pre-watermark fold\n\n"
        f"## [{d1} 12:00] ingested | folded X into projects/foo.md\n\n"
        f"## [{date.today().isoformat()} 08:00] ingest-pending | fold manually: bar\n")
    (tmp / "questions.md").write_text(
        "- [open] 2026-07-16 | test-q | Is this surfaced?\n")
    (tmp / "uni" / "deadlines.md").write_text(f"- {d1} | uni | Overdue thing | open\n")


def run():
    tmp = Path(tempfile.mkdtemp(prefix="oslib-test-"))
    make_vault(tmp)
    oslib.OS, real = tmp, oslib.OS
    try:
        h = oslib.health()
        assert any("STALLED 6d: outreach/stalled-thread.md" in l for l in h), h
        assert not any("COLD" in l for l in h), h  # stall is not the cold check

        r = oslib.reflect_view()
        d1 = (date.today() - timedelta(days=1)).isoformat()
        assert f"WATERMARK: {d1}" in r
        assert "folded X into projects/foo.md" in r
        assert "pre-watermark fold" not in r
        aud = r.split("== AUDIT")[1].split("== QUESTIONS")[0]
        assert "ingested | folded X" in aud, aud
        assert "ingest-pending | fold manually: bar" in aud, aud
        assert "test-q" in r
        assert "Overdue thing" in r
    finally:
        oslib.OS = real
    print("ok — all asserts passed")


if __name__ == "__main__":
    run()
