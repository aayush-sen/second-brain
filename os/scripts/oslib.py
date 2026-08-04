#!/usr/bin/env python3
"""oslib — the single parser/CRUD layer for OS records (see OS.md 'record format').
Every domain uses the same YAML-frontmatter markdown file; the dashboard, cache
builder, and any script import THIS instead of re-parsing. Stdlib only."""
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

OS = Path(__file__).resolve().parent.parent

COLLECTIONS = {  # name -> (directory, record type)
    "pipeline": ("career/pipeline", "opportunity"),
    "outreach": ("career/outreach", "outreach"),
    "ventures": ("ventures", "venture"),
    "projects": ("projects", "project"),
    "outbox":   ("outbox", "draft"),
    "courses":  ("uni/courses", "course"),
}
ENUMS = {
    "opportunity": ["lead", "researching", "drafting", "ready", "applied", "interviewing", "offer", "closed"],
    "outreach":    ["draft", "ready", "sent", "replied", "meeting", "dormant"],
    "venture":     ["spark", "brief", "building", "live", "killed"],
    "project":     ["active", "paused", "shelved", "done"],
    "draft":       ["needs-review", "approved", "sent", "discarded"],
    "course":      ["active", "done"],
}
TERMINAL = {"closed", "done", "killed", "sent", "discarded", "dormant", "shelved"}


def parse(path: Path) -> dict:
    # frontmatter is flat scalars only (see OS.md); normalize CRLF so a
    # Windows-saved record doesn't silently lose all its metadata
    text = path.read_text().replace("\r\n", "\n")
    meta, body = {}, text
    m = re.match(r"(?s)^---\n(.*?)\n---\n?(.*)$", text)
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r"([\w-]+):\s*(.*)$", line)
            if kv:
                meta[kv.group(1)] = kv.group(2).strip().strip('"')
        body = m.group(2)
    meta.setdefault("title", path.stem)
    return {"file": path.name, "meta": meta, "body": body.strip()}


def records(name: str) -> list:
    d, typ = COLLECTIONS[name]
    out = []
    p = OS / d
    if p.exists():
        for f in sorted(p.glob("*.md")):
            if f.name.startswith("_"):
                continue
            try:
                r = parse(f)
            except (OSError, UnicodeDecodeError) as e:
                print(f"oslib: skipping unreadable {d}/{f.name}: {e}", file=sys.stderr)
                continue
            r["meta"].setdefault("type", typ)
            st = r["meta"].get("status")
            if st not in ENUMS[typ]:
                if st:  # keep the bad value visible instead of masking a typo
                    r["meta"]["status_invalid"] = st
                r["meta"]["status"] = ENUMS[typ][0]
            out.append(r)
    return apply_order(name, out, lambda r: r["file"])


# Presentation order for dashboard lists — dashboard/order.json, {key: [ids]}.
# Purely display state (prose stays canonical), so it lives beside the dashboard.
ORDER = OS / "dashboard" / "order.json"


_ORDER_CACHE = {"mtime": None, "data": {}}


def order_list(key: str) -> list:
    try:
        mt = ORDER.stat().st_mtime_ns
        if _ORDER_CACHE["mtime"] != mt:
            _ORDER_CACHE.update(mtime=mt, data=json.loads(ORDER.read_text()))
        return _ORDER_CACHE["data"].get(key, [])
    except (OSError, ValueError):
        return []


def set_order(key: str, ids: list) -> bool:
    if not re.fullmatch(r"[a-z0-9-]+", key or "") or not isinstance(ids, list) \
            or not all(isinstance(i, str) and len(i) < 200 for i in ids):
        return False
    try:
        data = json.loads(ORDER.read_text())
    except (OSError, ValueError):
        data = {}
    data[key] = ids
    ORDER.write_text(json.dumps(data, indent=1))
    _ORDER_CACHE["mtime"] = None
    return True


def apply_order(key: str, items: list, id_of) -> list:
    pos = {i: n for n, i in enumerate(order_list(key))}
    return sorted(items, key=lambda x: (pos.get(id_of(x), len(pos)), id_of(x)))


def record_path(name: str, fname: str):
    d, _ = COLLECTIONS[name]
    f = OS / d / fname
    ok = (f.is_file() and f.suffix == ".md" and "/" not in fname
          and not fname.startswith("_") and f.parent == OS / d)
    return f if ok else None


