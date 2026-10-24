"""
tests.test_scan_slicer

Unit tests for Z-histogram peak analysis (storey height extraction)
and eye-level horizontal 2D slice extraction filtering low furniture.
"""

from pathlib import Path
import numpy as np
import pytest

from debim.scan.slicer import (
    StoreyHeightResult,
    SliceResult,
    detect_storey_height,
    extract_eye_level_slice,
    slice_point_cloud,
)
from debim.scan.calibrator import calibrate_point_cloud, save_ply


@pytest.fixture
def synthetic_room_point_cloud():
    """
    Generates a 3D point cloud for a 5.0m x 4.0m room with:
    - Dense floor at Z = 0.0m
    - Low coffee table at Z = 0.45m (x in [1.0, 2.0], y in [1.0, 2.0])
    - Desk at Z = 0.75m (x in [3.0, 4.0], y in [2.5, 3.5])
    - Room perimeter walls from Z = 0.0m to Z = 2.80m
    - Dense ceiling at Z = 2.80m
    """
    rng = np.random.default_rng(101)

    # 1. Floor points (Z ~ 0.0m)
    x_f = rng.uniform(0.0, 5.0, 2000)
    y_f = rng.uniform(0.0, 4.0, 2000)
    z_f = rng.normal(0.0, 0.01, 2000)
    floor_pts = np.column_stack([x_f, y_f, z_f])

    # 2. Low furniture: Coffee table (Z ~ 0.45m)
    x_t = rng.uniform(1.0, 2.0, 200)
    y_t = rng.uniform(1.0, 2.0, 200)
    z_t = rng.normal(0.45, 0.01, 200)
    table_pts = np.column_stack([x_t, y_t, z_t])

    # 3. Desk (Z ~ 0.75m)
    x_d = rng.uniform(3.0, 4.0, 200)
    y_d = rng.uniform(2.5, 3.5, 200)
    z_d = rng.normal(0.75, 0.01, 200)
    desk_pts = np.column_stack([x_d, y_d, z_d])

    # 4. Room Perimeter Walls (4 side walls, Z from 0.0 to 2.80)
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

    # 5. Ceiling points (Z ~ 2.80m)
    x_c = rng.uniform(0.0, 5.0, 1800)
    y_c = rng.uniform(0.0, 4.0, 1800)
    z_c = rng.normal(2.80, 0.01, 1800)
    ceiling_pts = np.column_stack([x_c, y_c, z_c])

    all_pts = np.vstack([floor_pts, table_pts, desk_pts, wall_pts, ceiling_pts])
    colors = rng.integers(0, 256, (len(all_pts), 3), dtype=np.uint8)

    return all_pts, colors


def test_detect_storey_height(synthetic_room_point_cloud):
    pts, _ = synthetic_room_point_cloud

    res = detect_storey_height(pts, bin_size=0.05)

    assert isinstance(res, StoreyHeightResult)
    np.testing.assert_allclose(res.floor_z, 0.0, atol=0.05)
    np.testing.assert_allclose(res.ceiling_z, 2.80, atol=0.05)
    np.testing.assert_allclose(res.storey_height, 2.80, atol=0.05)
    assert len(res.histogram_counts) > 0
    assert len(res.bin_centers) == len(res.histogram_counts)


def test_detect_storey_height_custom_floor():
    rng = np.random.default_rng(202)
    offset_z = 0.20
    target_height = 3.20

    # Floor at Z = 0.20
    xy_f = rng.uniform(0.0, 4.0, (1000, 2))
    z_f = rng.normal(offset_z, 0.01, 1000)
    f_pts = np.column_stack([xy_f, z_f])

    # Ceiling at Z = 0.20 + 3.20 = 3.40
    xy_c = rng.uniform(0.0, 4.0, (1000, 2))
    z_c = rng.normal(offset_z + target_height, 0.01, 1000)
    c_pts = np.column_stack([xy_c, z_c])

    # Walls between 0.20 and 3.40
    x_w = rng.uniform(0.0, 4.0, 500)
    y_w = rng.normal(0.0, 0.01, 500)
    z_w = rng.uniform(offset_z, offset_z + target_height, 500)
    w_pts = np.column_stack([x_w, y_w, z_w])

    pts = np.vstack([f_pts, c_pts, w_pts])

    res = detect_storey_height(pts, floor_search_range=(-0.1, 0.5))

    np.testing.assert_allclose(res.floor_z, offset_z, atol=0.05)
    np.testing.assert_allclose(res.ceiling_z, offset_z + target_height, atol=0.05)
    np.testing.assert_allclose(res.storey_height, target_height, atol=0.05)


