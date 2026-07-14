"""Companion panel geometry -- pure logic, no real Mac needed."""

from berry.companion import SPRITE_SIZE, panel_origin, scaled_size


def test_scaled_size_square_hits_target():
    assert scaled_size(32, 32, 120) == (120, 120)


def test_scaled_size_preserves_aspect_ratio_wide():
    assert scaled_size(64, 32, 120) == (120, 60)


def test_scaled_size_preserves_aspect_ratio_tall():
    assert scaled_size(32, 64, 120) == (60, 120)


def test_scaled_size_never_returns_zero():
    w, h = scaled_size(100, 1, 50)
    assert w >= 1 and h >= 1


def test_scaled_size_degenerate_input_falls_back_to_square():
    assert scaled_size(0, 0, 120) == (120, 120)


def test_panel_origin_is_horizontally_centered():
    x, _ = panel_origin(0, 0, 1440, 875, 120, 120)
    assert x == (1440 - 120) / 2


def test_panel_origin_touches_top_of_visible_area():
    # visibleFrame already excludes the menu bar, so the top of the
    # visible area is directly underneath it.
    _, y = panel_origin(0, 0, 1440, 875, 120, 120)
    assert y == 875 - 120


def test_panel_origin_respects_screen_offset():
    # secondary displays have nonzero frame origins
    x, y = panel_origin(1440, 100, 1000, 700, 120, 120)
    assert x == 1440 + (1000 - 120) / 2
    assert y == 100 + 700 - 120


def test_default_sprite_size_is_noticeably_bigger_than_menubar_icon():
    # the whole point of the companion: bigger than the 20-40px icon
    assert SPRITE_SIZE >= 100
