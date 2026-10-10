"""Optional: fetch the real 5-hour / weekly usage limits, the same read-only data Claude Code's /usage shows.

Opt-in (config "limits_api"). Uses the access token Claude Code already stored for you. Which account that is
depends on the Claude Code *config folder* (default ~/.claude, the CLI's login; the Desktop app keeps its own
separate login that this cannot read). Extra accounts = extra config folders, each logged in once with
`CLAUDE_CONFIG_DIR=<folder> claude` then /login.
  <folder>/.credentials.json     (macOS default folder: Keychain item "Claude Code-credentials")
The token is only read, held in memory for one request, and sent to api.anthropic.com. It is never
written, logged or refreshed here (if it has expired, open Claude Code once and it will refresh it).
Undocumented endpoint: it may change without notice.
"""
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import usage

class LimitsError(Exception):
    """Short, token-free message that is safe to show in the UI."""


def _oauth(config_dir=None):
    try:
        if sys.platform == "darwin" and not config_dir:
            raw = subprocess.run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                                 capture_output=True, text=True, timeout=10).stdout
        else:
            raw = (Path(config_dir) if config_dir else Path.home() / ".claude").joinpath(
                ".credentials.json").read_text(encoding="utf-8-sig")
        return json.loads(raw)["claudeAiOauth"]
    except Exception:
        raise LimitsError("no Claude login found (sign in to Claude Code first)")


def has_login(config_dir=None):
    try:
        _oauth(config_dir)
        return True
    except LimitsError:
        return False


def plan_label(config_dir=None):
    """'Pro', 'Max 5x', ... from the locally stored login (no network)."""
    try:
        o = _oauth(config_dir)
    except LimitsError:
        return ""
    kind = (o.get("subscriptionType") or "").capitalize()
    m = re.search(r"(\d+)x", o.get("rateLimitTier") or "")
    return (kind + (" %sx" % m.group(1) if m and kind == "Max" else "")).strip()


def _get(path, token):
    req = urllib.request.Request("https://api.anthropic.com" + path, headers={
        "Authorization": "Bearer " + token,
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": "claude-pet/1.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise LimitsError("request failed (HTTP %d)" % e.code)
    except Exception:
        raise LimitsError("request failed (offline?)")


def email(config_dir=None):
    """Account email of that login ('' if unavailable)."""
    try:
        o = _oauth(config_dir)
        if o.get("expiresAt", 0) / 1000 < time.time() + 30:
            return ""
        return ((_get("/api/oauth/profile", o["accessToken"]).get("account")) or {}).get("email", "")
    except (LimitsError, KeyError):
        return ""


def fetch(config_dir=None):
    """-> {'5h': (pct, resets_at|None), '7d': (...)}"""
    o = _oauth(config_dir)
    token = o.get("accessToken")
    if not token:
        raise LimitsError("no access token")
    if o.get("expiresAt", 0) / 1000 < time.time() + 30:
        raise LimitsError("login token expired (use Claude Code once to refresh it)")
    data = _get("/api/oauth/usage", token)
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


if __name__ == "__main__":      # python limits_api.py [config_dir] -> prints account + numbers (never the token)
    cd = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        print("account:", email(cd) or "?", "|", plan_label(cd) or "?")
        for k, (pct, reset) in fetch(cd).items():
            print(k, "%.0f%%" % pct, "resets in", usage.fmt_delta(reset - time.time()) if reset else "?")
    except LimitsError as e:
        print("error:", e)
