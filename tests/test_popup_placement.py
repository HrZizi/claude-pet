from claude_pet.ui.popup_menu import place_root, place_sub

# two monitors side by side: 0..3440 and 3440..6000 (work areas exclude the taskbar)
LEFT = (0, 0, 3440, 1392)
W, H = 260, 400


def inside(bounds, x, y, w=W, h=H):
    return bounds[0] <= x and x + w <= bounds[2] and bounds[1] <= y and y + h <= bounds[3]


def test_menu_stays_on_the_pets_monitor_even_at_the_screen_edge():
    pet = (3300, 1300, 3400, 1392)                       # pet near the right edge of the left monitor
    x, y = place_root(LEFT, W, H, cursor=(3390, 1350), avoid=pet)
    assert inside(LEFT, x, y)                            # not spilling onto the second screen


def test_menu_goes_above_the_pet_and_never_covers_it():
    pet = (1000, 1300, 1250, 1392)
    x, y = place_root(LEFT, W, H, cursor=(1010, 1350), avoid=pet)
    assert y + H <= pet[1]


def test_menu_goes_below_a_pet_docked_at_the_top():
    pet = (1000, 0, 1250, 90)
    x, y = place_root(LEFT, W, H, cursor=(1010, 40), avoid=pet)
    assert y >= pet[3]


def test_submenu_flips_left_instead_of_leaving_the_monitor():
    parent = (3150, 900, 3410, 1300)
    x, y = place_sub(LEFT, parent, row_y=60, w=W, h=200)
    assert inside(LEFT, x, y, h=200) and x < parent[0] + 10


def test_submenu_opens_to_the_right_when_there_is_room():
    parent = (500, 500, 760, 900)
    x, y = place_sub(LEFT, parent, row_y=60, w=W, h=200)
    assert x >= parent[2] - 5


def test_menu_larger_than_the_monitor_does_not_crash():
    x, y = place_root((0, 0, 200, 100), 300, 300, cursor=(50, 50), avoid=None)
    assert (x, y) == (4, 4)
