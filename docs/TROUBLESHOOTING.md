# Troubleshooting

Run `claude-pet doctor` first. It prints versions, the data folder, whether the hooks are installed and which accounts were found (never tokens).

**The pet never reacts to Claude**
- `doctor` should say `hooks installed`. If not: right-click → *Connect to Claude Code*, or `claude-pet install`.
- Hooks are read when a session starts: restart open Claude Code / Desktop sessions.
- Check that `state.json` in the data folder updates when you send a prompt.

**Stuck on "working"**
Pressing Esc mid-turn fires no `Stop` hook. The pet clears a working session after 10 minutes of silence.

**Card shows tokens instead of limits**
Turn on *Fetch real limits*. If it still shows tokens: the account has no readable login (Desktop-only account: link a CLI login, see [ACCOUNTS.md](ACCOUNTS.md)), or the token expired; open Claude Code once so it refreshes the token.

**Wrong account shown**
The header names the account. In *Auto* mode it follows the active session; pin another account from *Account* in the menu.

**Pet is hidden / off-screen**
Right-click → *Snap to taskbar / Dock*. If you cannot reach it, delete `config.json` in the data folder.

**Context menu appears on another monitor**
Menus are confined to the pet's monitor. If you see otherwise, please open an issue with the output of `doctor`.

**Windows SmartScreen warning**
The executables are unsigned. Choose *More info → Run anyway*, or build from source.

**Uninstall**
`claude-pet uninstall` removes the hooks, then remove the app. The installer's uninstaller also removes the hooks. Delete the data folder to remove settings.
