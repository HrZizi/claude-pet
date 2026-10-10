"""Command line entry point:  claude-pet [pet] | hook | statusline | install | uninstall | limits | doctor"""
import sys

from . import __version__

HELP = """claude-pet %s: an animated taskbar / Dock pet that shows what Claude Code is doing.

usage: claude-pet [command] [options]

commands:
  pet (default)      run the pet               --demo   canned data, no Claude needed (for screenshots)
  install            add the Claude Code hooks   --statusline  also set the CLI statusLine (limits, CLI only)
  uninstall          remove the hooks again
  limits [folder]    print the 5h / weekly limits of a Claude login (what the pet's card shows)
  doctor             print diagnostics (paste this into bug reports; contains no tokens)
  hook <event>       internal: called by Claude Code hooks (working|attention|done|end)
  statusline         internal: Claude Code statusLine command
  --version, --help
""" % __version__


def _ensure_streams():
    """Windowed (console-less) builds have no stdout / stderr: give print() somewhere harmless to go."""
    import os
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w"))


def main(argv=None):
    _ensure_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv and not argv[0].startswith("--") else "pet"
    rest = argv[1:] if argv and not argv[0].startswith("--") else argv

    if cmd in ("--version", "version") or "--version" in argv:
        print(__version__)
        return 0
    if cmd in ("help", "-h") or "--help" in argv:
        print(HELP)
        return 0
    if cmd == "hook":                              # hot path: import as little as possible
        from .claude import hook
        return hook.main(rest)
    if cmd == "statusline":
        from .claude import statusline
        return statusline.main(rest)
    if cmd == "install":
        from .claude import integration
        p = integration.install(statusline="--statusline" in rest)
        print("Hooks installed in %s\nRestart open Claude sessions so they load the hooks." % p)
        return 0
    if cmd == "uninstall":
        from .claude import integration
        print("Hooks removed from %s" % integration.uninstall())
        return 0
    if cmd == "limits":
        from .claude import limits_api, usage
        import time
        d = rest[0] if rest else None
        try:
            print("account:", limits_api.email(d) or "?", "|", limits_api.plan_label(d) or "?")
            for k, (pct, reset) in limits_api.fetch(d).items():
                print(k, "%.0f%%" % pct, "resets in", usage.fmt_delta(reset - time.time()) if reset else "?")
        except limits_api.LimitsError as e:
            print("error:", e)
            return 1
        return 0
    if cmd == "doctor":
        from . import doctor
        return doctor.main()
    if cmd == "pet":
        from . import app
        return app.run(demo="--demo" in rest)
    print("unknown command: %s\n\n%s" % (cmd, HELP))
    return 2
