"""Sprite packs: how pets are described, validated, found and installed.

A pack is a folder of *data only* (a `pack.json` manifest plus PNG sprite strips), never code, so installing a pack
from someone else cannot run anything. The three built-in pets are ordinary packs (see `src/claude_pet/packs`).
Format reference: docs/SPRITE_PACKS.md
"""
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from .. import paths
from . import png

FORMAT = 1
STATES = ("sleep", "idle", "working", "attention", "celebrate", "wants", "petted")
MAX_FRAME = 128                     # px, width and height of one frame
MAX_FRAMES = 600                    # frames per state
MAX_FILE_BYTES = 8_000_000
MAX_ZIP_BYTES, MAX_ZIP_FILES = 50_000_000, 400
BUILTIN_ORDER = ("claude", "eevee", "bulbasaur")
TICKS_PER_SECOND = 8                # the app's animation clock (125 ms per tick)


class PackError(ValueError):
    """A pack is invalid. The message names the pack and the problem, for the pack author."""


class StateAnim:
    def __init__(self, name, path, fps, count, motion, effects):
        self.name, self.path, self.fps, self.count = name, path, fps, count
        self.hold = max(1, round(TICKS_PER_SECOND / fps))     # app ticks each frame is shown
        self.motion, self.effects = motion, effects            # None = decide automatically


class Pack:
    def __init__(self, pid, root, builtin, meta, frame_w, frame_h, effects, states):
        self.id, self.root, self.builtin = pid, Path(root), builtin
        self.name, self.author = meta["name"], meta.get("author", "")
        self.license, self.description = meta.get("license", ""), meta.get("description", "")
        self.frame_w, self.frame_h, self.effects, self.states = frame_w, frame_h, effects, states
        self.warnings = []
        self._cache = {}

    @property
    def uses_effects(self):
        """True when the engine may draw outside the frame (effects, or motion for states the pack lacks)."""
        return bool(self.effects or len(self.states) < len(STATES)
                    or any(a.effects or a.motion for a in self.states.values()))

    def frames(self, state):
        """Decoded frames of one state (a list of frames; a frame is rows of '#rrggbb' or None)."""
        if state not in self._cache:
            self._cache[state] = self._decode(self.states[state])
        return self._cache[state]

    def _decode(self, anim):
        try:
            w, h, rgba = png.read_png(anim.path.read_bytes())
        except png.PngError as e:
            raise PackError("%s: %s: %s" % (self.id, anim.path.name, e))
        if h != self.frame_h or w != self.frame_w * anim.count:
            raise PackError("%s: %s changed size while loading" % (self.id, anim.path.name))
        frames = []
        for f in range(anim.count):
            rows = []
            for y in range(h):
                base = (y * w + f * self.frame_w) * 4
                row = []
                for x in range(self.frame_w):
                    i = base + x * 4
                    row.append(None if rgba[i + 3] < 128 else "#%02X%02X%02X" % (rgba[i], rgba[i + 1], rgba[i + 2]))
                rows.append(row)
            frames.append(rows)
        return frames

    def decode_all(self):
        for s in self.states:
            self.frames(s)


def _slug(text):
    s = re.sub(r"[^a-z0-9_-]+", "-", text.lower()).strip("-")
    return s or "pack"


def _num(v, name, lo, hi, pid):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise PackError("%s: %s must be a number from %g to %g" % (pid, name, lo, hi))
    return v


