"""
tests.test_scan_calibrator

Tests for point cloud ingestion, floor RANSAC plane estimation, Rodrigues rotation,
door opening height detection, and metric scale calibration.
"""

from pathlib import Path
import numpy as np
import pytest

from debim.scan.calibrator import (
    CalibrationResult,
    load_ply,
    save_ply,
    estimate_floor_plane,
    rodrigues_rotation_matrix,
    detect_door_height,
    calibrate_point_cloud,
)


@pytest.fixture
def temp_ply_dir(tmp_path: Path) -> Path:
    return tmp_path


def test_save_and_load_ply_ascii(temp_ply_dir: Path):
    filepath = temp_ply_dir / "test_ascii.ply"
    pts_orig = np.array([
        [0.0, 1.0, 2.0],
        [3.0, 4.0, 5.0],
        [6.0, 7.0, 8.0],
    ], dtype=np.float64)
    cols_orig = np.array([
        [255, 0, 0],
        [0, 255, 0],
        [0, 0, 255],
    ], dtype=np.uint8)

    save_ply(filepath, pts_orig, cols_orig, binary=False)
    assert filepath.exists()

    pts_loaded, cols_loaded = load_ply(filepath)
    np.testing.assert_allclose(pts_loaded, pts_orig, atol=1e-5)
    assert cols_loaded is not None
    np.testing.assert_array_equal(cols_loaded, cols_orig)


def test_save_and_load_ply_binary(temp_ply_dir: Path):
    filepath = temp_ply_dir / "test_binary.ply"
    pts_orig = np.array([
        [1.5, 2.5, 3.5],
        [4.5, 5.5, 6.5],
        [7.5, 8.5, 9.5],
    ], dtype=np.float64)
    cols_orig = np.array([
        [100, 150, 200],
        [50, 75, 100],
        [200, 100, 50],
    ], dtype=np.uint8)

    save_ply(filepath, pts_orig, cols_orig, binary=True)
    assert filepath.exists()

    pts_loaded, cols_loaded = load_ply(filepath)
    np.testing.assert_allclose(pts_loaded, pts_orig, atol=1e-4)
    assert cols_loaded is not None
    np.testing.assert_array_equal(cols_loaded, cols_orig)


def test_estimate_floor_plane_and_rodrigues():
    rng = np.random.default_rng(123)

    # True plane: tilted normal
    true_normal = np.array([0.05, 0.10, 0.9937], dtype=np.float64)
    true_normal /= np.linalg.norm(true_normal)
    true_d = -2.5 # Plane dist

    # Generate 1500 points on floor plane + small noise
    xy = rng.uniform(-10.0, 10.0, (1500, 2))
    z = (-true_d - true_normal[0] * xy[:, 0] - true_normal[1] * xy[:, 1]) / true_normal[2]
    floor_pts = np.column_stack([xy, z]) + rng.normal(0, 0.005, (1500, 3))

    est_normal, est_d, inliers = estimate_floor_plane(floor_pts, distance_threshold=0.03)

    # Check normal is pointing up and close to true
    assert est_normal[2] > 0.7
    np.testing.assert_allclose(est_normal, true_normal, atol=0.03)

    # Test Rodrigues rotation
    R = rodrigues_rotation_matrix(est_normal)
    assert R.shape == (3, 3)

    # Check that rotating normal gives +Z (0, 0, 1)
    rotated_normal = np.dot(R, est_normal)
    np.testing.assert_allclose(rotated_normal, [0.0, 0.0, 1.0], atol=1e-5)

    # Check rotated floor points are flat
    rotated_pts = np.dot(floor_pts, R.T)
    z_std = float(np.std(rotated_pts[:, 2]))
    assert z_std < 0.02


