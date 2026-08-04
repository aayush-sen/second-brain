#!/usr/bin/env python3
"""Daily insights — social/web pull for the morning briefing's Daily insights
section (os-reflect). Companion to the two Morning Brew newsletters the
reflection reads from Gmail; this script covers the real-time community side.

ALL SOURCES, 24H WINDOW: originally X-only (`--search=x`), but four straight
briefings (2026-07-13..16) flagged single-source concentration — X alone is
mostly aggregator-bot noise. Aayush's call (2026-07-16): run the engine's full
source set (X, Reddit, HN, web...) like the last30days skill does, just with a
1-day window. `--x-related` still pulls the day's posts from the prolific AI
voices so "what the big AI people said today" stays in the corpus.

Design notes learned the hard way:
- The engine IGNORES each subquery's `sources` field (it queries its whole
  available set); only a `--search=` flag restricts sources. We pass none.
- Every search_query must be a specific multi-word phrase — a bare short token
  like "ai" matches multilingual spam on X. No lone short tokens.
- No `--quick`: that profile runs only the FIRST subquery, dropping the rest.
- The plan/topic are static strings; no vault content ever enters a query
  (CLAUDE.md sensitive-content rule). Raw output goes to a temp dir.

Degrades loudly: any missing dependency prints one PULSE-UNAVAILABLE line and
exits 1 so the skill can fall back to plain WebSearch instead of failing."""
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOPIC = "AI developments and financial markets"
# Prolific AI voices + the labs/companies themselves — the engine pulls each
# one's posts for the day (lower weight) via from:{handle}, so the synthesis
# can surface what they actually said. People: Altman, Karpathy, LeCun,
# Hassabis, Ng, Jim Fan, Brockman, Musk, Paul Graham. Orgs: OpenAI, Anthropic,
# Nvidia, xAI. Handles that didn't post that day simply return nothing.
AI_VOICES = ("sama,karpathy,ylecun,demishassabis,AndrewYNg,DrJimFan,gdb,"
             "elonmusk,paulg,OpenAI,AnthropicAI,nvidia,xai")
# Six lanes, balanced AI + finance/investing, searched across every active
# source (per-subquery "sources" would be ignored by the engine anyway).
PLAN = """{
  "intent": "breaking_news",
  "freshness_mode": "strict_recent",
  "cluster_mode": "story",
  "subqueries": [
    {"label": "ai_labs",
     "search_query": "openai anthropic google deepmind",
     "ranking_query": "What are the biggest AI-lab stories today?",
     "weight": 1.0},
    {"label": "ai_models_agents",
     "search_query": "ai model agents release",
     "ranking_query": "What new AI models, agents, or tools are people posting about today?",
     "weight": 0.9},
    {"label": "ai_frontier",
     "search_query": "artificial intelligence AGI",
     "ranking_query": "What is the big-picture AI conversation today?",
     "weight": 0.8},
    {"label": "markets",
     "search_query": "stock market earnings",
     "ranking_query": "What are the biggest market-moving stories today?",
     "weight": 0.8},
    {"label": "macro_rates",
     "search_query": "federal reserve interest rates inflation",
     "ranking_query": "What macro, rates, or inflation news are people posting today?",
     "weight": 0.7},
    {"label": "investing",
     "search_query": "investing stocks nvidia tesla",
     "ranking_query": "What are investors talking about today?",
     "weight": 0.7}
  ]
}"""


def die(msg: str):
    print(f"PULSE-UNAVAILABLE: {msg} — fall back to WebSearch or skip the section.")
    sys.exit(1)


def find_engine() -> Path:
    root = Path.home() / ".claude/plugins/cache/last30days-skill/last30days"
    if not root.is_dir():
        die("last30days plugin not installed")

    def vkey(p: Path):
        try:
            return tuple(int(x) for x in p.name.split("."))
        except ValueError:
            return (-1,)

    for d in sorted((x for x in root.iterdir() if x.is_dir()), key=vkey, reverse=True):
        for cand in (d / "skills/last30days/scripts/last30days.py", d / "scripts/last30days.py"):
            if cand.is_file():
                return cand
    die("no engine script found in plugin cache")


def find_python() -> str:
    for py in ("python3.14", "python3.13", "python3.12"):
        if shutil.which(py):
            return py
    if sys.version_info >= (3, 12):
        return sys.executable
    die("no Python 3.12+ for the engine")


def engine_argv(py, engine, plan_file, tmp) -> list:
    """The engine command. No `--search=` flag: all active sources contribute
    (X-only proved too noisy — see module docstring). `--days=1` keeps it a
    24-hour pulse; `--x-related` pulls the AI voices' own posts; no --quick
    (it would run only the first subquery)."""
    return [py, str(engine), TOPIC, "--days=1", "--emit=compact",
            "--plan", str(plan_file), f"--x-related={AI_VOICES}", f"--save-dir={tmp}"]