def load(root, builtin=False):
    """Read and validate a pack folder (PNG headers are checked now; pixels are decoded on first use)."""
    root = Path(root)
    pid = _slug(root.name)
    mf = root / "pack.json"
    if not mf.is_file():
        raise PackError("%s: no pack.json found" % pid)
    try:
        m = json.loads(mf.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise PackError("%s: pack.json is not valid JSON (%s)" % (pid, e))
    if not isinstance(m, dict):
        raise PackError("%s: pack.json must contain an object" % pid)
    if m.get("format") != FORMAT:
        raise PackError("%s: \"format\" must be %d (this version of claude-pet reads format %d)" % (pid, FORMAT, FORMAT))
    name = m.get("name") or root.name
    if not isinstance(name, str) or not 1 <= len(name) <= 40:
        raise PackError("%s: \"name\" must be 1-40 characters" % pid)
    for k in ("author", "license", "description"):
        if k in m and not isinstance(m[k], str):
            raise PackError("%s: \"%s\" must be text" % (pid, k))
    fr = m.get("frame")
    if not (isinstance(fr, list) and len(fr) == 2):
        raise PackError("%s: \"frame\" must be [width, height] in pixels, e.g. [24, 24]" % pid)
    fw, fh = int(_num(fr[0], "frame width", 1, MAX_FRAME, pid)), int(_num(fr[1], "frame height", 1, MAX_FRAME, pid))
    effects = m.get("effects", True)
    if not isinstance(effects, bool):
        raise PackError("%s: \"effects\" must be true or false" % pid)
    raw = m.get("states")
    if not isinstance(raw, dict) or "idle" not in raw:
        raise PackError("%s: \"states\" must be an object that at least contains \"idle\"" % pid)

    states, warnings = {}, []
    for sname, spec in raw.items():
        if sname not in STATES:
            warnings.append("unknown state \"%s\" ignored (known: %s)" % (sname, ", ".join(STATES)))
            continue
        if not isinstance(spec, dict) or not isinstance(spec.get("file"), str):
            raise PackError("%s: state \"%s\" needs a \"file\"" % (pid, sname))
        rel = Path(spec["file"])
        if rel.is_absolute() or ".." in rel.parts or rel.suffix.lower() != ".png":
            raise PackError("%s: state \"%s\": file must be a .png path inside the pack folder" % (pid, sname))
        path = (root / rel).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            raise PackError("%s: state \"%s\": file points outside the pack folder" % (pid, sname))
        if not path.is_file():
            raise PackError("%s: state \"%s\": file \"%s\" not found" % (pid, sname, spec["file"]))
        if path.stat().st_size > MAX_FILE_BYTES:
            raise PackError("%s: %s is larger than %d MB" % (pid, spec["file"], MAX_FILE_BYTES // 1_000_000))
        fps = _num(spec.get("fps", 4), "fps of state \"%s\"" % sname, 1, TICKS_PER_SECOND, pid)
        for flag in ("motion", "effects"):
            if flag in spec and not isinstance(spec[flag], bool):
                raise PackError("%s: state \"%s\": \"%s\" must be true or false" % (pid, sname, flag))
        try:
            w, h = png.read_size(path.read_bytes())
        except png.PngError as e:
            raise PackError("%s: %s: %s" % (pid, spec["file"], e))
        if h != fh:
            raise PackError("%s: %s is %d px tall but the frame height is %d" % (pid, spec["file"], h, fh))
        if w % fw:
            raise PackError("%s: %s is %d px wide, which is not a multiple of the frame width %d"
                            % (pid, spec["file"], w, fw))
        count = w // fw
        if not 1 <= count <= MAX_FRAMES:
            raise PackError("%s: %s has %d frames (1-%d allowed)" % (pid, spec["file"], count, MAX_FRAMES))
        states[sname] = StateAnim(sname, path, fps, count, spec.get("motion"), spec.get("effects"))
    pack = Pack(pid, root, builtin, dict(m, name=name), fw, fh, effects, states)
    pack.warnings = warnings
    return pack


def validate(root):
    """Load a pack and decode every frame. Returns the pack (check .warnings); raises PackError."""
    pack = load(root)
    pack.decode_all()
    return pack


def builtin_dir():
    return Path(__file__).resolve().parent.parent / "packs"


def user_dir():
    d = paths.data_dir() / "packs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def discover(extra=()):
    """-> ({id: Pack}, [(folder, error message)]). Built-in packs first; a user pack with the same id replaces it."""
    found, errors = {}, []
    roots = [(builtin_dir(), True), (user_dir(), False)] + [(Path(e), False) for e in extra]
    for base, builtin in roots:
        if not base.is_dir():
            continue
        for d in sorted(p for p in base.iterdir() if p.is_dir() and (p / "pack.json").exists()):
            try:
                found[_slug(d.name)] = load(d, builtin)
            except PackError as e:
                errors.append((str(d), str(e)))
    order = {pid: i for i, pid in enumerate(BUILTIN_ORDER)}
    ordered = dict(sorted(found.items(), key=lambda kv: (not kv[1].builtin, order.get(kv[0], 99), kv[1].name.lower())))
    return ordered, errors


def _safe_extract(zpath, dest):
    with zipfile.ZipFile(zpath) as z:
        infos = z.infolist()
        if len(infos) > MAX_ZIP_FILES or sum(i.file_size for i in infos) > MAX_ZIP_BYTES:
            raise PackError("zip file is too large for a sprite pack")
        for i in infos:
            n = Path(i.filename)
            if n.is_absolute() or ".." in n.parts:
                raise PackError("zip file contains an unsafe path: %s" % i.filename)
        z.extractall(dest)


def _find_root(folder):
    folder = Path(folder)
    if (folder / "pack.json").exists():
        return folder
    subs = [p for p in folder.iterdir() if p.is_dir() and (p / "pack.json").exists()]
    if len(subs) == 1:
        return subs[0]
    raise PackError("no pack.json found (it must be at the top of the zip, or inside one folder)")


def install(src, overwrite=False):
    """Validate a pack folder or .zip and copy it into the user's packs folder. Returns the installed Pack."""
    src = Path(src)
    tmp = Path(tempfile.mkdtemp(prefix="claude-pet-pack-"))
    try:
        if src.is_file():
            if src.suffix.lower() != ".zip":
                raise PackError("choose a sprite pack folder or a .zip file")
            _safe_extract(src, tmp / "x")
            root = _find_root(tmp / "x")
        else:
            root = _find_root(src)
        pack = validate(root)
        dest = user_dir() / _slug(pack.name)
        if dest.exists():
            if not overwrite:
                raise PackError("a pack called '%s' is already installed" % dest.name)
            shutil.rmtree(dest)
        shutil.copytree(root, dest)
        return load(dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def export_builtin(pid, dest):
    """Copy a built-in pack out as an editable starting point for your own."""
    src = builtin_dir() / pid
    if not (src / "pack.json").exists():
        raise PackError("there is no built-in pack called '%s'" % pid)
    dest = Path(dest)
    if dest.exists():
        raise PackError("%s already exists" % dest)
    shutil.copytree(src, dest)
    return dest


def _blob_frame(w, h, bob):
    """A 16x16 green blob with two eyes; `bob` shifts it down a pixel for the second animation frame."""
    rgba = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            dy = y - (10 + bob)
            if ((x + .5 - 8) / 6.5) ** 2 + (dy / 5.0) ** 2 <= 1 and y < h - 1:
                eye = x in (5, 10) and dy in (-2, -1)
                rim = dy > 3
                color = (40, 40, 48) if eye else ((70, 150, 95) if rim else (96, 190, 120))
                i = (y * w + x) * 4
                rgba[i:i + 4] = bytes(color) + b"\xff"
    return bytes(rgba)


def scaffold(dest, name="My Pet"):
    """Create a minimal working pack (a two-frame blob) to start from."""
    dest = Path(dest)
    if dest.exists():
        raise PackError("%s already exists" % dest)
    dest.mkdir(parents=True)
    w, h = 16, 16
    frames = [_blob_frame(w, h, bob) for bob in (0, 1)]
    strip = bytearray(w * 2 * h * 4)
    for f, fr in enumerate(frames):
        for y in range(h):
            strip[(y * w * 2 + f * w) * 4:(y * w * 2 + f * w + w) * 4] = fr[y * w * 4:(y + 1) * w * 4]
    (dest / "idle.png").write_bytes(png.write_png(w * 2, h, bytes(strip)))
    manifest = {
        "format": FORMAT, "name": name, "author": "", "license": "CC0-1.0",
        "description": "Edit the PNGs and add more states: see docs/SPRITE_PACKS.md",
        "frame": [w, h], "effects": True,
        "states": {"idle": {"file": "idle.png", "fps": 2}},
    }
    (dest / "pack.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return dest