def test_detect_door_height():
    rng = np.random.default_rng(456)
    floor_z = 0.0
    h_door_true = 1.60

    # Floor points
    xy_f = rng.uniform(0.0, 4.0, (1000, 2))
    z_f = rng.normal(floor_z, 0.01, 1000)
    floor_pts = np.column_stack([xy_f, z_f])

    # Wall at y=0, x from 0 to 4, door cutout at x in [1.5, 2.5]
    # Solid left wall
    x_w_left = rng.uniform(0.0, 1.5, 500)
    z_w_left = rng.uniform(0.0, 2.5, 500)
    y_w_left = rng.normal(0.0, 0.01, 500)

    # Solid right wall
    x_w_right = rng.uniform(2.5, 4.0, 500)
    z_w_right = rng.uniform(0.0, 2.5, 500)
    y_w_right = rng.normal(0.0, 0.01, 500)

    # Door lintel header above cutout (x in [1.5, 2.5], z from 1.60 to 2.50)
    x_w_lintel = rng.uniform(1.5, 2.5, 300)
    z_w_lintel = rng.uniform(h_door_true, 2.50, 300)
    y_w_lintel = rng.normal(0.0, 0.01, 300)

    wall_pts = np.vstack([
        np.column_stack([x_w_left, y_w_left, z_w_left]),
        np.column_stack([x_w_right, y_w_right, z_w_right]),
        np.column_stack([x_w_lintel, y_w_lintel, z_w_lintel]),
    ])

    pts = np.vstack([floor_pts, wall_pts])

    h_detected = detect_door_height(pts, floor_z=0.0)
    np.testing.assert_allclose(h_detected, h_door_true, atol=0.05)


def test_calibrate_point_cloud(temp_ply_dir: Path):
    rng = np.random.default_rng(789)
    raw_floor_z = 1.25
    raw_door_height = 1.60

    # Tilted floor plane
    true_normal = np.array([0.02, 0.04, 0.998], dtype=np.float64)
    true_normal /= np.linalg.norm(true_normal)

    # Generate floor points
    xy_f = rng.uniform(-3.0, 3.0, (1200, 2))
    z_f = raw_floor_z + rng.normal(0, 0.005, 1200)
    floor_pts = np.column_stack([xy_f, z_f])

    # Wall points with door cutout (h_door = 1.60)
    x_w = rng.uniform(-2.0, 2.0, 600)
    y_w = rng.normal(1.0, 0.01, 600)
    # Door cutout at x in [-0.5, 0.5]: z >= 1.25 + 1.60
    z_w = []
    for xi in x_w:
        if -0.5 <= xi <= 0.5:
            z_w.append(rng.uniform(raw_floor_z + raw_door_height, raw_floor_z + 2.5))
        else:
            z_w.append(rng.uniform(raw_floor_z, raw_floor_z + 2.5))
    wall_pts = np.column_stack([x_w, y_w, np.array(z_w)])

    pts_raw = np.vstack([floor_pts, wall_pts])
    colors_raw = rng.integers(0, 256, (len(pts_raw), 3), dtype=np.uint8)

    # Save to binary PLY file
    ply_path = temp_ply_dir / "raw_room.ply"
    save_ply(ply_path, pts_raw, colors_raw, binary=True)

    # Calibrate
    res = calibrate_point_cloud(ply_path, target_door_height=2.00)

    assert isinstance(res, CalibrationResult)
    assert res.calibrated_points.shape == pts_raw.shape
    assert res.scale_factor > 0

    # Acceptance Criteria 1: Calibrated floor level at Z = 0
    # The floor points (first 1200 points) should have median Z very close to 0.0
    cal_floor_z = float(np.median(res.calibrated_points[:1200, 2]))
    np.testing.assert_allclose(cal_floor_z, 0.0, atol=0.03)

    # Acceptance Criteria 2: Door opening height rescaled to 2.00m
    expected_scale = 2.00 / raw_door_height # 2.00 / 1.60 = 1.25
    np.testing.assert_allclose(res.scale_factor, expected_scale, atol=0.05)

    # Check lintel height in calibrated points (door lintel at x in [-0.5*s, 0.5*s])
    door_lintel_mask = (
        (res.calibrated_points[:, 0] >= -0.5 * res.scale_factor) &
        (res.calibrated_points[:, 0] <= 0.5 * res.scale_factor) &
        (res.calibrated_points[:, 1] >= 0.8 * res.scale_factor) &
        (res.calibrated_points[:, 2] > 0.5)
    )
    door_lintel_z_min = float(np.min(res.calibrated_points[door_lintel_mask, 2]))
    np.testing.assert_allclose(door_lintel_z_min, 2.00, atol=0.05)
