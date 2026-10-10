"""Adds (or removes) the claude-pet hooks and statusLine in ~/.claude/settings.json.

python install.py              install hooks (+ statusLine if you don't already have one)
python install.py --uninstall  remove everything this script added
A backup is saved next to settings.json before any change.
"""
import json
import shlex
import shutil
import sys
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent
SETTINGS = Path.home() / ".claude" / "settings.json"
MARK = "claude-pet"

# (event, matcher or None, argument for hook.py)
HOOKS = [
    ("UserPromptSubmit", None, "working"),
    ("PostToolUse", None, "working"),
    ("Notification", "permission_prompt|elicitation_dialog", "attention"),
    ("Stop", None, "done"),
    ("SessionEnd", None, "end"),
]


def cmd(script, *args):
    path = (DIR / script).as_posix()
    if sys.platform.startswith("win"):
        # forward slashes + no quotes keeps this valid in bash, cmd and PowerShell
        py = shutil.which("python") and "python" or sys.executable.replace("\\", "/")
    else:
        py = shlex.quote(sys.executable)
        path = shlex.quote(path)
    return " ".join([py, path, *args])


def is_ours(h):
    c = h.get("command", "").replace("\\", "/")
    return DIR.as_posix() in c or MARK in c


def strip(settings):
    hooks = settings.get("hooks", {})
    for ev in list(hooks):
        groups = []
        for g in hooks[ev]:
            g["hooks"] = [h for h in g.get("hooks", []) if not is_ours(h)]
            if g["hooks"]:
                groups.append(g)
        if groups:
            hooks[ev] = groups
        else:
            del hooks[ev]
    if not hooks:
        settings.pop("hooks", None)
    sl = settings.get("statusLine") or {}
    if is_ours(sl):
        del settings["statusLine"]


def main():
    uninstall = "--uninstall" in sys.argv
    settings = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    if SETTINGS.exists():
        shutil.copy(SETTINGS, SETTINGS.with_name("settings.json.bak-%d" % time.time()))
    strip(settings)
    if not uninstall:
        hooks = settings.setdefault("hooks", {})
        for ev, matcher, arg in HOOKS:
            group = {"hooks": [{"type": "command", "command": cmd("hook.py", arg)}]}
            if matcher:
                group["matcher"] = matcher
            hooks.setdefault(ev, []).append(group)
        if "statusLine" not in settings:
            settings["statusLine"] = {"type": "command", "command": cmd("statusline.py")}
        else:
            print("You already have a statusLine; left it alone. See README to chain usage capture.")
    SETTINGS.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print("Uninstalled." if uninstall else "Installed. Restart open Claude sessions for hooks to load.")


if __name__ == "__main__":
    main()
