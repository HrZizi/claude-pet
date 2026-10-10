# Sprite packs

A **sprite pack** is a folder that gives Claude Pet a new pet: a `pack.json` manifest plus PNG sprite strips. Packs are
**data only** (never code), so installing one from someone else cannot run anything on your machine. The three shipped
pets (Claude, Eevee, Bulbasaur) are ordinary packs too; see [`src/claude_pet/packs`](../src/claude_pet/packs).

## Quick start

```bash
claude-pet pack new my-pet --name "My Pet"     # scaffold a working pack (a little blob)
# ... edit my-pet/idle.png, add more states ...
claude-pet pack validate my-pet                # check it
claude-pet pack install my-pet                 # copy it into your packs folder
```

Then right-click the pet → **Pet → Reload sprite packs** and choose it. Or drop the folder into your packs folder
(right-click → **Pet → Open sprite packs folder**) and reload. Start from a shipped pet instead:
`claude-pet pack export eevee my-eevee`.

## Layout

```text
my-pet/
  pack.json        the manifest
  idle.png         one PNG "strip" per state: the frames side by side
  working.png
  ...
```

### `pack.json`

```json
{
  "format": 1,
  "name": "My Pet",
  "author": "Your Name",
  "license": "CC0-1.0",
  "description": "A very good blob.",
  "frame": [24, 24],
  "effects": true,
  "states": {
    "idle":    { "file": "idle.png",    "fps": 4 },
    "working": { "file": "working.png", "fps": 8 }
  }
}
```

| Field | Required | Meaning |
|---|---|---|
| `format` | yes | Always `1`. |
| `name` | recommended | Shown in the menu (1-40 characters). Defaults to the folder name. |
| `author`, `license`, `description` | no | Informational. Please set a `license` if you share the pack. |
| `frame` | yes | `[width, height]` in pixels of **one frame**, 1-128 each. Every state uses the same frame size. |
| `effects` | no (default `true`) | Let the engine draw effects (zzz, hearts, ...) and motion on top. Set `false` if your frames already contain everything (the shipped pets do). |
| `states` | yes | Must contain `idle`. See below. |

Each state is `{ "file": "<name>.png", "fps": <1-8>, "motion": <bool>, "effects": <bool> }`:

- `file`: a `.png` inside the pack folder (no `..`, no absolute paths).
- `fps` (default 4): frames per second, 1 to 8. The app animates at 8 ticks per second, so `8` shows every frame each
  tick, `4` holds each frame for 2 ticks, `2` for 4.
- `motion` / `effects` (optional): override the pack-level behaviour for this state (see [How the engine fills in gaps](#how-the-engine-fills-in-gaps)).

## Sprite strips

- A strip is **all frames of a state side by side**: width = `frame width x number of frames`, height = `frame height`.
  The number of frames is worked out from the image width.
- **Transparency**: pixels with alpha below 50% are transparent; everything else is drawn fully opaque. There is no
  semi-transparency (the window has no anti-aliased edges), so draw pixel art with hard edges.
- **Alignment**: the pet stands on the bottom edge of the window, so keep the feet on the **bottom row** and centre
  the sprite horizontally. Leave a pixel or two of space at the sides if the pet moves.
- **Size**: 24-32 px works well; the app scales up with nearest-neighbour (size menu: 2x to 5x). Larger frames are
  allowed but become big on screen.
- **Format**: any non-interlaced PNG (8/16-bit RGBA, RGB, grey, indexed). Interlaced PNGs are rejected with a message.

Exporting from common tools: in **Aseprite** use *File → Export Sprite Sheet* with *Layout: Horizontal Strip* and no
padding; **LibreSprite** is the same; **Piskel** exports a horizontal PNG strip directly.

## States

| State | Shown when | If your pack has no strip for it, the engine... |
|---|---|---|
| `idle` | awake and calm (**required**) | (this is the base for all missing states) |
| `sleep` | nothing has happened for 20 s | shows `idle` with floating *zzz* |
| `working` | Claude is working | shows `idle` with a typing "..." bubble |
| `attention` | Claude needs you (permission prompt) | shows `idle`, shaking, with a sweat drop and "!" |
| `celebrate` | Claude just finished (about 4 s) | shows `idle`, hopping and mirroring, with sparkles |
| `wants` | finished, waiting to be petted (up to 2 min) | shows `idle` with hearts and a hopeful bounce |
| `petted` | you clicked the pet | shows `idle` wobbling, with a petting hand and hearts |

So a pack with only `idle` already behaves like a complete pet. Add strips for the states you want to draw yourself.

## How the engine fills in gaps

- A state you provide is played as drawn. By default **no** motion is added to it, and the engine draws effect glyphs on
  top only if the pack-level `"effects"` is `true`.
- A state you do **not** provide is derived from `idle` with motion **and** effects (unless `"effects": false`, which
  then only gives you the motion).
- A per-state `"motion"` / `"effects"` overrides the defaults, for example `"celebrate": { "file": "cheer.png", "motion": true }`
  keeps your drawing but adds the hop.
- Effect glyphs are placed relative to the top of your sprite, centred for a 24 px wide sprite.
- With effects or derived states the window gets a little extra room around the frame (4 px at the sides, 8 px on top) so
  nothing is clipped. A pack that provides all seven states with `"effects": false` gets no extra room.

## Installing and sharing

| | |
|---|---|
| Install from the menu | right-click → **Pet → Add sprite pack...** and choose a `.zip` |
| Install from the CLI | `claude-pet pack install <folder or .zip>` |
| Manual | copy the folder into the packs folder: `%LOCALAPPDATA%\ClaudePet\packs` (Windows), `~/Library/Application Support/ClaudePet/packs` (macOS), `~/.local/share/claude-pet/packs` (Linux). `claude-pet pack folder` prints it. |
| Share | zip the folder (with `pack.json` at the top, or inside a single folder) |

A custom pack with the same folder name as a shipped pet **replaces** it. Use a different name unless that is what you want.
Invalid packs are skipped; the menu shows why and `claude-pet pack list` / `claude-pet doctor` print the details.

## Limits and safety

Packs are validated before use: manifest fields and types, file paths that stay inside the pack, frame sizes, a cap of
600 frames per state and 8 MB per file, and PNGs are size-checked before they are decoded (decompression-bomb safe).
Zip files are checked for unsafe paths and size before extraction. A pack can only change how the pet *looks*.

## Licensing

Only share art you made or have the rights to. Fan art of existing characters is yours to share at your own risk; it is
not covered by this project's MIT license. Put the license of your art in `pack.json`.