def pull_voices(engine: Path) -> str:
    """FROM-lane pull for AI_VOICES, run BEFORE the engine's topic search.

    The engine's own handle lane (Phase 2) runs after 6 parallel X subqueries;
    one 429 marks X rate-limited and the lane is silently skipped — which is
    why briefings kept reporting 'quiet day for the named voices' on days they
    posted (diagnosed 2026-07-28). Going first, one cheap query per handle,
    sidesteps that. bird authenticates with Aayush's own Arc X session cookies
    (the tool's designed browser-cookie mode); creds never leave the machine.
    Degrades to an empty string, never fails the run."""
    try:
        sys.path.insert(0, str(engine.parent))
        from lib import env as l30_env, bird_x
        cfg = l30_env.get_config(l30_env.ConfigLoadPolicy(browser_cookies="read"))
        if not (cfg.get("AUTH_TOKEN") and cfg.get("CT0") and bird_x.is_bird_installed()):
            return "\n## AI voices (last 24h)\nVOICES-UNAVAILABLE: bird/X cookies not available.\n"
        bird_x.set_credentials(cfg["AUTH_TOKEN"], cfg["CT0"])
        since = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        items = bird_x.search_handles(
            [h for h in AI_VOICES.split(",")], None, since, count_per=5)
        if not items:
            return "\n## AI voices (last 24h)\n(none of the named voices posted)\n"
        lines = ["\n## AI voices (last 24h)",
                 "Actual posts BY the named voices, pulled directly — trust this over",
                 "the ranked clusters when judging whether they were quiet.\n"]
        for it in items:
            text = " ".join((it.get("text") or "").split())
            if len(text) > 300:
                text = text[:300] + "…"
            likes = (it.get("engagement") or {}).get("likes") or 0
            lines.append(f"- @{it.get('author_handle','?')} ({it.get('date') or '?'}) "
                         f"[{likes} likes] {text}")
            if it.get("url"):
                lines.append(f"  {it['url']}")
        return "\n".join(lines) + "\n"
    except Exception as e:
        return f"\n## AI voices (last 24h)\nVOICES-UNAVAILABLE: {e}\n"


MAX_CLUSTERS = 30


def pick_clusters(stdout: str, tmp: Path, limit: int = MAX_CLUSTERS) -> str:
    """Prefer the engine's saved raw file over `--emit=compact` stdout.

    Diagnosed 2026-08-03: retrieval is NOT single-source (a typical run pulls
    HN, GitHub and Reddit alongside X), but compact stdout keeps only the top
    ~7 clusters and X's engagement scores sweep those — so every briefing read
    as X-only noise. The raw file `--save-dir` already writes holds every
    cluster; take the first `limit` of them instead."""
    raw = next(iter(sorted(tmp.glob("*-raw.md"))), None)
    if raw is None:
        return stdout
    try:
        text = raw.read_text()
    except OSError:
        return stdout
    parts = re.split(r"(?m)^(?=### \d+\. )", text)
    return "".join(parts[:limit + 1]) if len(parts) > limit + 1 else text


def main():
    engine, py = find_engine(), find_python()
    voices = pull_voices(engine)
    tmp = Path(tempfile.mkdtemp(prefix="daily-insights-"))
    plan_file = tmp / "plan.json"
    plan_file.write_text(PLAN)
    env = os.environ.copy()
    # engine's stdlib urllib needs a CA bundle on framework-installed pythons
    cert = subprocess.run([py, "-c", "import certifi; print(certifi.where())"],
                          capture_output=True, text=True)
    if cert.returncode == 0 and cert.stdout.strip():
        env.setdefault("SSL_CERT_FILE", cert.stdout.strip())
    try:
        p = subprocess.run(
            engine_argv(py, engine, plan_file, tmp),
            capture_output=True, text=True, timeout=300, env=env)
    except subprocess.TimeoutExpired:
        die("engine timed out after 300s")
    if p.returncode:
        die(f"engine exited {p.returncode}: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else 'no stderr'}")
    out = pick_clusters(p.stdout, tmp) + voices
    # persist a snapshot os-reflect can fall back to if a later run is rate-limited
    try:
        snap = Path(__file__).resolve().parent.parent / "memory" / "cache" / "daily-insights-latest.md"
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(out)
    except OSError:
        pass
    print(out)


def selftest():
    """python3 daily_insights.py --selftest"""
    d = Path(tempfile.mkdtemp())
    body = "head\n" + "".join(f"### {i}. c{i}\nx\n" for i in range(1, 6))
    (d / "t-raw.md").write_text(body)
    assert pick_clusters("STDOUT", d, limit=2).count("### ") == 2
    assert pick_clusters("STDOUT", d, limit=99) == body
    assert pick_clusters("STDOUT", Path(tempfile.mkdtemp())) == "STDOUT"
    print("ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
