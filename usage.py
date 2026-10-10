"""Usage numbers for the pet.

1. Real account limits (% of the 5-hour / 7-day windows) from usage.json, written by statusline.py.
2. Fallback: tokens used locally, summed from Claude Code's transcripts in ~/.claude/projects.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

DIR = Path(__file__).resolve().parent
USAGE_FILE = DIR / "usage.json"
PROJECTS = Path.home() / ".claude" / "projects"
WEEK = 7 * 86400


def _epoch(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) / 1000 if v > 1e12 else float(v)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def read_limits():
    """-> {'5h': (pct, resets_at|None), '7d': (...)} or None when no fresh data exists."""
    try:
        d = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        rl = d["rate_limits"]
    except Exception:
        return None
    now = time.time()
    out = {}
    for label, key in (("5h", "five_hour"), ("7d", "seven_day")):
        w = rl.get(key)
        if not isinstance(w, dict) or w.get("used_percentage") is None:
            continue
        pct = float(w["used_percentage"])
        reset = _epoch(w.get("resets_at"))
        if reset and reset < now:      # that window has rolled over since the data was saved
            pct = 0.0
        out[label] = (pct, reset)
    return out or None


def fmt_tokens(n):
    if n >= 1e6:
        return "%.1fM" % (n / 1e6)
    if n >= 1e3:
        return "%dk" % round(n / 1e3)
    return str(int(n))


def fmt_delta(secs):
    secs = max(0, int(secs))
    h, m = divmod(secs // 60, 60)
    d, h = divmod(h, 24)
    if d:
        return "%dd%dh" % (d, h)
    return "%dh%02dm" % (h, m) if h else "%dm" % m


class LocalTokens:
    """Incrementally scans transcripts; call scan() from a background thread."""

    def __init__(self, root=None):
        self.root = Path(root) if root else PROJECTS
        self._offsets = {}      # path -> (size_read)
        self._msgs = {}         # message key -> (epoch, tokens)

    def scan(self):
        if not self.root.exists():
            return
        cutoff = time.time() - WEEK
        for p in self.root.rglob("*.jsonl"):
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_mtime < cutoff:
                continue
            # transcript id = file name; sub-agent files live in <session>/subagents/
            sid = p.parent.parent.name if p.parent.name == "subagents" else p.stem
            start = self._offsets.get(p, 0)
            if st.st_size < start:
                start = 0
            if st.st_size == start:
                continue
            try:
                with open(p, "rb") as f:
                    f.seek(start)
                    chunk = f.read()
            except OSError:
                continue
            end = chunk.rfind(b"\n") + 1      # only consume whole lines
            self._offsets[p] = start + end
            for line in chunk[:end].splitlines():
                if b'"usage"' not in line:
                    continue
                try:
                    o = json.loads(line)
                    m = o["message"]
                    u = m["usage"]
                    ts = _epoch(o["timestamp"])
                except Exception:
                    continue
                if not ts:
                    continue
                n = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0) \
                    + (u.get("cache_creation_input_tokens") or 0)
                key = (m.get("id") or "") + (o.get("requestId") or "") or id(o)
                old = self._msgs.get(key)
                if not old or n > old[1]:
                    self._msgs[key] = (ts, n, sid)

    def totals(self, owner=None, account=None, default=None):
        """Token sums for the last 5h / 7d. With owner ({session id: account id}) only that account's
        sessions count; sessions the owner map doesn't know belong to `default`."""
        now = time.time()
        five = week = 0
        for ts, n, sid in list(self._msgs.values()):
            if account is not None and owner is not None and owner.get(sid, default) != account:
                continue
            if now - ts <= WEEK:
                week += n
                if now - ts <= 5 * 3600:
                    five += n
        return {"5h": five, "7d": week}
