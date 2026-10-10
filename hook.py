"""Claude Code hook: records what this session is doing in state.json (read by pet.py).

usage: python hook.py working|attention|done|end
"""
import json
import os
import sys
import time

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "working"
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    sid = str(data.get("session_id") or "unknown")

    try:
        with open(STATE, encoding="utf-8") as f:
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

    tmp = STATE + ".tmp%d" % os.getpid()
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, STATE)
    except OSError:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
