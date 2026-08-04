#!/usr/bin/env python3
"""Phone dashboard sync — apply queued phone actions, push a state snapshot.
Single pass per run (launchd provides the loop). Stdlib only.
Run: python3 phone_sync.py [--dry-run]"""

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent  # os/scripts
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "dashboard"))
import oslib
import serve  # state() + redaction helpers; serve only binds a port under __main__

ENV_FILE = HERE.parent / "integrations" / "phone.env"
LOG_FILE = HERE.parent / "integrations" / "phone_sync.log"


def load_env() -> dict:
    cfg = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        if not cfg.get(key) or cfg[key].startswith("PASTE_"):
            sys.exit(f"phone_sync: set {key} in {ENV_FILE}")
    return cfg


def sb(cfg, method, path, body=None, prefer=None):
    """Supabase PostgREST call. Returns parsed JSON or None."""
    req = urllib.request.Request(
        cfg["SUPABASE_URL"].rstrip("/") + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    req.add_header("apikey", cfg["SUPABASE_SERVICE_KEY"])
    req.add_header("Authorization", "Bearer " + cfg["SUPABASE_SERVICE_KEY"])
    req.add_header("Content-Type", "application/json")
    if prefer:
        req.add_header("Prefer", prefer)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def apply_action(kind, p):
    """(ok, error) — mirrors the desktop dashboard's POST handlers via oslib."""
    try:
        if kind == "status":
            return oslib.set_status(
                p.get("col", ""), p.get("file", ""), p.get("status", "")
            ), None
        if kind == "note":
            return oslib.add_note(
                p.get("col", ""), p.get("file", ""), p.get("line", "")
            ), None
        if kind == "log":
            line = (p.get("line") or "").strip()
            if not line:
                return False, "empty line"
            oslib.episodic(p.get("type") or "note", line)
            return True, None
        if kind == "deadline":
            return oslib.set_deadline(
                p.get("date", ""), p.get("item", ""), p.get("status", "")
            ), None
        if kind == "deadline_add":
            return oslib.add_deadline(
                p.get("date", ""), p.get("domain", ""), p.get("item", "")
            ), None
        return False, f"unknown kind {kind}"
    except Exception as e:  # a bad action must never kill the run
        return False, repr(e)


def build_snapshot() -> dict:
    """Exactly what local /api/state serves, minus academics (v1)."""
    payload = serve.state()
    payload["deadlines"] = serve._public_deadlines(payload["deadlines"])
    payload["needs"] = serve._public_needs(payload["needs"])
    return payload


def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")


# absolute path — launchd's PATH doesn't include ~/.local/bin
CLAUDE_BIN = "/Users/aayush/.local/bin/claude"
VAULT = HERE.parent.parent
ASK_PROMPT = (
    "Answer this question from Aayush about his second brain / OS. "
    "Read wiki/index.md and the relevant os/ or wiki/ pages before answering. "
    "Plain text with light markdown, under 200 words, no preamble.\n\nQuestion: {q}"
)


def run_claude(q: str) -> str:
    """Headless subscription answer; always returns a non-empty string."""
    try:
        r = subprocess.run(
            [CLAUDE_BIN, "-p", ASK_PROMPT.format(q=q)],
            capture_output=True,
            text=True,
            timeout=240,
            cwd=str(VAULT),
        )
        return (
            r.stdout or ""
        ).strip() or f"(no answer — {(r.stderr or 'empty output').strip()[:200]})"
    except subprocess.TimeoutExpired:
        return "(timed out after 4 min — ask again or simplify)"
    except OSError as e:
        return f"(claude unavailable: {e})"


def answer_asks(cfg, dry=False):
    # ponytail: max 3 per run bounds runtime; launchd fires again in 2 min
    pending = (
        sb(
            cfg,
            "GET",
            "/rest/v1/asks?a=is.null&order=created_at.asc&select=id,q&limit=3",
        )
        or []
    )
    for a in pending:
        if dry:
            print(f"would answer: {a['q'][:60]}")
            continue
        ans = run_claude(a["q"])
        sb(
            cfg,
            "PATCH",
            f"/rest/v1/asks?id=eq.{a['id']}",
            {"a": ans[:8000], "answered_at": datetime.now(timezone.utc).isoformat()},
            prefer="return=minimal",
        )
        log(f"ask answered ({len(ans)} chars): {a['q'][:60]}")


def main(dry=False):
    cfg = load_env()
    now = datetime.now(timezone.utc).isoformat()
    pending = (
        sb(
            cfg,
            "GET",
            "/rest/v1/actions?applied_at=is.null&order=created_at.asc&select=id,kind,payload",
        )
        or []
    )
    applied = 0
    for a in pending:
        if dry:
            print(f"would apply {a['kind']}: {json.dumps(a['payload'])}")
            continue
        ok, err = apply_action(a["kind"], a["payload"] or {})
        sb(
            cfg,
            "PATCH",
            f"/rest/v1/actions?id=eq.{a['id']}",
            {"applied_at": now, "ok": ok, "error": err},
            prefer="return=minimal",
        )
        applied += 1
        log(f"action {a['kind']} ok={ok}" + (f" err={err}" if err else ""))
    snap = build_snapshot()
    if dry:
        print(
            f"would push snapshot ({len(json.dumps(snap))} bytes); {len(pending)} pending action(s)"
        )
        return
    sb(
        cfg,
        "POST",
        "/rest/v1/snapshot",
        {"id": 1, "data": snap, "updated_at": now},
        prefer="resolution=merge-duplicates,return=minimal",
    )
    log(f"synced: {applied} action(s), snapshot pushed")
    # asks last: a slow claude run must not delay the snapshot
    try:
        answer_asks(cfg)
    except Exception as e:  # asks table may not exist yet
        log(f"asks skipped: {e}")


if __name__ == "__main__":
    main(dry="--dry-run" in sys.argv)
