"""Optional: fetch the real 5-hour / weekly usage limits, the same read-only data Claude Code's /usage shows.

Opt-in (config "limits_api"). Uses the access token Claude Code already stored for you:
  Windows/Linux: ~/.claude/.credentials.json    macOS: Keychain item "Claude Code-credentials"
The token is only read, held in memory for one request, and sent to api.anthropic.com. It is never
written, logged or refreshed here (if it has expired, open Claude Code once and it will refresh it).
Undocumented endpoint: it may change without notice.
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import usage

URL = "https://api.anthropic.com/api/oauth/usage"


class LimitsError(Exception):
    """Short, token-free message that is safe to show in the UI."""


def _oauth():
    try:
        if sys.platform == "darwin":
            raw = subprocess.run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                                 capture_output=True, text=True, timeout=10).stdout
        else:
            raw = (Path.home() / ".claude" / ".credentials.json").read_text(encoding="utf-8")
        return json.loads(raw)["claudeAiOauth"]
    except Exception:
        raise LimitsError("no Claude login found (sign in to Claude Code first)")


def fetch():
    """-> {'5h': (pct, resets_at|None), '7d': (...)}"""
    o = _oauth()
    token = o.get("accessToken")
    if not token:
        raise LimitsError("no access token")
    if o.get("expiresAt", 0) / 1000 < time.time() + 30:
        raise LimitsError("login token expired (use Claude Code once to refresh it)")
    req = urllib.request.Request(URL, headers={
        "Authorization": "Bearer " + token,
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": "claude-pet/1.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise LimitsError("usage request failed (HTTP %d)" % e.code)
    except Exception:
        raise LimitsError("usage request failed (offline?)")
    out = {}
    for label, key in (("5h", "five_hour"), ("7d", "seven_day")):
        w = data.get(key)
        if not isinstance(w, dict):
            continue
        pct = w.get("utilization", w.get("used_percentage"))
        if pct is None:
            continue
        out[label] = (float(pct), usage._epoch(w.get("resets_at")))
    if not out:
        raise LimitsError("unexpected response format")
    return out


if __name__ == "__main__":      # python limits_api.py  -> prints the numbers (never the token)
    try:
        for k, (pct, reset) in fetch().items():
            print(k, "%.0f%%" % pct, "resets in", usage.fmt_delta(reset - time.time()) if reset else "?")
    except LimitsError as e:
        print("error:", e)