def set_status(name: str, fname: str, status: str) -> bool:
    _, typ = COLLECTIONS[name]
    f = record_path(name, fname)
    if not f or status not in ENUMS[typ]:
        return False
    t = f.read_text()
    t2, n = re.subn(r"(?m)^status:\s*\S+", f"status: {status}", t, count=1)
    if not n:
        return False
    t2 = re.sub(r"(?m)^updated:\s*\S+", f"updated: {date.today()}", t2, count=1)
    f.write_text(t2)
    append_log(f, f"status → {status} (dashboard)")
    episodic("decided", f"{name}/{fname} → {status}")
    return True


def append_log(f: Path, line: str):
    t = f.read_text()
    entry = f"- {date.today()} — {line}\n"
    if re.search(r"(?m)^## Log", t):
        t = t.rstrip("\n") + "\n" + entry
    else:
        t = t.rstrip("\n") + "\n\n## Log\n" + entry
    f.write_text(t)


def add_note(name: str, fname: str, line: str) -> bool:
    f = record_path(name, fname)
    if not f or not line.strip():
        return False
    append_log(f, line.strip())
    return True


def create_record(col: str, title: str, area="", priority="2", due="", body="") -> str:
    """New record file in a collection; returns filename or "" on failure."""
    if col not in COLLECTIONS or not title.strip():
        return ""
    d, typ = COLLECTIONS[col]
    p = OS / d
    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower())).strip("-")
    if not p.is_dir() or not slug:
        return ""
    fname, n = f"{slug}.md", 2
    while (p / fname).exists():
        fname, n = f"{slug}-{n}.md", n + 1
    meta = [f"type: {typ}", f"title: {title.strip()}", f"status: {ENUMS[typ][0]}", f"priority: {priority}"]
    if due:
        meta.append(f"due: {due}")
    if area:
        meta.append(f"area: {area}")
    meta.append(f"updated: {date.today()}")
    text = "---\n" + "\n".join(meta) + "\n---\n"
    if body.strip():
        text += "\n" + body.strip() + "\n"
    text += f"\n## Log\n- {date.today()} — created from dashboard\n"
    (p / fname).write_text(text)
    episodic("created", f"{col}/{fname}")
    return fname


def episodic(typ: str, line: str):
    # append mode: no read-modify-write, so concurrent appenders (server
    # thread + ingest threads) can't clobber each other
    with open(OS / "memory" / "episodic.md", "a", encoding="utf-8") as f:
        f.write(f"\n## [{datetime.now():%Y-%m-%d %H:%M}] {typ} | {line}\n")


def _episodic_entries() -> list:
    """Every episodic entry, chronological."""
    f = OS / "memory" / "episodic.md"
    if not f.exists():
        return []
    entries = re.findall(r"(?m)^## \[(.+?)\] ([\w-]+) \| (.+)$", f.read_text())
    return [{"ts": a, "type": b, "line": c} for a, b, c in entries]


def memory_feed(n=15) -> list:
    return _episodic_entries()[-n:][::-1]


DEFAULT_AREAS = [
    {"id": "career", "label": "Career", "collections": ["pipeline", "outreach"]},
    {"id": "research", "label": "Research", "collections": []},
    {"id": "academics", "label": "Academics", "collections": ["courses"]},
    {"id": "business", "label": "Business", "collections": ["ventures"]},
]


def areas() -> list:
    """Dashboard domain tabs; records attach via `area:` frontmatter."""
    f = OS / "dashboard" / "areas.json"
    return json.loads(f.read_text())["areas"] if f.exists() else DEFAULT_AREAS


def add_area(aid: str, label: str) -> bool:
    if not re.fullmatch(r"[a-z0-9-]+", aid or "") or not label.strip():
        return False
    cur = areas()
    if any(a["id"] == aid for a in cur):
        return False
    cur.append({"id": aid, "label": label.strip(), "collections": []})
    (OS / "dashboard" / "areas.json").write_text(json.dumps({"areas": cur}, indent=2) + "\n")
    return True


def set_area_hidden(aid: str, hidden: bool) -> bool:
    """Hide/show a dashboard area; the flag lives in areas.json so it
    survives refreshes and restarts. Records are untouched."""
    cur = areas()
    for area in cur:
        if area["id"] == aid:
            if hidden:
                area["hidden"] = True
            else:
                area.pop("hidden", None)
            (OS / "dashboard" / "areas.json").write_text(
                json.dumps({"areas": cur}, indent=2) + "\n"
            )
            return True
    return False


