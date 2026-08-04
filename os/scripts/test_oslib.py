#!/usr/bin/env python3
"""Self-check for oslib's reflection helpers — stall detection + reflect view.
Stdlib only; builds a throwaway vault in tmp and asserts. Run:
    python3 os/scripts/test_oslib.py
"""
import sys
import tempfile
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canvas_store
import oslib


CANVAS_SNAPSHOT = {
    "schema_version": 1,
    "run_id": "run-1",
    "trigger": "manual",
    "started_at": "2026-07-27T10:00:00-04:00",
    "finished_at": "2026-07-27T10:01:00-04:00",
    "status": "success",
    "profile": {"id": "7", "time_zone": "America/New_York"},
    "scope_status": {
        "courses": "success",
        "course:101:assignments": "success",
        "course:101:objects": "success",
        "course:101:syllabus": "success",
    },
    "courses": [{
        "id": "101", "course_code": "MMW 15R", "name": "The Contemporary Era",
        "state": "active", "start_at": "2026-06-29T00:00:00Z",
        "end_at": "2026-08-01T00:00:00Z", "term": {"name": "Summer 2026"},
        "instructors": [{"id": "9", "name": "Professor Carreras"}],
        "html_url": "https://canvas.ucsd.edu/courses/101",
    }],
    "assignments": [{
        "id": "501", "course_id": "101", "name": "Annotated bibliography",
        "description": "<p>Submit an abstract.</p>",
        "html_url": "https://canvas.ucsd.edu/courses/101/assignments/501",
        "assignment_type": "assignment", "group_category_id": None,
        "unlock_at": None, "lock_at": None,
        "due_at": "2026-07-31T23:59:00-04:00", "due_tz": "America/New_York",
        "all_dates": [], "submission": {
            "workflow_state": "unsubmitted", "submitted_at": None,
            "missing": False, "excused": False, "score": None,
            "grade": None, "feedback": [],
        }, "attachments": [],
    }],
    "objects": [], "syllabi": [],
}


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


def test_canvas_deadline_merge_preserves_manual_file_and_cli_shape(tmp):
    deadline_file = tmp / "uni" / "deadlines.md"
    manual = "- 2026-07-31 | MMW-15R | Annotated bibliography | open\n"
    deadline_file.write_text(manual)
    db_path = tmp / "uni" / "private" / "canvas.sqlite"
    con = canvas_store.open_db(db_path)
    canvas_store.ingest_snapshot(CANVAS_SNAPSHOT, con)
    con.close()

    rows = oslib.deadlines({name: [] for name in oslib.COLLECTIONS})
    assert len(rows) == 1
    assert rows[0]["due_at"] == "2026-07-31T23:59:00-04:00"
    assert rows[0]["stable_id"] == "501"
    assert rows[0]["source"] == "canvas"
    assert deadline_file.read_text() == manual

    output = StringIO()
    with redirect_stdout(output):
        oslib.main(["due"])
    lines = output.getvalue().splitlines()
    assert len(lines) == 1
    assert len(lines[0].split(" | ")) == 5
    assert "Annotated bibliography" in lines[0]
    assert "(canvas/501)" in lines[0]


