#!/usr/bin/env python3
"""Build (or query) the disposable FTS5 cache over all of os/ (OS.md rule 6).
  python3 build_cache.py                    rebuild memory/cache/os.sqlite
  python3 build_cache.py --search "query"   FTS5 search from the CLI"""
import re
import sqlite3
import sys
from pathlib import Path

OS = Path(__file__).resolve().parent.parent
DB = OS / "memory" / "cache" / "os.sqlite"
# Recall content only: templates (_*.md), briefings (stale-by-design archive),
# dashboard specs, and the contract/vision/questions files are read directly
# when needed and would only pollute search hits.
INDEX_DIRS = ("career", "ventures", "projects", "uni", "knowledge", "memory", "outbox")


def build():
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute("CREATE VIRTUAL TABLE chunks USING fts5(path, section, text)")
    n = 0
    files = sorted(f for d in INDEX_DIRS for f in (OS / d).rglob("*.md")
                   if not f.name.startswith("_"))
    for f in files:
        rel = str(f.relative_to(OS))
        parts = re.split(r"(?m)^(#{1,3} .+)$", f.read_text())
        rows = [(rel, "(top)", parts[0])]
        for i in range(1, len(parts), 2):
            rows.append((rel, parts[i].lstrip("# ").strip(), parts[i + 1] if i + 1 < len(parts) else ""))
        for r in rows:
            if r[2].strip():
                con.execute("INSERT INTO chunks VALUES (?,?,?)", r)
                n += 1
    con.commit()
    print(f"indexed {n} sections -> {DB}")


def search(q):
    con = sqlite3.connect(DB)
    sql = ("SELECT path, section, snippet(chunks,2,'[',']','…',18) FROM chunks "
           "WHERE chunks MATCH ? ORDER BY rank LIMIT 12")
    try:
        rows = con.execute(sql, (q,)).fetchall()
    except sqlite3.OperationalError:  # FTS metacharacters — retry as a phrase
        try:
            rows = con.execute(sql, ('"' + q.replace('"', ' ') + '"',)).fetchall()
        except sqlite3.OperationalError:
            rows = []
    for p, s, sn in rows:
        print(f"{p} § {s}\n  {sn}")
    if not rows:
        print("no hits")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--search":
        if not DB.exists():
            build()
        search(sys.argv[2])
    else:
        build()
