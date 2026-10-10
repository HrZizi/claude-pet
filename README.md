# claude-pet

A tiny animated pet that sits on your taskbar edge and shows what Claude is doing.

| What Claude is doing | Pet |
|---|---|
| nothing (idle 20s+) | curled up asleep, zzz |
| working | sits behind a little laptop, focused eyes, typing paws, dots bubble |
| needs you (permission prompt) | distraught: drooping ears, tears, sweat drop, trembling |
| just finished | happy hop with sparkles |
| finished, waiting for you | big sparkly eyes, wagging tail, hearts: wants a pet (up to 2 min) |
| you click it | gets petted: hand strokes its head, hearts, purring |

Pets: Claude, Eevee, Bulbasaur (right-click -> Pet). Click the pet to pet it. Drag to move; it snaps
back onto the taskbar edge when dropped near it. Right-click: size, usage on/off and view, preview every
animation, snap to taskbar, start with Windows. Click the usage card to switch between limits / tokens / rotate.

## Setup
    python install.py       # adds hooks (+ statusLine if you have none) to ~/.claude/settings.json
    start.bat               # runs the pet (or right-click -> Start with Windows)
    python install.py --uninstall

Restart open Claude sessions after installing so they load the hooks.

## Usage panel
- Real 5h / 7d account limits (%) appear once Claude Code has passed rate-limit data to the
  statusLine script (`statusline.py`). Only works if the statusLine runs in your Claude setup.
- Until then it shows tokens used locally (from ~/.claude/projects). Set `token_budget_5h` /
  `token_budget_7d` in config.json to turn that into a percentage.
- Already have your own statusLine? Pipe its stdin through `statusline.py` first, or add
  the same `rate_limits` write to your script.

## Files
pet.py (app) | sprites.py (pixel art, edit/add pets here) | render.py (animation) |
hook.py (writes state.json) | statusline.py + usage.py (usage) | install.py

## Platform support
Windows 10/11 only today. macOS looks feasible (Tk + hooks are cross-platform); the Windows-specific
parts that would need a mac counterpart:

| Area | Windows (now) | macOS equivalent |
|---|---|---|
| see-through window | `-transparentcolor` | `-transparent True` + `bg='systemTransparent'` |
| taskbar/dock edge | `SystemParametersInfo(SPI_GETWORKAREA)` | `NSScreen.visibleFrame` (pyobjc) |
| light/dark theme | registry | `defaults read -g AppleInterfaceStyle` |
| start at login | .vbs in Startup | LaunchAgent plist |
| right-click | Button-3 | Button-2 / Ctrl-click |
| hook command | `python ...` | `python3 ...` |
| fonts | Segoe UI | system font |

Not yet implemented or tested (no Mac available to test on).
