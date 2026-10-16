"""
Unit test suite for relative touching space placement syntax (touching: { target, side, align }).
Verifies 2D space coordinate solving for relative adjacencies across all cardinal sides and alignments.
"""

import pytest
from debim.derive import solve_relative_space_positions, Space2DBounds
from debim.schema import IfcSpace, SpaceTouchingSpec, SpacePlacement


def test_touching_spaces_cardinal_positions():
    spaces = [
        IfcSpace(
            tag="MAIN",
            dimensions=(4.0, 5.0),
            origin=(10.0, 10.0),
        ),
        IfcSpace(
            tag="NORTH_ROOM",
            dimensions=(3.0, 3.0),
            touching=SpaceTouchingSpec(target="MAIN", side="NORTH", align="LEFT"),
        ),
        IfcSpace(
            tag="SOUTH_ROOM",
            dimensions=(3.0, 3.0),
            touching=SpaceTouchingSpec(target="MAIN", side="SOUTH", align="RIGHT"),
        ),
        IfcSpace(
            tag="EAST_ROOM",
            dimensions=(2.0, 4.0),
            touching=SpaceTouchingSpec(target="MAIN", side="EAST", align="BOTTOM"),
        ),
        IfcSpace(
            tag="WEST_ROOM",
            dimensions=(2.0, 4.0),
            touching=SpaceTouchingSpec(target="MAIN", side="WEST", align="CENTER"),
        ),
    ]

    resolved = solve_relative_space_positions(spaces)

    # MAIN bounds: x in [10, 14], y in [10, 15]
    assert resolved["MAIN"].min_x == 10.0
    assert resolved["MAIN"].max_x == 14.0
    assert resolved["MAIN"].min_y == 10.0
    assert resolved["MAIN"].max_y == 15.0

    # NORTH_ROOM: target MAIN, NORTH, align LEFT -> min_y = 15.0, max_y = 18.0, min_x = 10.0, max_x = 13.0
    assert resolved["NORTH_ROOM"].min_y == 15.0
    assert resolved["NORTH_ROOM"].max_y == 18.0
    assert resolved["NORTH_ROOM"].min_x == 10.0
    assert resolved["NORTH_ROOM"].max_x == 13.0

    # SOUTH_ROOM: target MAIN, SOUTH, align RIGHT -> max_y = 10.0, min_y = 7.0, max_x = 14.0, min_x = 11.0
    assert resolved["SOUTH_ROOM"].max_y == 10.0
    assert resolved["SOUTH_ROOM"].min_y == 7.0
    assert resolved["SOUTH_ROOM"].max_x == 14.0
    assert resolved["SOUTH_ROOM"].min_x == 11.0

    # EAST_ROOM: target MAIN, EAST, align BOTTOM -> min_x = 14.0, max_x = 16.0, min_y = 10.0, max_y = 14.0
    assert resolved["EAST_ROOM"].min_x == 14.0
    assert resolved["EAST_ROOM"].max_x == 16.0
    assert resolved["EAST_ROOM"].min_y == 10.0
    assert resolved["EAST_ROOM"].max_y == 14.0

    # WEST_ROOM: target MAIN, WEST, align CENTER -> max_x = 10.0, min_x = 8.0, center_y = 12.5 -> min_y = 10.5, max_y = 14.5
    assert resolved["WEST_ROOM"].max_x == 10.0
    assert resolved["WEST_ROOM"].min_x == 8.0
    assert resolved["WEST_ROOM"].min_y == 10.5
    assert resolved["WEST_ROOM"].max_y == 14.5


def test_nested_chained_touching_spaces():
    spaces = [
        {"tag": "R1", "dimensions": [4.0, 4.0], "origin": [0.0, 0.0]},
        {"tag": "R2", "dimensions": [4.0, 4.0], "touching": {"target": "R1", "side": "EAST", "align": "BOTTOM"}},
        {"tag": "R3", "dimensions": [4.0, 4.0], "touching": {"target": "R2", "side": "EAST", "align": "BOTTOM"}},
    ]

    resolved = solve_relative_space_positions(spaces)

    assert resolved["R1"].min_x == 0.0 and resolved["R1"].max_x == 4.0
    assert resolved["R2"].min_x == 4.0 and resolved["R2"].max_x == 8.0
    assert resolved["R3"].min_x == 8.0 and resolved["R3"].max_x == 12.0
