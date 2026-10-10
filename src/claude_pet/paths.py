"""Where claude-pet keeps its runtime files (never inside the install / source folder)."""
import os
import sys
from pathlib import Path


def is_frozen():
    """True when running from a PyInstaller build."""
    return bool(getattr(sys, "frozen", False))


def data_dir():
    """Per-user data folder. Override with the CLAUDE_PET_HOME environment variable."""
    env = os.environ.get("CLAUDE_PET_HOME")
    if env:
        p = Path(env)
    elif sys.platform.startswith("win"):
        p = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "ClaudePet"
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "ClaudePet"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "claude-pet"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_file():
    return data_dir() / "config.json"          # user settings (pet, size, position, accounts...)


def state_file():
    return data_dir() / "state.json"           # what each Claude session is doing (written by the hook)


def usage_file():
    return data_dir() / "usage.json"           # rate limits passed in by the CLI statusLine (optional)


def statusline_debug_file():
    return data_dir() / "statusline_last.json"
