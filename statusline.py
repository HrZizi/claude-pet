"""Claude Code statusLine command. Saves the account rate-limit info Claude Code passes in
(5-hour and 7-day usage) to usage.json for the pet, and prints a short status line."""
import json
import os
import sys
import time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage.json")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    try:                                   # diagnostics: what does Claude Code actually send?
        with open(OUT.replace("usage.json", "statusline_last.json"), "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "keys": sorted(data), "data": data}, f)
    except OSError:
        pass
    rl = data.get("rate_limits")
    if isinstance(rl, dict) and rl:
        try:
            tmp = OUT + ".tmp%d" % os.getpid()
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "rate_limits": rl}, f)
            os.replace(tmp, OUT)
        except OSError:
            pass
    model = (data.get("model") or {}).get("display_name") or ""
    parts = [model] if model else []
    five = (rl or {}).get("five_hour") or {}
    if five.get("used_percentage") is not None:
        parts.append("5h %d%%" % round(five["used_percentage"]))
    print(" | ".join(parts))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