QUESTION_RE = re.compile(r"- \[(?:answered (\d{4}-\d{2}-\d{2})|open)\] (\d{4}-\d{2}-\d{2}) \| ([\w-]+) \| (.+)$")


def questions() -> list:
    """questions.md lines → dicts; answered/answer empty while open."""
    f = OS / "questions.md"
    out = []
    if not f.exists():
        return out
    for l in f.read_text().splitlines():
        m = QUESTION_RE.match(l)
        if not m:
            continue
        adate, asked, qid, rest = m.groups()
        text, _, ans = rest.partition(" → ") if adate else (rest, "", "")
        out.append({"id": qid, "text": text, "asked": asked,
                    "status": "answered" if adate else "open",
                    "answered": adate or "", "answer": ans})
    return apply_order("questions", out, lambda q: q["id"])


def answer_question(qid: str, answer: str) -> bool:
    f = OS / "questions.md"
    answer = answer.strip()
    if not f.exists() or not answer:
        return False
    lines = f.read_text().splitlines()
    for i, l in enumerate(lines):
        m = QUESTION_RE.match(l)
        if m and not m.group(1) and m.group(3) == qid:
            lines[i] = f"- [answered {date.today()}] {m.group(2)} | {qid} | {m.group(4)} → {answer}"
            f.write_text("\n".join(lines) + "\n")
            episodic("decided", f"answered {qid}: {answer}")
            return True
    return False


DEADLINE_RE = re.compile(r"- (\d{4}-\d{2}-\d{2}) \| (\S+) \| (.+?) \| ([\w-]+)\s*$")


def _deadline_tokens(value: str) -> tuple:
    return tuple(re.findall(r"[a-z0-9]+", value.lower()))


def _merge_canvas_deadlines(items: list) -> list:
    """Add the private Canvas view when present, collapsing display duplicates."""
    try:
        import canvas_store
        if not canvas_store.DB_PATH.exists():
            return items
        con = canvas_store.open_db(canvas_store.DB_PATH)
        try:
            canvas_items = canvas_store.canvas_deadlines(con)
        finally:
            con.close()
    except (OSError, ValueError, ImportError, sqlite3.Error):
        return items

    def duplicate(manual, canvas):
        return (
            manual["status"] != "done"
            and manual["date"] == canvas["date"]
            and _deadline_tokens(manual["item"]) == _deadline_tokens(canvas["item"])
            and _deadline_tokens(manual["domain"]) == _deadline_tokens(canvas["course"])
        )

    # OS consumers (health, needs, due, reflect, Today) speak open|in-progress|
    # done; a submitted/excused Canvas row is "done" in that vocabulary. The
    # Academics view reads the richer flags (complete/missing/graded) directly.
    for canvas in canvas_items:
        if canvas.get("complete"):
            canvas["status"] = "done"

    return [
        item for item in items
        if not any(duplicate(item, canvas) for canvas in canvas_items)
    ] + canvas_items


def deadlines(cols=None) -> list:
    """uni/deadlines.md table merged with every live record's due: date.
    Pass an already-parsed {name: records(name)} to avoid re-reading."""
    items = []
    f = OS / "uni" / "deadlines.md"
    if f.exists():
        for l in f.read_text().splitlines():
            m = DEADLINE_RE.match(l)
            if m:
                d0, dom, item, st = m.groups()
                items.append({"date": d0, "domain": dom, "item": item, "status": st,
                              "days": (date.fromisoformat(d0) - date.today()).days, "src": "uni"})
    if cols is None:
        cols = {name: records(name) for name in COLLECTIONS}
    for name in COLLECTIONS:
        for r in cols[name]:
            due, st = r["meta"].get("due"), r["meta"]["status"]
            if due and st not in TERMINAL:
                try:
                    days = (date.fromisoformat(due) - date.today()).days
                except ValueError:
                    continue
                items.append({"date": due, "domain": name, "item": r["meta"]["title"],
                              "status": st, "days": days, "src": f"{name}/{r['file']}"})
    items = _merge_canvas_deadlines(items)
    return sorted(items, key=lambda x: x["date"])


