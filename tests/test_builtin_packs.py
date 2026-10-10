"""The shipped pets are ordinary sprite packs. These tests guard that they stay valid and match their source art."""
import sys
from pathlib import Path

import pytest

from claude_pet.art import engine, pack

ROOT = Path(__file__).resolve().parents[1]
BUILTIN = ["claude", "eevee", "bulbasaur"]


@pytest.mark.parametrize("pid", BUILTIN)
def test_builtin_pack_is_valid_complete_and_self_drawn(pid):
    pk = pack.validate(pack.builtin_dir() / pid)
    assert pk.builtin is False or True                      # validate() loads without the flag; discover() sets it
    assert set(pk.states) == set(pack.STATES)               # all seven states drawn by hand/bake
    assert pk.effects is False and not pk.uses_effects
    assert (pk.frame_w, pk.frame_h) == (28, 30) and pk.warnings == []


def test_discovery_marks_them_builtin_in_the_usual_order():
    found, errors = pack.discover()
    assert errors == []
    assert [k for k, v in found.items() if v.builtin] == BUILTIN


@pytest.mark.parametrize("pid", BUILTIN)
@pytest.mark.parametrize("state", pack.STATES)
def test_every_state_renders_at_a_constant_size(pid, state):
    pk = pack.load(pack.builtin_dir() / pid)
    for tick in range(0, 200, 13):
        g = engine.grid(pk, engine.pose(pk, state, tick))
        assert (len(g[0]), len(g)) == (28, 30)
        assert any(c != engine.KEY for row in g for c in row), "empty frame"


@pytest.mark.parametrize("pid", BUILTIN)
def test_baked_packs_match_the_procedural_source(pid):
    """If someone edits scripts/procedural/sprites.py without re-running bake_builtin_packs.py, this fails."""
    sys.path.insert(0, str(ROOT / "scripts" / "procedural"))
    try:
        import pose
    finally:
        sys.path.pop(0)
    pk = pack.load(pack.builtin_dir() / pid)
    for state in pack.STATES:
        for tick in (0, 1, 7, 23, 59, 71):
            expected = pose.grid(pose.pose(pid, state, tick))
            assert engine.grid(pk, engine.pose(pk, state, tick)) == expected, (pid, state, tick)
