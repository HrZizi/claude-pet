"""Command line entry point:  claude-pet [pet] | hook | statusline | install | uninstall | limits | doctor"""
import sys
from pathlib import Path

from . import __version__

HELP = """claude-pet %s: an animated taskbar / Dock pet that shows what Claude Code is doing.

usage: claude-pet [command] [options]

commands:
  pet (default)      run the pet               --demo   canned data, no Claude needed (for screenshots)
  install            add the Claude Code hooks   --statusline  also set the CLI statusLine (limits, CLI only)
  uninstall          remove the hooks again
  pack ...           sprite packs: list | validate DIR | new DIR | install PATH | export ID DIR | folder
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
    if cmd == "pack":
        return _pack(rest)
    if cmd == "doctor":
        from . import doctor
        return doctor.main()
    if cmd == "pet":
        from . import app
        return app.run(demo="--demo" in rest)
    print("unknown command: %s\n\n%s" % (cmd, HELP))
    return 2


def _pack(rest):
    from .art import pack as packs
    sub = rest[0] if rest else "list"
    args = rest[1:]
    try:
        if sub == "list":
            found, errors = packs.discover()
            for pid, pk in found.items():
                print("%-14s %-22s %s%s" % (pid, pk.name, "built-in" if pk.builtin else "custom",
                                           ("  by " + pk.author) if pk.author else ""))
            for folder, msg in errors:
                print("INVALID  %s\n         %s" % (folder, msg))
            print("your packs folder:", packs.user_dir())
        elif sub == "validate" and args:
            pk = packs.validate(args[0])
            print("OK: %s (%dx%d px frames), states: %s" % (pk.name, pk.frame_w, pk.frame_h, ", ".join(
                "%s(%d)" % (n, a.count) for n, a in pk.states.items())))
            missing = [n for n in packs.STATES if n not in pk.states]
            if missing:
                print("not provided (the engine derives these from idle): %s" % ", ".join(missing))
            for w in pk.warnings:
                print("warning:", w)
        elif sub == "new" and args:
            name = args[args.index("--name") + 1] if "--name" in args else Path(args[0]).name
            print("created", packs.scaffold(args[0], name), "- edit it, then: claude-pet pack validate", args[0])
        elif sub == "install" and args:
            pk = packs.install(args[0], overwrite="--overwrite" in args)
            print("installed '%s'. Restart the pet or use right-click > Pet > Reload sprite packs." % pk.name)
        elif sub == "export" and len(args) >= 2:
            print("exported to", packs.export_builtin(args[0], args[1]))
        elif sub == "folder":
            print(packs.user_dir())
        else:
            print(HELP)
            return 2
    except packs.PackError as e:
        print("error:", e)
        return 1
    return 0
