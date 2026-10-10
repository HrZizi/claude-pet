"""Claude Code statusLine command (optional, CLI only).

Saves the account rate-limit info Claude Code passes in (5-hour and 7-day usage) to usage.json for the pet,
and prints a short status line. The Desktop app does not run the statusLine; use the limits API toggle there.
"""
import json
import os
import sys
import time

from .. import paths


def main(argv=None):
    out = str(paths.usage_file())
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    try:                                   # diagnostics: what does Claude Code actually send?
        with open(str(paths.statusline_debug_file()), "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "keys": sorted(data)}, f)       # key names only, never values
    except OSError:
        pass
    rl = data.get("rate_limits")
    if isinstance(rl, dict) and rl:
        try:
            tmp = out + ".tmp%d" % os.getpid()
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "rate_limits": rl}, f)
            os.replace(tmp, out)
        except OSError:
            pass
    model = (data.get("model") or {}).get("display_name") or ""
    parts = [model] if model else []
    five = (rl or {}).get("five_hour") or {}
    if five.get("used_percentage") is not None:
        parts.append("5h %d%%" % round(five["used_percentage"]))
    print(" | ".join(parts))
    return 0
