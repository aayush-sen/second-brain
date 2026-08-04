#!/usr/bin/env python3
"""Assert-based checks for phone_sync action mapping. Run: python3 test_phone_sync.py"""

import phone_sync as ps

calls = []
ps.oslib.set_status = lambda c, f, s: calls.append(("status", c, f, s)) or True
ps.oslib.add_note = lambda c, f, l: calls.append(("note", c, f, l)) or True
ps.oslib.episodic = lambda t, l: calls.append(("log", t, l))
ps.oslib.set_deadline = lambda d, i, s: calls.append(("deadline", d, i, s)) or True
ps.oslib.add_deadline = lambda d, dm, i: (
    calls.append(("deadline_add", d, dm, i)) or True
)

assert ps.apply_action(
    "status", {"col": "pipeline", "file": "acme.md", "status": "applied"}
) == (True, None)
assert calls[-1] == ("status", "pipeline", "acme.md", "applied")

assert ps.apply_action("note", {"col": "projects", "file": "x.md", "line": "hi"}) == (
    True,
    None,
)
assert calls[-1] == ("note", "projects", "x.md", "hi")

assert ps.apply_action("log", {"line": "did a thing"}) == (True, None)
assert calls[-1] == ("log", "note", "did a thing")  # type defaults to "note"

n = len(calls)
assert ps.apply_action("log", {"line": "  "}) == (False, "empty line")
assert len(calls) == n  # no episodic call on empty

assert ps.apply_action(
    "deadline", {"date": "2026-08-10", "item": "PA3", "status": "done"}
) == (True, None)
assert calls[-1] == ("deadline", "2026-08-10", "PA3", "done")

assert ps.apply_action(
    "deadline_add", {"date": "2026-08-12", "domain": "uni", "item": "HW4"}
) == (True, None)
assert calls[-1] == ("deadline_add", "2026-08-12", "uni", "HW4")

assert ps.apply_action("nope", {}) == (False, "unknown kind nope")


def boom(*a):
    raise RuntimeError("disk on fire")


ps.oslib.set_status = boom
ok, err = ps.apply_action(
    "status", {"col": "pipeline", "file": "a.md", "status": "lead"}
)
assert ok is False and "disk on fire" in err


# ---- ask answering: run_claude always returns a non-empty string ----
class FakeResult:
    def __init__(self, out, err=""):
        self.stdout, self.stderr = out, err


ps.subprocess.run = lambda *a, **k: FakeResult("the answer")
assert ps.run_claude("q?") == "the answer"

ps.subprocess.run = lambda *a, **k: FakeResult("", "boom")
assert ps.run_claude("q?").startswith("(no answer — boom")


def raise_timeout(*a, **k):
    raise ps.subprocess.TimeoutExpired(cmd="claude", timeout=240)


ps.subprocess.run = raise_timeout
assert "timed out" in ps.run_claude("q?")

print("test_phone_sync: all assertions pass")
