"""
tests.test_scan_wall_extractor

Unit tests for 2D RANSAC wall centerline extractor, Manhattan 90-degree
orthogonal rectifier, corner snapping, and topological loop closure.
"""

import math
import numpy as np
import pytest

from debim.scan.wall_extractor import (
    ExtractedWall,
    WallExtractionResult,
    fit_lines_2d_ransac,
    rectify_manhattan,
    snap_corners_and_close_loops,
    extract_walls,
)
from debim.scan.slicer import slice_point_cloud


@pytest.fixture
def synthetic_room_3d_point_cloud():
    """
    Generates a 3D point cloud for a 5.0m x 4.0m room with walls, floor, and ceiling.
    """
    rng = np.random.default_rng(101)

    # Wall 1: x = 0, y in [0, 4]
    w1_y = rng.uniform(0.0, 4.0, 800)
    w1_z = rng.uniform(0.0, 2.80, 800)
    w1_x = rng.normal(0.0, 0.01, 800)

    # Wall 2: x = 5, y in [0, 4]
    w2_y = rng.uniform(0.0, 4.0, 800)
    w2_z = rng.uniform(0.0, 2.80, 800)
    w2_x = rng.normal(5.0, 0.01, 800)

    # Wall 3: y = 0, x in [0, 5]
    w3_x = rng.uniform(0.0, 5.0, 800)
    w3_z = rng.uniform(0.0, 2.80, 800)
    w3_y = rng.normal(0.0, 0.01, 800)

    # Wall 4: y = 4, x in [0, 5]
    w4_x = rng.uniform(0.0, 5.0, 800)
    w4_z = rng.uniform(0.0, 2.80, 800)
    w4_y = rng.normal(4.0, 0.01, 800)

    wall_pts = np.vstack([
        np.column_stack([w1_x, w1_y, w1_z]),
        np.column_stack([w2_x, w2_y, w2_z]),
        np.column_stack([w3_x, w3_y, w3_z]),
        np.column_stack([w4_x, w4_y, w4_z]),
    ])

    # Floor & Ceiling
    x_f = rng.uniform(0.0, 5.0, 1000)
    y_f = rng.uniform(0.0, 4.0, 1000)
    z_f = rng.normal(0.0, 0.01, 1000)

    x_c = rng.uniform(0.0, 5.0, 1000)
    y_c = rng.uniform(0.0, 4.0, 1000)
    z_c = rng.normal(2.80, 0.01, 1000)

    all_pts = np.vstack([wall_pts, np.column_stack([x_f, y_f, z_f]), np.column_stack([x_c, y_c, z_c])])
    colors = rng.integers(0, 256, (len(all_pts), 3), dtype=np.uint8)
    return all_pts, colors


@pytest.fixture
def synthetic_2d_rectangle():
    """
    Generates 2D point cloud slice for a 6.0m x 4.0m rectangular room perimeter:
    - Wall 1: x in [0, 6], y = 0
    - Wall 2: x = 6, y in [0, 4]
    - Wall 3: x in [0, 6], y = 4
    - Wall 4: x = 0, y in [0, 4]
    """
    rng = np.random.default_rng(303)

    # Wall 1: Bottom wall (0, 0) to (6, 0)
    w1_x = rng.uniform(0.0, 6.0, 300)
    w1_y = rng.normal(0.0, 0.01, 300)

    # Wall 2: Right wall (6, 0) to (6, 4)
    w2_x = rng.normal(6.0, 0.01, 200)
    w2_y = rng.uniform(0.0, 4.0, 200)

    # Wall 3: Top wall (0, 4) to (6, 4)
    w3_x = rng.uniform(0.0, 6.0, 300)
    w3_y = rng.normal(4.0, 0.01, 300)

    # Wall 4: Left wall (0, 0) to (0, 4)
    w4_x = rng.normal(0.0, 0.01, 200)
    w4_y = rng.uniform(0.0, 4.0, 200)

    pts = np.vstack([
        np.column_stack([w1_x, w1_y]),
        np.column_stack([w2_x, w2_y]),
        np.column_stack([w3_x, w3_y]),
        np.column_stack([w4_x, w4_y]),
    ])
    return pts