def set_deadline(date0: str, item: str, status: str) -> bool:
    if status not in ("open", "in-progress", "done"):
        return False
    f = OS / "uni" / "deadlines.md"
    if not f.exists():
        return False
    lines = f.read_text().splitlines()
    for i, l in enumerate(lines):
        m = DEADLINE_RE.match(l)
        if m and m.group(1) == date0 and m.group(3) == item:
            lines[i] = f"- {date0} | {m.group(2)} | {item} | {status}"
            f.write_text("\n".join(lines) + "\n")
            episodic("done" if status == "done" else "decided", f"deadline {date0} {item} → {status}")
            return True
    return False


def add_deadline(date0: str, domain: str, item: str) -> bool:
    try:
        date.fromisoformat(date0)
    except ValueError:
        return False
    item, domain = item.strip(), re.sub(r"\s+", "-", (domain or "").strip()) or "uni"
    if not item:
        return False
    f = OS / "uni" / "deadlines.md"
    try:
        f.write_text(f.read_text().rstrip("\n") + f"\n- {date0} | {domain} | {item} | open\n")
    except OSError:
        return False
    episodic("filed", f"deadline {date0} {domain} {item}")
    return True


PREP_RE = re.compile(r"- (\d{4}-\d{2}-\d{2}) \| (.+?) \| (.+?) \| (open|done)\s*$")
PREP_DAY_RE = re.compile(r"- (\d{4}-\d{2}-\d{2})(?: \| (\d+)m)?\s*$")  # date [| minutes]


def prep_plan() -> dict:
    """career/prep/plan.md — the weekly-block table plus the ## Daily check-in
    lines (`- YYYY-MM-DD | 45m`, written by the dashboard's slider+button).
    days maps date → minutes."""
    f = OS / "career" / "prep" / "plan.md"
    if not f.exists():
        return {"weeks": [], "days": {}}
    weeks, day_mins = [], {}
    for l in f.read_text().splitlines():
        m = PREP_RE.match(l)
        if m:
            w, block, focus, st = m.groups()
            days = (date.fromisoformat(w) - date.today()).days
            weeks.append({"week": w, "block": block, "focus": focus, "status": st,
                          "current": -7 < days <= 0})
            continue
        m = PREP_DAY_RE.match(l)
        if m:
            day_mins[m.group(1)] = int(m.group(2) or 30)
    return {"weeks": weeks, "days": day_mins}


def log_prep_day(day: str = "", minutes: int = 30) -> bool:
    """Record time spent on prep for today (or an ISO date). Re-logging a day
    replaces its minutes — the slider sets the day's total."""
    day = day if day and day != "today" else date.today().isoformat()
    try:
        date.fromisoformat(day)
        minutes = max(1, min(480, int(minutes)))
    except (ValueError, TypeError):
        return False
    f = OS / "career" / "prep" / "plan.md"
    if not f.exists():
        return False
    line = f"- {day} | {minutes}m"
    lines = f.read_text().rstrip("\n").splitlines()
    for i, l in enumerate(lines):
        m = PREP_DAY_RE.match(l)
        if m and m.group(1) == day:
            lines[i] = line
            break
    else:
        if not any(l.startswith("## Daily") for l in lines):
            lines += ["", "## Daily"]
        lines.append(line)
    f.write_text("\n".join(lines) + "\n")
    episodic("done", f"prep day {day} — {minutes}m")
    return True


def set_prep(week: str, status: str) -> bool:
    if status not in ("open", "done"):
        return False
    f = OS / "career" / "prep" / "plan.md"
    if not f.exists():
        return False
    lines = f.read_text().splitlines()
    for i, l in enumerate(lines):
        m = PREP_RE.match(l)
        if m and m.group(1) == week:
            lines[i] = f"- {week} | {m.group(2)} | {m.group(3)} | {status}"
            f.write_text("\n".join(lines) + "\n")
            episodic("done" if status == "done" else "decided", f"prep week {week} ({m.group(2)}) → {status}")
            return True
    return False


def latest_briefing():
    d = OS / "briefings"
    files = sorted(d.glob("????-??-??.md")) if d.exists() else []
    if not files:
        return None
    f = files[-1]
    r = parse(f)
    return {"date": f.stem, "body": r["body"], "today": f.stem == str(date.today())}


def blocked_line(body: str) -> str:
    m = re.search(r"\*\*Blocked on:\*\*\s*(.+)", body)
    return m.group(1).strip() if m else ""


