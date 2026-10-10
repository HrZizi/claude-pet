"""Connects claude-pet to Claude Code by adding (or removing) hooks in ~/.claude/settings.json.

Only entries that call claude-pet are ever touched; everything else in the file is preserved, and a backup is
written next to it before any change.
"""
import json
import shlex
import shutil
import sys
import time
from pathlib import Path

from .. import paths

SETTINGS = Path.home() / ".claude" / "settings.json"

# (event, matcher or None, argument for `hook`)
HOOKS = [
    ("UserPromptSubmit", None, "working"),
    ("PostToolUse", None, "working"),
    ("Notification", "permission_prompt|elicitation_dialog", "attention"),
    ("Stop", None, "done"),
    ("SessionEnd", None, "end"),
]


def _quote(s):
    if sys.platform.startswith("win"):
        s = s.replace("\\", "/")
        return '"%s"' % s if " " in s else s       # unquoted when possible: valid in bash, cmd and PowerShell
    return shlex.quote(s)


def launcher():
    """argv prefix that runs the claude-pet CLI from wherever it is installed."""
    exe = Path(sys.executable)
    if paths.is_frozen():                                                       # PyInstaller build
        cli = exe.with_name("claude-pet-cli" + exe.suffix)
        return [str(cli if cli.exists() else exe)]
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        exe = exe.with_name("python.exe")                                       # hooks need stdin / no GUI host
    return [str(exe), "-m", "claude_pet"]


def command(*args):
    return " ".join(_quote(p) for p in launcher() + list(args))


def is_ours(h):
    c = (h.get("command") or "").replace("\\", "/").lower().replace("-", "_")
    return "claude_pet" in c or "claudepet" in c


def _strip(settings):
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
    if is_ours(settings.get("statusLine") or {}):
        del settings["statusLine"]


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig")) if Path(path).exists() else {}


def _save(path, settings):
    path = Path(path)
    if path.exists():
        shutil.copy(path, path.with_name(path.name + ".bak-%d" % time.time()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def install(settings_path=None, statusline=False):
    """Add the hooks (replacing any older claude-pet entries). Returns the settings path."""
    path = settings_path or SETTINGS
    settings = _load(path)
    _strip(settings)
    hooks = settings.setdefault("hooks", {})
    for ev, matcher, arg in HOOKS:
        group = {"hooks": [{"type": "command", "command": command("hook", arg)}]}
        if matcher:
            group["matcher"] = matcher
        hooks.setdefault(ev, []).append(group)
    if statusline and "statusLine" not in settings:
        settings["statusLine"] = {"type": "command", "command": command("statusline")}
    _save(path, settings)
    return path


def uninstall(settings_path=None):
    path = settings_path or SETTINGS
    if not Path(path).exists():
        return path
    settings = _load(path)
    _strip(settings)
    _save(path, settings)
    return path


def is_installed(settings_path=None):
    """True when every claude-pet hook event is present."""
    try:
        hooks = _load(settings_path or SETTINGS).get("hooks", {})
    except (OSError, ValueError):
        return False
    return all(any(is_ours(h) for g in hooks.get(ev, []) for h in g.get("hooks", [])) for ev, _, _ in HOOKS)
