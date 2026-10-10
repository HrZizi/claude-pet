# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Custom sprite packs.** Any folder with a `pack.json` and PNG strips is a pet: right-click → Pet → Add sprite pack / Open sprite
  packs folder, or `claude-pet pack new | validate | install | export | list`. Packs are data only (no code), validated, and
  size-limited. A pack with just an `idle` animation gets sleeping, working, distressed, celebrating, wanting-a-pet and petted
  behaviour from the engine. See `docs/SPRITE_PACKS.md`.
- Dependency-free PNG reader / writer (all colour types, bit depths and filters).

### Changed
- The built-in Claude, Eevee and Bulbasaur are now ordinary sprite packs, baked from their procedural source art
  (moved to `scripts/procedural`). Animations are baked as exact loops, so a few timings (idle, working) were simplified.

## [0.1.1] - 2026-10-10

### Fixed
- A menu *Preview animation* choice now expires after 20 seconds. Previously it overrode what Claude was really doing indefinitely
  and invisibly (e.g. leaving "Asleep" selected made the pet look broken while sessions were running).
- The installer / uninstaller only stop and remove the copy in their own folder (and that copy's Start menu shortcut and *Apps* entry), not another running or installed copy.

## [0.1.0] - 2026-10-10

### Added
- Animated pixel-art pets (Claude, Eevee, Bulbasaur) reacting to Claude Code: asleep, working, distraught, done, wants-a-pet, petted.
- Usage card with 5-hour / weekly limits (opt-in) and per-account token counts; rotate / limits / tokens views.
- Automatic detection of CLI and Claude Desktop accounts; Auto mode follows the active session; link a CLI login to a Desktop account.
- Taskbar / Dock docking with free dragging, multi-monitor aware; styled always-on-top context menu confined to one monitor.
- `claude-pet` CLI (`install`, `uninstall`, `limits`, `doctor`, `--demo`), PyInstaller build, self-contained Windows installer + uninstaller, portable zip, pixel-art app icon.
- macOS support layer (untested).
