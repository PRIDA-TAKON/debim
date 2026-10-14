"""
Unit tests for pure-Python 2D geometry engine (src/debim/geometry2d.py).
Verifies Shoelace area, polygon perimeter, polygon inset, and point-in-polygon
against standard geometric formulas and Shapely ground truth.
"""

import pytest
from debim.geometry2d import (
    point_in_polygon,
    polygon_inset,
    polygon_perimeter,
    shoelace_area,
    signed_shoelace_area,
)

try:
    from shapely.geometry import Polygon
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


def test_shoelace_area_basic():
    # Unit square
    square = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert shoelace_area(square) == pytest.approx(1.0, abs=1e-6)

    # 10 x 5 Rectangle
    rect = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
    assert shoelace_area(rect) == pytest.approx(50.0, abs=1e-6)

    # Closed polygon (last point == first point)
    rect_closed = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0), (0.0, 0.0)]
    assert shoelace_area(rect_closed) == pytest.approx(50.0, abs=1e-6)

    # 3D vertices (z coordinate ignored)
    rect_3d = [(0.0, 0.0, 2.5), (10.0, 0.0, 2.5), (10.0, 5.0, 2.5), (0.0, 5.0, 2.5)]
    assert shoelace_area(rect_3d) == pytest.approx(50.0, abs=1e-6)


def test_signed_shoelace_area_winding():
    ccw = [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)]
    cw = [(0.0, 0.0), (0.0, 3.0), (4.0, 3.0), (4.0, 0.0)]

    assert signed_shoelace_area(ccw) == pytest.approx(12.0, abs=1e-6)
    assert signed_shoelace_area(cw) == pytest.approx(-12.0, abs=1e-6)


def test_polygon_perimeter():
    square = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    assert polygon_perimeter(square) == pytest.approx(8.0, abs=1e-6)

    triangle = [(0.0, 0.0), (3.0, 0.0), (0.0, 4.0)]
    assert polygon_perimeter(triangle) == pytest.approx(12.0, abs=1e-6)


def test_point_in_polygon():
    poly = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

    assert point_in_polygon((5.0, 5.0), poly) is True
    assert point_in_polygon((-1.0, 5.0), poly) is False
    assert point_in_polygon((11.0, 5.0), poly) is False
    assert point_in_polygon((0.0, 0.0), poly) is True  # Vertex
    assert point_in_polygon((5.0, 0.0), poly) is True  # Edge


def test_polygon_inset_rectangle():
    rect = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
    offset = 0.5

    inset = polygon_inset(rect, offset)
    assert len(inset) == 4
    assert shoelace_area(inset) == pytest.approx((10.0 - 1.0) * (5.0 - 1.0), abs=1e-4)

    expected = [(0.5, 0.5), (9.5, 0.5), (9.5, 4.5), (0.5, 4.5)]
    for p_act, p_exp in zip(inset, expected):
        assert p_act[0] == pytest.approx(p_exp[0], abs=1e-4)
        assert p_act[1] == pytest.approx(p_exp[1], abs=1e-4)


def test_polygon_outset():
    rect = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0)]
    offset = -0.5

    outset = polygon_inset(rect, offset)
    assert len(outset) == 4
    assert shoelace_area(outset) == pytest.approx((10.0 + 1.0) * (5.0 + 1.0), abs=1e-4)

    expected = [(-0.5, -0.5), (10.5, -0.5), (10.5, 5.5), (-0.5, 5.5)]
    for p_act, p_exp in zip(outset, expected):
        assert p_act[0] == pytest.approx(p_exp[0], abs=1e-4)
        assert p_act[1] == pytest.approx(p_exp[1], abs=1e-4)


@pytest.mark.skipif(not HAS_SHAPELY, reason="Shapely not installed")
def test_compare_with_shapely():
    # L-shaped room polygon
    l_shape = [
        (0.0, 0.0),
        (8.0, 0.0),
        (8.0, 4.0),
        (4.0, 4.0),
        (4.0, 8.0),
        (0.0, 8.0),
    ]

    sp_poly = Polygon(l_shape)

    # 1. Area match
    assert shoelace_area(l_shape) == pytest.approx(sp_poly.area, abs=1e-4)

    # 2. Perimeter match
    assert polygon_perimeter(l_shape) == pytest.approx(sp_poly.length, abs=1e-4)

    # 3. Inset area match (offset = 0.2m)
    offset = 0.2
    py_inset = polygon_inset(l_shape, offset)
    sp_buffered = sp_poly.buffer(-offset, join_style="mitre")

    assert shoelace_area(py_inset) == pytest.approx(sp_buffered.area, abs=1e-4)
