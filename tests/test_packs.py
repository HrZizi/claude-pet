import json
import zipfile

import pytest

from claude_pet.art import engine, pack
from pngutil import solid, write_pack

RED, BLUE = (200, 40, 40), (40, 40, 200)


def idle_only(root, **kw):
    return write_pack(root, {"idle": [solid(RED), solid(BLUE)]}, **kw)


# ------------------------------------------------------------------ loading and validation
def test_minimal_pack_loads_and_decodes(tmp_path):
    pk = pack.validate(idle_only(tmp_path / "mini"))
    assert (pk.id, pk.name, pk.frame_w, pk.frame_h) == ("mini", "Test Pet", 8, 8)
    assert pk.states["idle"].count == 2
    assert pk.frames("idle")[0][0][0] == "#C82828" and pk.frames("idle")[1][0][0] == "#2828C8"


def test_transparent_pixels_become_none(tmp_path):
    pk = pack.validate(write_pack(tmp_path / "t", {"idle": [solid(RED, shape=lambda x, y: x < 4)]}))
    row = pk.frames("idle")[0][0]
    assert row[:4] == ["#C82828"] * 4 and row[4:] == [None] * 4


@pytest.mark.parametrize("mutate, message", [
    (lambda m: m.update(format=2), "format"),
    (lambda m: m.pop("frame"), "frame"),
    (lambda m: m.update(frame=[0, 8]), "frame width"),
    (lambda m: m.update(frame=[999, 8]), "frame width"),
    (lambda m: m.update(states={}), "idle"),
    (lambda m: m.update(effects="yes"), "effects"),
    (lambda m: m["states"]["idle"].update(file="missing.png"), "not found"),
    (lambda m: m["states"]["idle"].update(file="../outside.png"), "the pack folder"),
    (lambda m: m["states"]["idle"].update(file="/etc/passwd.png"), "the pack folder"),
    (lambda m: m["states"]["idle"].update(file="idle.txt"), ".png"),
    (lambda m: m["states"]["idle"].update(fps=0), "fps"),
    (lambda m: m["states"]["idle"].update(fps=60), "fps"),
    (lambda m: m["states"]["idle"].update(motion="yes"), "motion"),
    (lambda m: m.update(frame=[5, 8]), "multiple of the frame width"),
    (lambda m: m.update(frame=[8, 9]), "tall"),
])
def test_invalid_manifests_give_a_clear_error(tmp_path, mutate, message):
    root = idle_only(tmp_path / "bad")
    m = json.loads((root / "pack.json").read_text())
    mutate(m)
    (root / "pack.json").write_text(json.dumps(m))
    with pytest.raises(pack.PackError, match=message):
        pack.load(root)


def test_not_json_and_missing_manifest(tmp_path):
    (tmp_path / "a").mkdir()
    with pytest.raises(pack.PackError, match="no pack.json"):
        pack.load(tmp_path / "a")
    (tmp_path / "a" / "pack.json").write_text("{nope")
    with pytest.raises(pack.PackError, match="not valid JSON"):
        pack.load(tmp_path / "a")


def test_not_actually_a_png_is_reported(tmp_path):
    root = idle_only(tmp_path / "fake")
    (root / "idle.png").write_bytes(b"this is text, not a png")
    with pytest.raises(pack.PackError, match="not a PNG"):
        pack.load(root)


def test_unknown_states_are_ignored_with_a_warning(tmp_path):
    root = idle_only(tmp_path / "w")
    m = json.loads((root / "pack.json").read_text())
    m["states"]["dancing"] = m["states"]["idle"]
    (root / "pack.json").write_text(json.dumps(m))
    pk = pack.validate(root)
    assert "dancing" not in pk.states and any("dancing" in w for w in pk.warnings)


def test_symlink_escaping_the_pack_is_refused(tmp_path):
    outside = idle_only(tmp_path / "outside")
    root = idle_only(tmp_path / "evil")
    (root / "idle.png").unlink()
    try:
        (root / "idle.png").symlink_to(outside / "idle.png")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available")
    with pytest.raises(pack.PackError, match="outside the pack folder"):
        pack.load(root)


# ------------------------------------------------------------------ engine behaviour
def test_provided_state_is_used_and_fps_sets_the_hold(tmp_path):
    root = write_pack(tmp_path / "p", {"idle": [solid(RED)], "working": [solid(BLUE), solid(RED)]},
                      manifest_states={"idle": {"file": "idle.png", "fps": 8}, "working": {"file": "working.png", "fps": 2}})
    pk = pack.load(root)
    assert pk.states["working"].hold == 4                                  # 8 ticks/s at 2 fps
    used = [engine.pose(pk, "working", t)[:2] for t in range(8)]
    assert used == [("working", 0)] * 4 + [("working", 1)] * 4


def test_missing_state_is_derived_from_idle_with_motion_and_effects(tmp_path):
    pk = pack.load(idle_only(tmp_path / "d"))
    for state in pack.STATES:                                              # every state renders
        g = engine.grid(pk, engine.pose(pk, state, 3))
        assert len(g) == engine.grid_size(pk)[1] and len(g[0]) == engine.grid_size(pk)[0]
    k = engine.pose(pk, "sleep", 0)
    assert k[0] == "idle" and k[5], "sleep should reuse idle and add the zzz effect"
    assert engine.pose(pk, "attention", 0)[2] != engine.pose(pk, "attention", 1)[2], "attention shakes"


