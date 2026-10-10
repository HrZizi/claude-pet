"""Claude Code hook: records what this session is doing in state.json (read by the pet).

usage: claude-pet-cli hook working|attention|done|end        (event JSON arrives on stdin)

Kept deliberately tiny and dependency-free: it runs on every prompt and tool call.
"""
import json
import os
import sys
import time

from .. import paths


def main(argv):
    event = argv[0] if argv else "working"
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    sid = str(data.get("session_id") or "unknown")

    state_path = str(paths.state_file())
    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}
    sessions = state.setdefault("sessions", {})

    now = time.time()
    if event == "end":
        sessions.pop(sid, None)
    else:
        sessions[sid] = {"state": event, "ts": now}
    for k in [k for k, v in sessions.items() if now - v.get("ts", 0) > 86400]:
        del sessions[k]

    tmp = state_path + ".tmp%d" % os.getpid()
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, state_path)
    except OSError:
        pass
    return 0
