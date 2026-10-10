# Contributing

Thanks for helping! Bug reports, new pets, platform fixes (especially **macOS**) and docs are all welcome.

## Setup

```bash
git clone https://github.com/HrZizi/claude-pet.git && cd claude-pet
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest
claude-pet --demo                                # run the UI with canned data, no Claude needed
```

## Guidelines

- Keep the runtime **dependency-free** (standard library only). Dev tools (pytest, Pillow, PyInstaller) are fine in `[dev]`.
- Keep the `hook` command fast: it runs on every tool call. Do not add imports to `claude/hook.py`.
- Never read, log, store or transmit credentials beyond what `limits_api.py` already documents. No telemetry.
- Add or update tests for behaviour changes. Rendering and placement logic are pure functions on purpose.
- UI changes: include a screenshot made with `--demo` (no personal data). `python scripts/make_assets.py --screens` regenerates the README images.

## Adding a pet

The easy way (no code): make a **sprite pack**, see [docs/SPRITE_PACKS.md](docs/SPRITE_PACKS.md). `claude-pet pack new` scaffolds one and
`claude-pet pack validate` checks it. To contribute it to the built-in set, open a PR adding the folder under
`src/claude_pet/packs/` (only art you made or that is freely licensed).

The three shipped pets are *generated*: the source art is procedural code in `scripts/procedural/sprites.py`, baked into
packs with `python scripts/bake_builtin_packs.py` (a test fails if the packs and the source drift apart). Old instructions
for writing a procedural pet:

1. Write a drawing function in `src/claude_pet/art/sprites.py` (see `eevee()` as a model): paint parts with `Cv.paint`, reuse the shared `face()` for expressions, honour `ear`, `tail` and `lie`.
2. Register it in `PETS` and `DRAWERS`.
3. `python scripts/make_assets.py` regenerates the preview GIFs; `pytest` checks that every state renders.
4. Please only submit art you created yourself or that is freely licensed.

## Commits and pull requests

Small, focused PRs; describe *why*. The PR template has a short checklist.