def needs_today(cols=None, dls=None) -> list:
    """What genuinely needs Aayush: approvals, near deadlines, blocked work.
    Pass pre-parsed cols/deadlines to avoid re-reading every record."""
    if cols is None:
        cols = {name: records(name) for name in COLLECTIONS}
    if dls is None:
        dls = deadlines(cols)
    needs = []
    for r in cols["outbox"]:
        if r["meta"]["status"] == "needs-review":
            needs.append({"label": f"Approve: {r['meta']['title']}", "kind": "outbox", "target": r["file"]})
    for d in dls:
        if d["status"] not in ("done",) and d["days"] <= 3:
            needs.append({"label": f"Due {d['date']}: {d['item']}", "kind": "deadline",
                          "target": f"{d['date']}|{d['item']}", "src": d["src"]})
    for r in cols["projects"]:
        b = blocked_line(r["body"])
        if b and r["meta"]["status"] in ("active", "paused"):
            needs.append({"label": f"Unblock {r['meta']['title']}: {b}", "kind": "projects", "target": r["file"]})
    return needs


# ---- CLI: read views + episodic append, so agents get the whole picture
# from one command instead of reading every record file. ----

def _last_touch(r) -> str:
    """Most recent ## Log date, falling back to updated:."""
    dates = re.findall(r"(?m)^- (\d{4}-\d{2}-\d{2}) —", r["body"])
    return max(dates, default=r["meta"].get("updated", ""))


def _days_word(d: int) -> str:
    return "today" if d == 0 else (f"in {d}d" if d > 0 else f"{-d}d overdue")


def health(stale_days=14, cold_days=21, stall_days=5) -> list:
    """Mechanical hygiene findings across the whole OS (weekly-review step 3)."""
    cols = {name: records(name) for name in COLLECTIONS}
    lines = []
    for d in deadlines(cols):
        if d["status"] != "done" and d["days"] < 0:
            lines.append(f"OVERDUE {-d['days']}d: {d['date']} | {d['item']} ({d['src']})")
    for name, recs in cols.items():
        for r in recs:
            m = r["meta"]
            if "status_invalid" in m:
                lines.append(f'ENUM: {name}/{r["file"]} status "{m["status_invalid"]}" not in {m["type"]} enum')
            # cold check runs before the terminal skip: `sent` is terminal for
            # deadline purposes but is exactly the state a thread goes cold in
            if name == "outreach" and m["status"] in ("sent", "replied", "meeting"):
                try:
                    cold = (date.today() - date.fromisoformat(_last_touch(r))).days
                except ValueError:
                    cold = None
                if cold is not None and cold > cold_days:
                    lines.append(f"COLD {cold}d: outreach/{r['file']} last touch {_last_touch(r)} (status {m['status']})")
            # a drafted-but-never-sent thread stalls silently: the cold check
            # above never sees it (wrong statuses) and STALE waits 14 days
            if name == "outreach" and m["status"] in ("draft", "ready"):
                try:
                    stalled = (date.today() - date.fromisoformat(_last_touch(r))).days
                except ValueError:
                    stalled = None
                if stalled is not None and stalled >= stall_days:
                    lines.append(f"STALLED {stalled}d: outreach/{r['file']} (status {m['status']}) — drafted, not sent")
            if m["status"] in TERMINAL:
                continue
            try:
                age = (date.today() - date.fromisoformat(m.get("updated", ""))).days
            except ValueError:
                age = None
                lines.append(f"STALE: {name}/{r['file']} has no valid updated: date")
            if age is not None and age > stale_days:
                lines.append(f"STALE {age}d: {name}/{r['file']} (status {m['status']})")
            if name == "pipeline" and not m.get("due"):
                lines.append(f"NO-DUE: pipeline/{r['file']} (status {m['status']}) — no timeline captured")
    for r in cols["outbox"]:
        if r["meta"]["status"] == "needs-review":
            lines.append(f"OUTBOX: {r['file']} awaiting review (updated {r['meta'].get('updated', '?')})")
            for find in verify_draft(r["file"]):
                lines.append(f"GATE: outbox/{r['file']} — {find}")
    return lines


GATES = ("critic", "redactor")  # both must stamp PASS before a draft is review-ready


def verify_draft(fname: str) -> list:
    """Mechanical gate for outbox drafts — the script-decides step of the
    routing contract. Returns finding lines; empty list = pass."""
    f = record_path("outbox", fname)
    if not f:
        return [f"no such outbox record: {fname}"]
    r = parse(f)
    m = r["meta"]
    finds = []
    if m.get("status") not in ENUMS["draft"]:
        finds.append(f"status \"{m.get('status')}\" not in draft enum")
    for gate in GATES:
        v = m.get(gate, "")
        if not v.upper().startswith("PASS"):
            finds.append(f"{gate}: missing or not PASS ({v or 'absent'})")
    if not re.search(r"(?m)^\*\*Destination:\*\*", r["body"]):
        finds.append("no **Destination:** line — Aayush can't send without one")
    return finds


