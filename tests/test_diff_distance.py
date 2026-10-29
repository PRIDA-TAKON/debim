"""
tests/test_diff_distance.py

Unit tests for point-to-plane and point-to-mesh distance calculation engine,
element deviation calculations, and CLI integration.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from debim.diff import (
    compute_point_to_plane_distance,
    compute_point_to_mesh_distance,
    calculate_element_deviations,
    get_element_mesh,
)
from debim.scan.calibrator import save_ply
from debim.schema import (
    load_manifest,
    ProjectManifest,
    ProjectInfo,
    Material,
    Grids,
    SpatialStructure,
    Storey,
    IfcWall,
    IfcColumn,
    IfcSlab,
    WallPlacement,
    ColumnPlacement,
    SlabPlacement,
    BoxProfile,
)
from debim.resolver import resolve_manifest
from debim.cli import main


def test_compute_point_to_plane_distance_basic():
    plane_origin = np.array([0.0, 0.0, 0.0])
    plane_normal = np.array([0.0, 0.0, 1.0])

    pts = np.array([
        [1.0, 2.0, 0.0],
        [0.0, 0.0, 1.5],
        [5.0, 5.0, -0.8],
    ])

    dists = compute_point_to_plane_distance(pts, plane_origin, plane_normal)
    assert dists.shape == (3,)
    np.testing.assert_allclose(dists, [0.0, 1.5, -0.8], atol=1e-6)


def test_compute_point_to_plane_distance_non_unit_normal():
    plane_origin = np.array([1.0, 1.0, 1.0])
    plane_normal = np.array([0.0, 0.0, 5.0])  # Non-unit length normal

    pts = np.array([
        [1.0, 1.0, 1.0],
        [1.0, 1.0, 3.0],
        [1.0, 1.0, -1.0],
    ])

    dists = compute_point_to_plane_distance(pts, plane_origin, plane_normal)
    np.testing.assert_allclose(dists, [0.0, 2.0, -2.0], atol=1e-6)


def test_compute_point_to_plane_distance_empty():
    dists = compute_point_to_plane_distance(np.empty((0, 3)), [0, 0, 0], [0, 0, 1])
    assert dists.size == 0


def test_compute_point_to_mesh_distance_single_triangle():
    verts = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ], dtype=np.float64)
    faces = np.array([[0, 1, 2]], dtype=np.int32)

    pts = np.array([
        [0.2, 0.2, 1.0],   # Above interior
        [2.0, 0.0, 0.0],   # Outside near (1,0,0)
        [0.0, 0.0, 0.0],   # On vertex
    ], dtype=np.float64)

    dists, closest = compute_point_to_mesh_distance(pts, verts, faces)

    assert dists.shape == (3,)
    assert closest.shape == (3, 3)

    # Point 0: [0.2, 0.2, 1.0] -> closest is [0.2, 0.2, 0.0], distance = 1.0
    pytest.approx(dists[0], 1.0)
    np.testing.assert_allclose(closest[0], [0.2, 0.2, 0.0], atol=1e-5)

    # Point 1: [2.0, 0.0, 0.0] -> closest on segment AB is [1.0, 0.0, 0.0], distance = 1.0
    pytest.approx(dists[1], 1.0)
    np.testing.assert_allclose(closest[1], [1.0, 0.0, 0.0], atol=1e-5)

    # Point 2: [0.0, 0.0, 0.0] -> on vertex, distance = 0.0
    pytest.approx(dists[2], 0.0)
    np.testing.assert_allclose(closest[2], [0.0, 0.0, 0.0], atol=1e-5)


def test_compute_point_to_mesh_distance_box():
    # 1m x 1m x 1m cube centered at origin (-0.5 to 0.5)
    verts = np.array([
        [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5],
        [-0.5, -0.5,  0.5], [0.5, -0.5,  0.5], [0.5, 0.5,  0.5], [-0.5, 0.5,  0.5],
    ], dtype=np.float64)

    faces = np.array([
        [0, 1, 2], [0, 2, 3], # Bottom
        [4, 6, 5], [4, 7, 6], # Top
        [0, 4, 5], [0, 5, 1], # Front
        [2, 6, 7], [2, 7, 3], # Back
        [0, 3, 7], [0, 7, 4], # Left
        [1, 5, 6], [1, 6, 2], # Right
    ], dtype=np.int32)

    pts = np.array([
        [0.0, 0.0, 1.5],  # 1.0m above top face (+Z)
        [1.5, 0.0, 0.0],  # 1.0m to the right (+X)
    ], dtype=np.float64)

    dists, closest = compute_point_to_mesh_distance(pts, verts, faces)

    np.testing.assert_allclose(dists, [1.0, 1.0], atol=1e-5)
    np.testing.assert_allclose(closest[0], [0.0, 0.0, 0.5], atol=1e-5)
    np.testing.assert_allclose(closest[1], [0.5, 0.0, 0.0], atol=1e-5)


def test_calculate_element_deviations_synthetic():
    manifest = ProjectManifest(
        project=ProjectInfo(id="P1", name="Test Project"),
        materials=[Material(id="Concrete", name="Concrete", category="CONCRETE", unit_cost_ref="CONCRETE")],
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 4.0}),
        spatial_structure=SpatialStructure(storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.0)]),
        elements=[
            IfcWall(
                tag="W1",
                placement=WallPlacement(
                    from_grid=("1", "A"),
                    to_grid=("2", "A"),
                    storey="FL1",
                ),
                thickness=0.20,
                height=3.0,
                material="Concrete",
            )
        ]
    )
    resolved = resolve_manifest(manifest)

    # Generate synthetic scan points shifted by +15mm (0.015m) along Y
    # Wall front face is at Y = +0.10m
    y_front = 0.10 + 0.015  # Shifted outwards by 15mm
    xs = np.linspace(0.5, 3.5, 10)
    zs = np.linspace(0.5, 2.5, 10)
    grid_x, grid_z = np.meshgrid(xs, zs)

    scan_pts = np.column_stack([
        grid_x.ravel(),
        np.full(grid_x.size, y_front),
        grid_z.ravel(),
    ])

    dev_res = calculate_element_deviations(scan_pts, resolved.elements)

    assert len(dev_res.deviations) == 1
    dev = dev_res.deviations[0]

    assert dev.tag == "W1"
    assert dev.point_count == 100
    pytest.approx(dev.absolute_error_mm, 15.0, abs=1.0)
    pytest.approx(dev.delta_y, 0.015, abs=0.005)


def test_get_element_mesh_various():
    manifest = ProjectManifest(
        project=ProjectInfo(id="P1", name="Test Project"),
        materials=[Material(id="Concrete", name="Concrete", category="CONCRETE", unit_cost_ref="CONCRETE")],
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 4.0}),
        spatial_structure=SpatialStructure(storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.0)]),
        elements=[
            IfcColumn(
                tag="C1",
                placement=ColumnPlacement(grid=("1", "A"), storey="FL1"),
                profile=BoxProfile(width=0.3, depth=0.3),
                material="Concrete",
            ),
            IfcSlab(
                tag="S1",
                placement=SlabPlacement(
                    boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                    storey="FL1",
                ),
                thickness=0.15,
                material="Concrete",
            ),
        ]
    )
    resolved = resolve_manifest(manifest)

    c_verts, c_faces = get_element_mesh(resolved.columns[0])
    assert c_verts.shape[0] == 8
    assert c_faces.shape[0] == 12

    s_verts, s_faces = get_element_mesh(resolved.slabs[0])
    assert s_verts.shape[0] == 8
    assert s_faces.shape[0] > 0


def test_cli_diff_calculate(tmp_path):
    # 1. Create a dummy PLY scan file
    scan_pts = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [1.0, 1.0, 0.0],
    ], dtype=np.float64)

    ply_path = tmp_path / "test_scan.ply"
    save_ply(ply_path, scan_pts, binary=True)

    # 2. Use house.debim if it exists or create a simple manifest
    house_path = Path("house.debim")
    if not house_path.exists():
        house_path = Path("examples/farnsworth_house/house.debim")

    out_json = tmp_path / "out_deviations.json"

    # Run CLI
    cmd_args = [
        "diff",
        "calculate",
        "--scan",
        str(ply_path),
        "-m",
        str(house_path if house_path.exists() else "project.yaml"),
        "-o",
        str(out_json),
    ]

    try:
        main(cmd_args)
    except SystemExit as e:
        assert e.code == 0

    assert out_json.exists()
    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "deviations" in data
    assert "metadata" in data
    assert isinstance(data["deviations"], list)
