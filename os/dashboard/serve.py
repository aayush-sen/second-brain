#!/usr/bin/env python3
"""Agentic OS dashboard — stdlib only. Run: python3 serve.py → http://localhost:8877
All parsing/writes go through scripts/oslib.py; this file is just HTTP plumbing."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import oslib
from oslib import OS, COLLECTIONS, ENUMS

# ---- ingestion: log notes and freeform updates get folded into the records
# they touch by a headless claude run (Sonnet, per OS.md model policy).
# Fire-and-forget; on any failure the entry stays in episodic as
# ingest-pending so the next os-reflect folds it by hand. ----
CLAUDE = shutil.which("claude")
INGEST_RULES = (
    "Work only inside this directory (the OS). Read OS.md first and follow the record format. "
    "Fold the information into prose bodies (What it is / Why it matters / Next step / Blocked on) "
    "and frontmatter (status, due, priority, updated) where it clearly applies; flag contradictions "
    "rather than silently resolving them. Keep existing ## Log lines untouched. When done, run "
    "`python3 scripts/oslib.py log ingested \"<one line: what changed>\"` — never open episodic.md to "
    "append — then `python3 scripts/build_cache.py`. Do not git commit — the daily reflect commits.")


def spawn_ingest(prompt, origin):
    if not CLAUDE:
        oslib.episodic("ingest-pending", f"claude CLI not found — fold manually: {origin}")
        return

    def run():
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        try:
            p = subprocess.run(
                [CLAUDE, "-p", prompt, "--model", "sonnet", "--permission-mode", "acceptEdits",
                 "--allowedTools", "Read,Edit,Write,Grep,Glob,Bash(python3 scripts/build_cache.py:*),"
                                   "Bash(python3 scripts/oslib.py:*)"],
                cwd=str(OS), env=env, capture_output=True, timeout=600)
            if p.returncode:
                oslib.episodic("ingest-pending", f"ingest exited {p.returncode} — fold manually: {origin}")
        except Exception as e:
            oslib.episodic("ingest-pending", f"ingest failed ({e.__class__.__name__}) — fold manually: {origin}")

    threading.Thread(target=run, daemon=True).start()


def ingest_note(col, fname, line):
    d, _ = COLLECTIONS[col]
    spawn_ingest(
        f"Aayush just logged this note on {d}/{fname} via the dashboard (it is already appended to that "
        f"record's ## Log): «{line}». He uses log notes to feed the OS details it doesn't know yet — "
        f"update that record so its body and frontmatter reflect the note, and update any other record "
        f"the note clearly names. {INGEST_RULES}",
        f"note on {col}/{fname}: {line[:80]}")


def ingest_update(text):
    spawn_ingest(
        f"Aayush posted this freeform update on his dashboard (already recorded in memory/episodic.md): "
        f"«{text}». Find the records it touches — grep across the collections, or use "
        f"`python3 scripts/build_cache.py --search '<terms>'` — and update them. An update may also close "
        f"or add a line in uni/deadlines.md. If it maps to no record, the episodic entry is enough; do "
        f"nothing further. {INGEST_RULES}",
        f"update: {text[:80]}")


def state():
    # parse every record exactly once per request, then share the result
    cols = {name: oslib.records(name) for name in COLLECTIONS}
    dls = oslib.deadlines(cols)
    return {
        "collections": cols,
        "enums": ENUMS,
        "types": {name: COLLECTIONS[name][1] for name in COLLECTIONS},
        "deadlines": dls,
        "needs": oslib.needs_today(cols, dls),
        "feed": oslib.memory_feed(),
        "briefing": oslib.latest_briefing(),
        "areas": oslib.areas(),
        "questions": oslib.questions(),
        "stats": oslib.stats(cols),
    }


def search(q):
    db = OS / "memory" / "cache" / "os.sqlite"
    if not db.exists():
        subprocess.run([sys.executable, str(OS / "scripts" / "build_cache.py")])
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT path, section, snippet(chunks,2,'<b>','</b>','…',16) FROM chunks "
            "WHERE chunks MATCH ? ORDER BY rank LIMIT 10", (q,)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    return [{"path": p, "section": s, "snippet": sn} for p, s, sn in rows]


class H(BaseHTTPRequestHandler):
    def _send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._send((OS / "dashboard" / "app" / "index.html").read_bytes(), ctype="text/html")
        elif u.path == "/api/state":
            self._send(state())
        elif u.path == "/api/search":
            self._send(search(parse_qs(u.query).get("q", [""])[0]))
        elif u.path.startswith("/fonts/"):
            fonts = (OS / "dashboard" / "app" / "fonts").resolve()
            f = (fonts / u.path[len("/fonts/"):]).resolve()
            mime = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf"}.get(f.suffix)
            if f.is_file() and mime and f.is_relative_to(fonts):
                self._send(f.read_bytes(), ctype=mime)
            else:
                self._send({"err": "not found"}, 404)
        else:
            self._send({"err": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("body must be a JSON object")
        except ValueError:
            return self._send({"err": "bad request body"}, 400)
        if u.path == "/api/status":
            self._send({"ok": oslib.set_status(data.get("col", ""), data.get("file", ""), data.get("status", ""))})
        elif u.path == "/api/note":
            ok = oslib.add_note(data.get("col", ""), data.get("file", ""), data.get("line", ""))
            if ok:
                ingest_note(data["col"], data["file"], data["line"])
            self._send({"ok": ok})
        elif u.path == "/api/update":
            text = (data.get("text") or "").strip()
            if text:
                oslib.episodic("update", text)
                ingest_update(text)
            self._send({"ok": bool(text)})
        elif u.path == "/api/reorder":
            self._send({"ok": oslib.set_order(data.get("key", ""), data.get("ids", []))})
        elif u.path == "/api/deadline":
            self._send({"ok": oslib.set_deadline(data.get("date", ""), data.get("item", ""), data.get("status", ""))})
        elif u.path == "/api/log":
            oslib.episodic(data.get("type", "note"), data.get("line", ""))
            self._send({"ok": True})
        elif u.path == "/api/create":
            fname = oslib.create_record(data.get("col", ""), data.get("title", ""), data.get("area", ""),
                                        data.get("priority", "2"), data.get("due", ""), data.get("body", ""))
            self._send({"ok": bool(fname), "file": fname})
        elif u.path == "/api/area":
            self._send({"ok": oslib.add_area(data.get("id", ""), data.get("label", ""))})
        elif u.path == "/api/answer":
            self._send({"ok": oslib.answer_question(data.get("id", ""), data.get("answer", ""))})
        elif u.path == "/api/deadline_add":
            self._send({"ok": oslib.add_deadline(data.get("date", ""), data.get("domain", ""), data.get("item", ""))})
        else:
            self._send({"err": "not found"}, 404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    # single-threaded on purpose: it serializes record writes with no locking.
    # PORT env overrides for preview tooling; Aayush's default stays 8877.
    port = int(os.environ.get("PORT", "8877"))
    print(f"Agentic OS dashboard → http://localhost:{port}")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
