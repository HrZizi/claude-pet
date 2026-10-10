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
back onto the taskbar edge when dropped near it. Right-click (styled like the card, always above the pet): account, size, usage on/off and view, preview every
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
- **Accounts are detected automatically** (no credentials touched): the CLI login from `~/.claude.json`, and
  every Claude Desktop account from the Desktop app's session records (`.../Claude/claude-code-sessions/<account id>`).
  The default mode is **Auto**: the card follows whichever account owns the session that is currently active
  (the hook's session id is matched to the Desktop record). Pin an account from right-click -> *Account*, or click
  the card's header line to cycle Auto -> each account.
- **Per-account tokens**: transcripts are attributed to the account that owns the session, so the token numbers
  are per account even though all transcripts share `~/.claude/projects`.
- **Real limits need a readable login.** The CLI login's limits work as above. The Desktop app's own login is
  encrypted by the OS and the pet does not try to read it, so a Desktop-only account shows tokens and a hint.
  To get its limits, sign that account into a Claude Code config folder once: *Account -> Add / link a login
  folder...* (copies `CLAUDE_CONFIG_DIR=<folder> claude`; run it, then `/login`). It is matched to the Desktop
  account by account id and linked automatically. Desktop accounts have no readable name or email, so they are
  called "Desktop account (xxxx)" until you rename them.
- **statusLine (CLI only)**: if your CLI statusLine passes `rate_limits`, `statusline.py` saves them and
  they are used first. The Desktop app does not run the statusLine.
- **Tokens**: tokens used locally (from `~/.claude/projects`). Set `token_budget_5h` / `token_budget_7d`
  in config.json to show them as a percentage.

## Files
pet.py (app) | popup_menu.py (context menu) | accounts.py (account detection) | platform_support.py (OS-specific bits) | limits_api.py (real limits) | sprites.py (pixel art, edit/add pets here) | render.py (animation) |
hook.py (writes state.json) | statusline.py + usage.py (usage) | install.py

## Platform support
- **Windows 10/11**: tested.
- **macOS**: implemented in `platform_support.py` but **untested** (written without a Mac). Requires Python 3
  with Tk 8.6 (python.org installer, or `brew install python-tk`). For the exact Dock position install
  `pip install pyobjc-framework-Cocoa`; without it the Dock size is estimated from its preferences.
  Use `./start.sh`, then `python3 install.py`. Right-click = two-finger click or Ctrl-click. If the pet
  appears with a black/opaque background or can't be clicked, that's the first thing to report.