def test_reflect_view_surfaces_canvas_state(tmp):
    db_path = tmp / "uni" / "private" / "canvas.sqlite"
    if db_path.exists():
        db_path.unlink()
    now = datetime.now(timezone.utc)
    con = canvas_store.open_db(db_path)

    ok = deepcopy(CANVAS_SNAPSHOT)
    ok["started_at"] = (now - timedelta(hours=2)).isoformat(timespec="seconds")
    ok["finished_at"] = (now - timedelta(hours=2)).isoformat(timespec="seconds")
    ok["assignments"][0]["due_at"] = (
        (date.today() + timedelta(days=2)).isoformat() + "T23:59:00-04:00"
    )
    ok["assignments"].append({
        "id": "599", "course_id": "101", "name": "Excused past quiz",
        "description": "", "html_url": "https://canvas.ucsd.edu/x",
        "assignment_type": "quiz", "group_category_id": None,
        "unlock_at": None, "lock_at": None,
        "due_at": (date.today() - timedelta(days=9)).isoformat()
                  + "T10:00:00-04:00",
        "due_tz": "America/New_York", "all_dates": [], "attachments": [],
        "submission": {"workflow_state": "unsubmitted", "submitted_at": None,
                       "missing": False, "excused": True, "score": None,
                       "grade": None, "feedback": []},
    })
    assert canvas_store.ingest_snapshot(ok, con)["status"] == "success"

    r = oslib.reflect_view()
    assert "== CANVAS ==" in r
    # authentication/staleness cannot be buried below the fold
    assert r.index("== CANVAS ==") < r.index("== HEALTH ==")
    section = r.split("== CANVAS ==")[1].split("== HEALTH ==")[0]
    assert "state: connected" in section
    assert "last success:" in section
    assert "changed:" in section
    assert "Annotated bibliography" in section     # due-soon Canvas work
    # Canvas-complete (excused/submitted) work is done to the OS: never
    # overdue in HEALTH, never listed in DUE, never urgent in CANVAS
    assert "Excused past quiz" not in r
    # every pre-existing section survives
    for heading in ("== HEALTH ==", "== NEEDS ==", "== DUE",
                    "== EPISODIC", "== AUDIT", "== QUESTIONS", "== STATS =="):
        assert heading in r, heading

    expired = deepcopy(ok)
    expired["run_id"] = "run-login"
    expired["status"] = "login_required"
    expired["started_at"] = now.isoformat(timespec="seconds")
    expired["finished_at"] = now.isoformat(timespec="seconds")
    canvas_store.ingest_snapshot(expired, con)
    con.close()

    r2 = oslib.reflect_view()
    section = r2.split("== CANVAS ==")[1].split("== HEALTH ==")[0]
    assert "state: login_required" in section
    assert "last attempt:" in section
    assert "last success:" in section
    assert ("warning: Log into Canvas again; "
            "Pierce never needs your credentials.") in section
    db_path.unlink()


def test_unreadable_private_database_preserves_manual_deadlines(tmp):
    db_path = tmp / "uni" / "private" / "canvas.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"not a SQLite database")
    rows = oslib.deadlines({name: [] for name in oslib.COLLECTIONS})
    assert len(rows) == 1
    assert rows[0]["src"] == "uni"


def test_area_hiding_persists_and_roundtrips(tmp):
    (tmp / "dashboard").mkdir(exist_ok=True)
    assert oslib.add_area("athletics", "Athletics")
    assert oslib.set_area_hidden("athletics", True)
    assert [a["id"] for a in oslib.areas() if a.get("hidden")] == ["athletics"]
    # flag survives a fresh read (the persistence the nav relies on)
    assert oslib.set_area_hidden("athletics", False)
    assert not any(a.get("hidden") for a in oslib.areas())
    assert not oslib.set_area_hidden("missing", True)


def run():
    tmp = Path(tempfile.mkdtemp(prefix="oslib-test-"))
    make_vault(tmp)
    oslib.OS, real = tmp, oslib.OS
    canvas_store.DB_PATH, real_db = (
        tmp / "uni" / "private" / "canvas.sqlite",
        canvas_store.DB_PATH,
    )
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
        test_canvas_deadline_merge_preserves_manual_file_and_cli_shape(tmp)
        test_reflect_view_surfaces_canvas_state(tmp)
        test_unreadable_private_database_preserves_manual_deadlines(tmp)
        test_area_hiding_persists_and_roundtrips(tmp)
    finally:
        oslib.OS = real
        canvas_store.DB_PATH = real_db
    print("ok — all asserts passed")


if __name__ == "__main__":
    run()
