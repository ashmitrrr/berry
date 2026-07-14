"""Hover hit-testing for the notch panel -- pure arithmetic, no real Mac needed.

find_status_button() isn't covered here: it's a thin, defensive attribute
lookup against rumps/AppKit objects that don't exist off of a real Mac,
and its only real failure mode (rumps changes its internal attribute
names) needs hand-verification against the installed rumps version, not
a unit test.
"""

from berry.notch import point_in_rect


def test_point_inside_rect():
    assert point_in_rect(50, 50, rx=0, ry=0, rw=100, rh=100)


def test_point_outside_rect():
    assert not point_in_rect(150, 50, rx=0, ry=0, rw=100, rh=100)


def test_point_on_edge_is_inside():
    assert point_in_rect(100, 100, rx=0, ry=0, rw=100, rh=100)


def test_margin_extends_the_hit_area():
    # just outside the raw rect, but within the hover slack margin
    assert point_in_rect(103, 50, rx=0, ry=0, rw=100, rh=100, margin=4.0)


def test_margin_does_not_extend_forever():
    assert not point_in_rect(110, 50, rx=0, ry=0, rw=100, rh=100, margin=4.0)
