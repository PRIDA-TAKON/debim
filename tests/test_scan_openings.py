"""
tests.test_scan_openings

Unit and integration tests for vertical point density profile sampling and opening
gap detection (doors: floor-to-2m void, windows: 0.8m-to-2m void with apron wall below 0.8m).
"""

import numpy as np
import pytest

from debim.scan.wall_extractor import ExtractedWall, WallExtractionResult
from debim.scan.opening_detector import (
    DetectedOpening,
    OpeningDetectionResult,
    detect_openings_along_wall,
    detect_openings,
)


@pytest.fixture
def wall_with_door_and_window():
    """
    Creates a 10.0m horizontal wall segment along Y=0.0 (X from 0.0 to 10.0)
    and synthetic 3D point cloud with:
    - Door D1 void from X = 1.0 to 2.0 (Z in [0.0, 2.0] void, header wall points above Z >= 2.0)
    - Window W1 void from X = 5.0 to 6.5 (Z in [0.8, 2.0] void, apron wall below Z < 0.8, header wall points above Z >= 2.0)
    - Solid wall sections everywhere else.
    """
    wall = ExtractedWall(
        start_point=(0.0, 0.0),
        end_point=(10.0, 0.0),
        thickness=0.15,
        height=2.80,
    )

    rng = np.random.default_rng(2025)
    pts = []

    # Dense points along solid wall sections and headers
    # Sampling grid along wall length (x in [0, 10], z in [0, 2.8])
    for x in np.linspace(0.0, 10.0, 200):
        for z in np.linspace(0.0, 2.80, 50):
            # Check if point falls inside Door void (X in [1.0, 2.0], Z in [0.0, 2.0])
            is_door_void = (1.0 <= x <= 2.0) and (0.0 <= z < 2.0)
            # Check if point falls inside Window void (X in [5.0, 6.5], Z in [0.8, 2.0])
            is_window_void = (5.0 <= x <= 6.5) and (0.8 <= z < 2.0)

            if not is_door_void and not is_window_void:
                y = float(rng.normal(0.0, 0.005))
                pts.append([x, y, z])

    pts_arr = np.array(pts, dtype=np.float64)
    return wall, pts_arr


def test_detect_openings_along_wall(wall_with_door_and_window):
    wall, pts_3d = wall_with_door_and_window

    openings = detect_openings_along_wall(
        wall=wall,
        points_3d=pts_3d,
        wall_index=0,
        floor_z=0.0,
        bin_size=0.05,
        min_opening_width=0.40,
    )

    assert len(openings) == 2

    # Door
    door = [o for o in openings if o.opening_type == "Door"][0]
    assert door.opening_type == "Door"
    assert np.isclose(door.sill_height, 0.0, atol=0.05)
    assert np.isclose(door.head_height, 2.0, atol=0.10)
    assert np.isclose(door.width, 1.0, atol=0.10)
    assert door.height > 1.80
    assert 0.95 <= door.start_point[0] <= 1.05
    assert 1.95 <= door.end_point[0] <= 2.05

    # Window
    window = [o for o in openings if o.opening_type == "Window"][0]
    assert window.opening_type == "Window"
    assert np.isclose(window.sill_height, 0.80, atol=0.10)
    assert np.isclose(window.head_height, 2.0, atol=0.10)
    assert np.isclose(window.width, 1.5, atol=0.10)
    assert np.isclose(window.height, 1.20, atol=0.15)
    assert 4.95 <= window.start_point[0] <= 5.05
    assert 6.45 <= window.end_point[0] <= 6.55


def test_detect_openings_multiple_walls(wall_with_door_and_window):
    wall1, pts_3d = wall_with_door_and_window

    # Second wall along Y=5.0 (X from 0 to 6) with a Door from X=2.0 to 3.0
    wall2 = ExtractedWall(
        start_point=(0.0, 5.0),
        end_point=(6.0, 5.0),
        thickness=0.15,
        height=2.80,
    )

    rng = np.random.default_rng(42)
    pts2 = []
    for x in np.linspace(0.0, 6.0, 120):
        for z in np.linspace(0.0, 2.80, 50):
            if not (2.0 <= x <= 3.0 and 0.0 <= z < 2.0):
                y = 5.0 + float(rng.normal(0.0, 0.005))
                pts2.append([x, y, z])

    all_pts = np.vstack([pts_3d, np.array(pts2)])

    res = detect_openings(
        walls_or_result=[wall1, wall2],
        points_3d=all_pts,
        floor_z=0.0,
    )

    assert isinstance(res, OpeningDetectionResult)
    assert res.num_openings == 3
    assert res.num_doors == 2
    assert res.num_windows == 1

    # Verify tags
    assert res.doors[0].tag == "D1"
    assert res.doors[1].tag == "D2"
    assert res.windows[0].tag == "W1"


def test_detect_openings_empty_and_solid():
    wall = ExtractedWall(
        start_point=(0.0, 0.0),
        end_point=(4.0, 0.0),
        thickness=0.15,
        height=2.80,
    )

    # Empty points
    empty_pts = np.empty((0, 3), dtype=np.float64)
    res_empty = detect_openings([wall], empty_pts)
    assert res_empty.num_openings == 0

    # Completely solid wall (no voids)
    pts = []
    for x in np.linspace(0.0, 4.0, 100):
        for z in np.linspace(0.0, 2.80, 40):
            pts.append([x, 0.0, z])

    res_solid = detect_openings([wall], np.array(pts))
    assert res_solid.num_openings == 0
