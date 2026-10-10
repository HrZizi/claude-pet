# Architecture

```text
Claude Code ──hook──▶ claude-pet hook ──▶ state.json ──▶ PetApp (Tkinter) ──▶ pixels on screen
                                                ▲
transcripts (~/.claude/projects) ─▶ usage.LocalTokens ─┤
Desktop session records ─▶ accounts.scan_desktop ──────┤
(opt-in) Anthropic usage endpoint ─▶ limits_api ───────┘
```

## Modules (`src/claude_pet/`)

| Module | Responsibility |
|---|---|
| `cli.py` / `__main__.py` | Command dispatch. The `hook` path imports almost nothing so it starts fast. |
| `app.py` | `PetApp`: borderless, always-on-top, colour-keyed Tk window; 8 fps animation loop; usage card; drag + dock-snapping; menu wiring; account selection. |
| `art/pack.py` | Sprite packs: manifest validation (types, paths, sizes), lazy PNG decoding, discovery of built-in + user packs, install from folder / zip, scaffolding. Packs are data only. |
| `art/png.py` | Dependency-free PNG reader / writer, defensive against hostile files. |
| `art/engine.py` | Turns *(pack, state, tick)* into a frame: picks the pack's frame, or derives a missing state from `idle` with motion and effects (zzz, hearts, hand, ...). Pure Python, no Tk. |
| `art/glyphs.py` | The effect glyph bitmaps. |
| `packs/` | The built-in pets as ordinary packs (generated; see below). |
| `claude/hook.py` | Writes `{session_id: {state, ts}}` to `state.json` atomically. Runs on every prompt and tool call. |
| `claude/integration.py` | Adds / removes only claude-pet entries in `~/.claude/settings.json`, with a backup. |
| `claude/accounts.py` | Detects the CLI account and Desktop accounts from local metadata and resolves which account owns a session. |
| `claude/usage.py` | Incremental transcript scanner (token totals per 5 h / 7 d window, de-duplicated, attributed per account). |
| `claude/limits_api.py` | Opt-in, read-only fetch of 5 h / weekly limits using the CLI login. |
| `ui/popup_menu.py` | Custom context menu (rounded, themed, submenus). Placement is pure functions (`place_root`, `place_sub`) confined to the pet's monitor. |
| `ui/platform_support.py` | Everything OS-specific: transparency, work area / Dock, per-monitor bounds, theme, fonts, start-at-login. |
| `paths.py` | Per-user data folder (`CLAUDE_PET_HOME` overrides). |
| `demo.py` | Canned data for `--demo`. |

## State flow

1. Claude Code fires a hook (`UserPromptSubmit` and `PostToolUse` → *working*; `Notification` for permission prompts → *attention*; `Stop` → *done*; `SessionEnd` → remove).
2. The hook merges the event into `state.json` (per session id).
3. `PetApp.summarize()` reduces all sessions to one animation state, with priority *attention > petted > working > celebrate > wants > idle/sleep*.
4. Working sessions with no event for 10 minutes are treated as stale (an interrupted turn fires no `Stop` hook).

## Rendering

The window uses a colour key (`#010203`) on Windows and real alpha on macOS. Frames are built as small `PhotoImage`s, zoomed by the chosen scale and cached by pose key.

## Why no dependencies?

Tkinter ships with Python, so the installer / zip is self-contained and the project is easy to audit: it reads and writes only the files listed in the README's privacy section.

## Sprite packs and the built-in pets

At runtime there is exactly one way to get a pet: load a sprite pack. The built-ins are not special: they live in
`src/claude_pet/packs/` and are baked from procedural source art (`scripts/procedural/sprites.py` draws shaded, outlined shapes;
`scripts/procedural/pose.py` is the old pose / laptop / effects logic) by `scripts/bake_builtin_packs.py`. Each animation is baked at
its exact loop length so it repeats seamlessly. `tests/test_builtin_packs.py` fails if the committed PNGs no longer match the source.
