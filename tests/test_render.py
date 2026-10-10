import pytest

from claude_pet.art import render, sprites

STATES = ["sleep", "idle", "working", "attention", "celebrate", "wants", "petted"]


@pytest.mark.parametrize("pet", sorted(sprites.PETS))
@pytest.mark.parametrize("state", STATES)
def test_every_pet_renders_every_state(pet, state):
    for tick in range(0, 60, 7):
        g = render.grid(render.pose(pet, state, tick))
        assert len(g) == render.GH and all(len(row) == render.GW for row in g)
        assert any(c != render.KEY for row in g for c in row), "frame is empty"


@pytest.mark.parametrize("pet", sorted(sprites.PETS))
def test_sprite_fits_canvas(pet):
    px = sprites.draw(pet)
    assert px and all(0 <= x < sprites.W and 0 <= y < sprites.H for x, y in px)


def test_pose_is_hashable_and_deterministic():
    a = render.pose("eevee", "working", 5)
    assert a == render.pose("eevee", "working", 5)
    hash(a)


def test_working_pet_has_laptop_and_sleeping_pet_lies_down():
    assert dict(render.pose("claude", "working", 0)[1])["laptop"] is not None
    assert dict(render.pose("claude", "sleep", 0)[1])["lie"] is True
