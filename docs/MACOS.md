# macOS notes

macOS support is implemented in `src/claude_pet/ui/platform_support.py` and `popup_menu.py` but was written without a Mac
to test on. Reports and fixes are very welcome.

## Install

Python 3 with **Tk 8.6** is required (python.org installer, or `brew install python-tk`).

```bash
pipx install "claude-pet[mac]"   # [mac] adds pyobjc for the exact Dock position
claude-pet install
claude-pet
```

## What differs from Windows

| Area | Windows | macOS |
|---|---|---|
| See-through window | colour key | `-transparent` + `systemTransparent` |
| Dock / work area | `SystemParametersInfo` | `NSScreen.visibleFrame` (pyobjc); without pyobjc the Dock size is estimated from `defaults read com.apple.dock` |
| Per-monitor bounds | `MonitorFromPoint` | `NSScreen.screens()` |
| Right-click | right button | two-finger click or Ctrl-click |
| Start at login | Startup-folder script | `~/Library/LaunchAgents/com.claude-pet.plist` |
| Theme | registry | `defaults read -g AppleInterfaceStyle` |
| Login token | `~/.claude/.credentials.json` | Keychain item `Claude Code-credentials` (default folder) |

## Things most likely to need a fix

- Borderless window still shows a title bar, or is not click-through where transparent.
- The pet is not on top of the Dock or full-screen apps (window level).
- The Keychain asks for access the first time the limits feature reads the token. Choose *Always Allow* or decline (the card then shows tokens).
- A login folder added via `CLAUDE_CONFIG_DIR` may store its token in a *different* Keychain entry instead of a file, so linking extra accounts may need a code change.