def test_effects_false_pack_draws_exactly_its_own_pixels(tmp_path):
    states = {s: [solid(RED)] for s in pack.STATES}
    pk = pack.load(write_pack(tmp_path / "full", states, effects=False))
    assert engine.grid_size(pk) == (8, 8)                                  # no padding when it draws everything
    for s in pack.STATES:
        key = engine.pose(pk, s, 5)
        assert key[2:] == (0, 0, False, ())
        assert all(c == "#C82828" for row in engine.grid(pk, key) for c in row)


def test_effects_and_motion_can_be_overridden_per_state(tmp_path):
    states = {"idle": [solid(RED)], "celebrate": [solid(BLUE)]}
    ms = {"idle": {"file": "idle.png"}, "celebrate": {"file": "celebrate.png", "motion": True, "effects": True}}
    pk = pack.load(write_pack(tmp_path / "o", states, effects=False, manifest_states=ms))
    key = engine.pose(pk, "celebrate", 2)
    assert key[0] == "celebrate" and key[3] != 0 and key[5]                # own frames, plus hop and sparkles


def test_mirror_flips_the_picture(tmp_path):
    pk = pack.load(write_pack(tmp_path / "m", {"idle": [solid(RED, shape=lambda x, y: x < 2)]}))
    g = engine.grid(pk, ("idle", 0, 0, 0, True, ()))
    px, _ = engine.pads(pk)
    assert g[engine.pads(pk)[1]][px + 7] == "#C82828" and g[engine.pads(pk)[1]][px] == engine.KEY


# ------------------------------------------------------------------ discovery
def test_discover_finds_builtin_and_user_packs_and_reports_broken_ones(tmp_path):
    user = pack.user_dir()
    idle_only(user / "mine", name="Mine")
    broken = idle_only(user / "broken")
    (broken / "idle.png").write_bytes(b"x")
    found, errors = pack.discover()
    assert {"claude", "eevee", "bulbasaur"} <= set(found) and "mine" in found
    assert list(found)[:3] == ["claude", "eevee", "bulbasaur"]            # built-ins first, in their usual order
    assert any("broken" in e[0] for e in errors) and "broken" not in found
    assert found["mine"].builtin is False


def test_user_pack_can_replace_a_builtin_of_the_same_id():
    idle_only(pack.user_dir() / "eevee", name="Custom Eevee")
    found, _ = pack.discover()
    assert found["eevee"].name == "Custom Eevee" and not found["eevee"].builtin


# ------------------------------------------------------------------ install / scaffold / export
def test_install_from_folder_and_overwrite(tmp_path):
    src = idle_only(tmp_path / "src", name="Fresh Fox")
    pk = pack.install(src)
    assert pk.id == "fresh-fox" and (pack.user_dir() / "fresh-fox" / "idle.png").exists()
    with pytest.raises(pack.PackError, match="already installed"):
        pack.install(src)
    assert pack.install(src, overwrite=True).id == "fresh-fox"


def make_zip(path, root, prefix=""):
    with zipfile.ZipFile(path, "w") as z:
        for f in root.rglob("*"):
            if f.is_file():
                z.write(f, prefix + f.relative_to(root).as_posix())
    return path


def test_install_from_zip_with_or_without_a_top_folder(tmp_path):
    src = idle_only(tmp_path / "src", name="Zip Pet")
    assert pack.install(make_zip(tmp_path / "flat.zip", src)).id == "zip-pet"
    assert pack.install(make_zip(tmp_path / "nested.zip", src, "Zip Pet/"), overwrite=True).id == "zip-pet"


def test_zip_slip_and_junk_are_rejected(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../evil.txt", "x")
        z.writestr("pack.json", "{}")
    with pytest.raises(pack.PackError, match="unsafe path"):
        pack.install(bad)
    with pytest.raises(pack.PackError, match="no pack.json"):
        empty = tmp_path / "e.zip"
        with zipfile.ZipFile(empty, "w") as z:
            z.writestr("readme.txt", "hi")
        pack.install(empty)
    (tmp_path / "x.txt").write_text("not a pack")
    with pytest.raises(pack.PackError, match="folder or a .zip"):
        pack.install(tmp_path / "x.txt")
    assert not (tmp_path / "evil.txt").exists()


def test_install_validates_before_copying_anything(tmp_path):
    src = idle_only(tmp_path / "src", name="Half Broken")
    (src / "idle.png").write_bytes(b"nope")
    with pytest.raises(pack.PackError):
        pack.install(src)
    assert not (pack.user_dir() / "half-broken").exists()


def test_scaffold_is_a_valid_pack_and_export_builtin_roundtrips(tmp_path):
    pk = pack.validate(pack.scaffold(tmp_path / "new", "Brand New"))
    assert pk.name == "Brand New" and "idle" in pk.states
    with pytest.raises(pack.PackError, match="already exists"):
        pack.scaffold(tmp_path / "new")
    out = pack.export_builtin("eevee", tmp_path / "eevee-copy")
    assert len(pack.validate(out).states) == 7
    with pytest.raises(pack.PackError, match="no built-in"):
        pack.export_builtin("nope", tmp_path / "x")