def stats(cols=None) -> dict:
    """Outcome metrics from record statuses — the evaluation layer.
    No new state: everything derives from what the funnel enums already encode."""
    if cols is None:
        cols = {name: records(name) for name in COLLECTIONS}
    oc = Counter(r["meta"]["status"] for r in cols["outreach"])
    contacted = oc["sent"] + oc["replied"] + oc["meeting"] + oc["dormant"]
    replied = oc["replied"] + oc["meeting"]
    pc = Counter(r["meta"]["status"] for r in cols["pipeline"])
    dc = Counter(r["meta"]["status"] for r in cols["outbox"])
    return {
        "outreach": {"threads": len(cols["outreach"]), "contacted": contacted,
                     "replied": replied, "meetings": oc["meeting"],
                     "reply_rate": round(100 * replied / contacted) if contacted else None},
        "pipeline": {"open": sum(v for k, v in pc.items() if k not in TERMINAL),
                     "applied": pc["applied"] + pc["interviewing"] + pc["offer"],
                     "interviewing": pc["interviewing"], "offers": pc["offer"]},
        "outbox": {"waiting": dc["needs-review"], "sent": dc["sent"], "discarded": dc["discarded"]},
    }


def _stats_lines(s: dict) -> list:
    o, p, d = s["outreach"], s["pipeline"], s["outbox"]
    rate = f"{o['reply_rate']}%" if o["reply_rate"] is not None else "n/a"
    return [f"outreach: {o['threads']} threads | {o['contacted']} contacted | "
            f"{o['replied']} replied ({rate}) | {o['meetings']} meetings",
            f"pipeline: {p['open']} open | {p['applied']} applied+ | "
            f"{p['interviewing']} interviewing | {p['offers']} offers",
            f"outbox:   {d['waiting']} waiting | {d['sent']} sent | {d['discarded']} discarded"]


def _canvas_lines() -> list:
    """Compact Canvas connection truth for the daily pre-read — never raw
    payloads, never credentials. Empty list when no private mirror exists."""
    try:
        import canvas_store
        if not canvas_store.DB_PATH.exists():
            return []
        con = canvas_store.open_db(canvas_store.DB_PATH)
    except Exception:
        return ["state: unreadable — private mirror could not be opened"]
    try:
        state = canvas_store.connection_state(con)
        latest = state.get("latest_run") or {}
        lines = [f"state: {state['state']}"]
        attempt = latest.get("finished_at") or latest.get("started_at")
        if attempt:
            lines.append(f"last attempt: {attempt}")
        if state.get("last_success"):
            lines.append(f"last success: {state['last_success']}")
        if state["state"] == "login_required":
            lines.append("warning: Log into Canvas again; "
                         "Pierce never needs your credentials.")
        elif state["state"] == "stale":
            lines.append("warning: no successful refresh in 36h — "
                         "showing the last good snapshot.")
        elif state["state"] == "failed":
            lines.append("warning: last refresh failed — "
                         f"{latest.get('error') or 'unknown error'}")
        elif state["state"] == "partial":
            lines.append("warning: last refresh was partial — "
                         "failed courses kept their previous data.")
        lines.append(f"changed: {latest.get('changed_count', 0)} "
                     "facts in the last run")
        for d in canvas_store.canvas_deadlines(con):
            if d["missing"] or d["overdue"] or d["due_soon"]:
                flag = ("missing" if d["missing"]
                        else "overdue" if d["overdue"] else "due soon")
                lines.append(f"- {flag}: {d['item']} ({d['course']}) "
                             f"due {d['due_at']}")
        return lines
    except Exception:
        return ["state: unreadable — private mirror could not be opened"]
    finally:
        con.close()


