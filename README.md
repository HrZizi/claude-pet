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
    start.bat               # runs the pet (macOS/Linux: ./start.sh) (or right-click -> Start with Windows)
    python install.py --uninstall

Restart open Claude sessions after installing so they load the hooks.

## Usage card
Click the card (or right-click -> Usage view) to switch between **limits**, **tokens** or **rotate**.
- **Real limits (5h / weekly %)**: right-click -> *Fetch real limits from Anthropic*. Opt-in. It reads the
  login token that **Claude Code (the CLI)** stored in its config folder (`~/.claude/.credentials.json`; macOS
  Keychain item "Claude Code-credentials") and makes one read-only request every 3 minutes to
  `api.anthropic.com/api/oauth/usage`, the data behind `/usage`. The token is never stored, logged or refreshed
  by the pet. Undocumented endpoint, may change. Check with `python limits_api.py [config_folder]`.
  **The Claude Desktop app keeps its own separate login, which the pet cannot read.** So the limits are those of
  whichever account the CLI is logged into; the card header always names the account and plan it is showing.
- **Several accounts**: right-click -> *Account* -> *Add account...* (name + a config folder). Each account is a
  Claude Code config folder logged in once with `CLAUDE_CONFIG_DIR=<folder> claude` then `/login` (the dialog
  copies that command for you). Switch with the *Account* menu, or just click the card's header line.
  Tokens are always "this PC": transcripts from every account on the machine are mixed together.
- **statusLine (CLI only)**: if your CLI statusLine passes `rate_limits`, `statusline.py` saves them and
  they are used first. The Desktop app does not run the statusLine.
- **Tokens**: tokens used locally (from `~/.claude/projects`). Set `token_budget_5h` / `token_budget_7d`
  in config.json to show them as a percentage.

## Files
pet.py (app) | platform_support.py (OS-specific bits) | limits_api.py (real limits) | sprites.py (pixel art, edit/add pets here) | render.py (animation) |
hook.py (writes state.json) | statusline.py + usage.py (usage) | install.py

## Platform support
- **Windows 10/11**: tested.
- **macOS**: implemented in `platform_support.py` but **untested** (written without a Mac). Requires Python 3
  with Tk 8.6 (python.org installer, or `brew install python-tk`). For the exact Dock position install
  `pip install pyobjc-framework-Cocoa`; without it the Dock size is estimated from its preferences.
  Use `./start.sh`, then `python3 install.py`. Right-click = two-finger click or Ctrl-click. If the pet
  appears with a black/opaque background or can't be clicked, that's the first thing to report.