def test_extract_eye_level_slice_and_low_furniture_filtering(synthetic_room_point_cloud):
    pts, colors = synthetic_room_point_cloud

    slice_res = extract_eye_level_slice(
        pts,
        colors=colors,
        z_level=1.20,
        thickness=0.10,
        filter_low_furniture=True,
        floor_z=0.0,
    )

    assert isinstance(slice_res, SliceResult)
    assert slice_res.num_points > 0
    assert len(slice_res.slice_points_2d) == slice_res.num_points
    assert len(slice_res.slice_points_3d) == slice_res.num_points
    assert slice_res.slice_colors is not None
    assert len(slice_res.slice_colors) == slice_res.num_points

    # 1. Check all extracted 3D points fall strictly in Z range [1.10, 1.30]
    z_slice = slice_res.slice_points_3d[:, 2]
    assert np.all((z_slice >= 1.10) & (z_slice <= 1.30))

    # 2. Check low furniture points (Z < 0.90m) and ceiling/floor are completely excluded
    # Table (Z ~ 0.45) in x in [1.0, 2.0], y in [1.0, 2.0]
    table_mask = (
        (slice_res.slice_points_2d[:, 0] >= 1.0) & (slice_res.slice_points_2d[:, 0] <= 2.0) &
        (slice_res.slice_points_2d[:, 1] >= 1.0) & (slice_res.slice_points_2d[:, 1] <= 2.0)
    )
    # The only points inside table bounds in slice should be wall points if any wall passes through, but no furniture surface points!
    # All points in slice have Z >= 1.10, so table top at 0.45 is filtered out.

    # 3. Verify room perimeter wall points are preserved
    x_2d = slice_res.slice_points_2d[:, 0]
    y_2d = slice_res.slice_points_2d[:, 1]

    # Walls were at x=0, x=5, y=0, y=4
    has_x0_wall = np.any(np.abs(x_2d - 0.0) < 0.05)
    has_x5_wall = np.any(np.abs(x_2d - 5.0) < 0.05)
    has_y0_wall = np.any(np.abs(y_2d - 0.0) < 0.05)
    has_y4_wall = np.any(np.abs(y_2d - 4.0) < 0.05)

    assert has_x0_wall
    assert has_x5_wall
    assert has_y0_wall
    assert has_y4_wall


def test_slice_point_cloud_convenience(synthetic_room_point_cloud):
    pts, colors = synthetic_room_point_cloud

    storey_res, slice_res = slice_point_cloud(
        pts,
        colors=colors,
        eye_level=1.20,
        thickness=0.10,
    )

    assert isinstance(storey_res, StoreyHeightResult)
    assert isinstance(slice_res, SliceResult)
    np.testing.assert_allclose(storey_res.storey_height, 2.80, atol=0.05)
    assert slice_res.num_points > 0


def test_empty_point_cloud():
    pts = np.empty((0, 3), dtype=np.float64)

    storey_res = detect_storey_height(pts)
    assert storey_res.floor_z == 0.0
    assert storey_res.ceiling_z == 2.80

    slice_res = extract_eye_level_slice(pts)
    assert slice_res.num_points == 0
    assert len(slice_res.slice_points_2d) == 0


def test_integration_calibrator_and_slicer(tmp_path: Path, synthetic_room_point_cloud):
    pts, colors = synthetic_room_point_cloud

    # Shift raw points so floor is at Z = 1.50
    pts_raw = pts + np.array([0.0, 0.0, 1.50])

    ply_path = tmp_path / "room_raw.ply"
    save_ply(ply_path, pts_raw, colors, binary=True)

    # 1. Calibrate point cloud
    cal_res = calibrate_point_cloud(ply_path, target_door_height=2.00)

    # 2. Slice calibrated point cloud
    storey_res, slice_res = slice_point_cloud(cal_res.calibrated_points, colors=cal_res.calibrated_colors)

    # Check floor detected at Z ~ 0.0
    np.testing.assert_allclose(storey_res.floor_z, 0.0, atol=0.05)
    assert slice_res.num_points > 0
    # Perimeter 2D points extracted at eye level
    assert slice_res.slice_points_2d.shape[1] == 2