def test_fit_lines_2d_ransac(synthetic_2d_rectangle):
    pts_2d = synthetic_2d_rectangle

    segments = fit_lines_2d_ransac(
        pts_2d,
        distance_threshold=0.05,
        min_inliers=20,
        min_length=1.0,
    )

    assert len(segments) >= 4
    for p1, p2 in segments:
        length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        assert length >= 1.0


def test_rectify_manhattan():
    # Slightly noisy line segments close to 0 deg and 90 deg
    noisy_segments = [
        ((0.0, 0.1), (6.0, 0.2)),    # ~1.0 deg
        ((6.1, 0.0), (5.9, 4.0)),    # ~92.8 deg
        ((0.0, 3.9), (6.0, 4.1)),    # ~1.9 deg
        ((-0.1, 0.0), (0.1, 4.0)),   # ~87.1 deg
    ]

    rectified = rectify_manhattan(
        noisy_segments,
        dominant_angles=(0.0, 90.0, 45.0, 135.0),
    )

    assert len(rectified) == 4
    for p1, p2 in rectified:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        angle_deg = math.degrees(math.atan2(dy, dx)) % 180.0
        # Check angle is snapped very close to 0 deg or 90 deg
        is_horiz = min(angle_deg, 180.0 - angle_deg) < 1.0
        is_vert = abs(angle_deg - 90.0) < 1.0
        assert is_horiz or is_vert


def test_snap_corners_and_close_loops():
    # 4 rectified line segments with minor gaps at corners
    segments = [
        ((0.1, 0.0), (5.9, 0.0)),
        ((6.0, 0.1), (6.0, 3.9)),
        ((5.9, 4.0), (0.1, 4.0)),
        ((0.0, 3.9), (0.0, 0.1)),
    ]

    walls, closed_polys = snap_corners_and_close_loops(
        segments,
        snap_threshold=0.50,
        thickness=0.20,
        height=3.00,
    )

    assert len(walls) == 4
    for w in walls:
        assert isinstance(w, ExtractedWall)
        assert w.thickness == 0.20
        assert w.height == 3.00
        assert len(w.polygon) == 4
        assert w.length > 0.0

    # Verify topological loop closure
    assert len(closed_polys) >= 1
    poly = closed_polys[0]
    assert len(poly) >= 4


def test_extract_walls_end_to_end(synthetic_2d_rectangle):
    pts_2d = synthetic_2d_rectangle

    res = extract_walls(
        pts_2d,
        thickness=0.15,
        height=2.80,
        distance_threshold=0.05,
        min_inliers=20,
        snap_threshold=0.50,
    )

    assert isinstance(res, WallExtractionResult)
    assert res.num_walls >= 4
    assert len(res.walls) == res.num_walls
    assert len(res.closed_polygons) >= 1

    # Verify attributes on extracted walls
    for w in res.walls:
        assert w.thickness == 0.15
        assert w.height == 2.80
        assert len(w.polygon) == 4
        assert w.angle_deg in [0.0, 90.0, 45.0, 135.0, 180.0] or abs(w.angle_deg % 90.0) < 2.0


def test_integration_slicer_and_wall_extractor(synthetic_room_3d_point_cloud):
    pts, colors = synthetic_room_3d_point_cloud

    # 1. Slice point cloud at eye level
    storey_res, slice_res = slice_point_cloud(pts, colors=colors)
    assert slice_res.num_points > 0

    # 2. Extract walls from slice
    res = extract_walls(
        slice_res,
        thickness=0.15,
        height=storey_res.storey_height,
        distance_threshold=0.08,
        min_inliers=15,
        snap_threshold=0.50,
    )

    assert isinstance(res, WallExtractionResult)
    assert res.num_walls >= 4
    for w in res.walls:
        assert w.thickness == 0.15
        assert np.isclose(w.height, storey_res.storey_height, atol=0.05)
        assert len(w.polygon) == 4
