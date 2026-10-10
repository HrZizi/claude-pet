"""`claude-pet doctor`: prints what is needed to debug a setup. Never prints tokens or full credentials."""
import platform
import sys

from . import __version__, paths


def main():
    from .claude import accounts, integration, limits_api
    print("claude-pet", __version__)
    print("python   ", sys.version.split()[0], "(frozen build)" if paths.is_frozen() else "")
    print("system   ", platform.platform())
    print("data dir ", paths.data_dir())
    print("hooks    ", "installed" if integration.is_installed() else "NOT installed (run: claude-pet install)")
    print("hook cmd ", integration.command("hook", "working"))
    try:
        import tkinter
        print("tk       ", tkinter.TkVersion)
    except Exception as e:
        print("tk       ", "MISSING:", e)
    from .art import pack as packs
    found, errors = packs.discover()
    print("sprite packs:", ", ".join("%s%s" % (k, "" if v.builtin else " (custom)") for k, v in found.items()))
    for folder, msg in errors:
        print("  INVALID pack:", msg)
    print("accounts:")
    for a in accounts.detect([], {}):
        readable = (a["source"] == "cli" or bool(a["dir"])) and limits_api.has_login(a["dir"])
        print("  - %-26s %-8s %s" % (a["name"], a["source"], "login readable" if readable else "no readable login (tokens only)"))
    return 0