def reflect_view() -> str:
    """One-shot deterministic pre-read for the daily reflection (os-reflect
    step 1): everything checkable in one output, so the agent's judgment
    starts from a complete, unforgettable picture."""
    cols = {name: records(name) for name in COLLECTIONS}
    dls = deadlines(cols)
    lb = latest_briefing()
    wm = lb["date"] if lb else ""
    out = [f"WATERMARK: {wm or 'none — first run'}"]
    canvas = _canvas_lines()
    if canvas:  # before HEALTH so auth/staleness can't be skipped
        out += ["", "== CANVAS =="] + canvas
    out += ["", "== HEALTH =="]
    out += health() or ["healthy: no findings"]
    out += ["", "== NEEDS =="]
    out += [f"- {n['label']} [{n['kind']}]" for n in needs_today(cols, dls)] or ["none"]
    out += ["", "== DUE (overdue or next 7d) =="]
    near = [d for d in dls if d["status"] != "done" and d["days"] <= 7]
    out += [f"{d['date']} | {d['item']} | {d['status']} | {_days_word(d['days'])}"
            for d in near] or ["none"]
    eps = [e for e in _episodic_entries() if not wm or e["ts"][:10] >= wm]
    out += ["", f"== EPISODIC since {wm or 'ever'} =="]
    out += [f"[{e['ts']}] {e['type']} | {e['line']}" for e in eps] or ["none"]
    out += ["", "== AUDIT (verify each against the record it names) =="]
    out += [f"[{e['ts']}] {e['type']} | {e['line']}" for e in eps
            if e["type"] in ("ingested", "ingest-pending")] or ["none"]
    out += ["", "== QUESTIONS (open) =="]
    out += [f"- {q['id']} ({q['asked']}): {q['text']}"
            for q in questions() if q["status"] == "open"] or ["none"]
    out += ["", "== STATS =="] + _stats_lines(stats(cols))
    return "\n".join(out)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="oslib.py", description="OS record views (read-only) + episodic append.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="one line per record: col/file | status | pN | due | upd | title")
    p.add_argument("collection", nargs="?", choices=sorted(COLLECTIONS))
    p.add_argument("--active", action="store_true", help="hide terminal-status records")
    sub.add_parser("due", help="merged deadline view (uni table + record due:)")
    sub.add_parser("needs", help="what genuinely needs Aayush today")
    p = sub.add_parser("health", help="mechanical hygiene findings (overdue/stale/cold/stalled/enum/outbox)")
    p.add_argument("--stale-days", type=int, default=14)
    p.add_argument("--cold-days", type=int, default=21)
    p.add_argument("--stall-days", type=int, default=5)
    p = sub.add_parser("verify", help="mechanical gate on an outbox draft (critic/redactor stamps, schema)")
    p.add_argument("file", help="outbox record filename, e.g. jane-street-followup.md")
    sub.add_parser("stats", help="outcome metrics: outreach reply rate, pipeline funnel, outbox throughput")
    sub.add_parser("reflect", help="one-shot deterministic pre-read for the daily reflection")
    p = sub.add_parser("log", help='append one episodic entry: log <type> "<line>"')
    p.add_argument("type")
    p.add_argument("line")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for name in ([a.collection] if a.collection else COLLECTIONS):
            for r in records(name):
                m = r["meta"]
                if a.active and m["status"] in TERMINAL:
                    continue
                print(f"{name}/{r['file']} | {m['status']} | p{m.get('priority', '-')} | "
                      f"due:{m.get('due', '-')} | upd:{m.get('updated', '-')} | {m.get('title', '')}")
    elif a.cmd == "due":
        for d in deadlines():
            word = "done" if d["status"] == "done" else _days_word(d["days"])
            print(f"{d['date']} | {d['domain']} | {d['item']} | {d['status']} | {word} ({d['src']})")
    elif a.cmd == "needs":
        for n in needs_today():
            print(f"- {n['label']} [{n['kind']}]")
    elif a.cmd == "health":
        found = health(a.stale_days, a.cold_days, a.stall_days)
        print("\n".join(found) if found else "healthy: no findings")
    elif a.cmd == "verify":
        finds = verify_draft(a.file)
        if finds:
            print("\n".join(f"FAIL: {x}" for x in finds))
            sys.exit(1)
        print(f"PASS: outbox/{a.file} is review-ready")
    elif a.cmd == "stats":
        print("\n".join(_stats_lines(stats())))
    elif a.cmd == "reflect":
        print(reflect_view())
    elif a.cmd == "log":
        if not re.fullmatch(r"[a-z][a-z-]*", a.type) or not a.line.strip():
            ap.error("type must be a lowercase slug (e.g. filed, decided) and line non-empty")
        episodic(a.type, a.line.strip())
        print("logged")


if __name__ == "__main__":
    main()
