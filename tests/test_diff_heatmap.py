"""
tests/test_diff_heatmap.py

Unit tests for ICP fine alignment, deviation tolerance heatmap color mapping,
colorized PLY export, standalone 3D HTML heatmap viewer generation, and CLI integration.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from debim.diff.aligner import icp_fine_align
from debim.diff.heatmap import generate_deviation_heatmap, HeatmapResult, export_colorized_ply
from debim.diff.viewer_html import generate_heatmap_html
from debim.scan.calibrator import save_ply, load_ply
from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    Material,
    Grids,
    SpatialStructure,
    Storey,
    IfcWall,
    WallPlacement,
)
from debim.resolver import resolve_manifest
from debim.cli import main


def test_icp_fine_align_synthetic_rotation_translation():
    # Source cube surface points
    rng = np.random.default_rng(42)
    source_pts = rng.uniform(-1.0, 1.0, size=(200, 3))

    # Apply rigid transformation (30 degree rotation around Z, translate by [2.0, -1.0, 0.5])
    angle = np.radians(30.0)
    R_true = np.array([
        [np.cos(angle), -np.sin(angle), 0.0],
        [np.sin(angle),  np.cos(angle), 0.0],
        [0.0,            0.0,           1.0],
    ])
    t_true = np.array([2.0, -1.0, 0.5])

    target_pts = (source_pts @ R_true.T) + t_true

    # Run ICP alignment to align target_pts back to source_pts
    aligned_pts, T_matrix, rmse = icp_fine_align(target_pts, source_pts, max_iterations=50)

    assert rmse < 1e-3
    np.testing.assert_allclose(aligned_pts, source_pts, atol=1e-2)
    assert T_matrix.shape == (4, 4)


def test_generate_deviation_heatmap_color_mapping():
    pts = np.array([
        [0.0, 0.0, 0.0],  # Within tolerance
        [1.0, 0.0, 0.0],  # Protrusion (+15mm > 10mm)
        [2.0, 0.0, 0.0],  # Recessed (-15mm < -10mm)
        [3.0, 0.0, 0.0],  # Within tolerance (+5mm <= 10mm)
    ], dtype=np.float64)

    devs = np.array([0.0, 15.0, -15.0, 5.0], dtype=np.float64)

    res = generate_deviation_heatmap(pts, devs, tolerance_mm=10.0)

    assert res.tolerance_mm == 10.0
    assert res.within_tolerance_count == 2
    assert res.out_of_tolerance_count == 2
    pytest.approx(res.pass_percentage, 50.0)

    # Check RGB colors
    # Point 0: Green [34, 197, 94]
    np.testing.assert_array_equal(res.colors[0], [34, 197, 94])
    # Point 1: Red [239, 68, 68]
    np.testing.assert_array_equal(res.colors[1], [239, 68, 68])
    # Point 2: Blue [59, 130, 246]
    np.testing.assert_array_equal(res.colors[2], [59, 130, 246])
    # Point 3: Green [34, 197, 94]
    np.testing.assert_array_equal(res.colors[3], [34, 197, 94])


def test_export_colorized_ply(tmp_path):
    pts = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], dtype=np.float64)
    devs = np.array([5.0, 20.0], dtype=np.float64)

    res = generate_deviation_heatmap(pts, devs, tolerance_mm=10.0)
    ply_path = tmp_path / "colored_deviation.ply"

    exported = export_colorized_ply(ply_path, res, binary=True)
    assert exported.exists()

    # Re-read PLY and check points and colors
    read_pts, read_cols = load_ply(exported)
    np.testing.assert_allclose(read_pts, pts, atol=1e-4)
    assert read_cols is not None
    np.testing.assert_array_equal(read_cols, res.colors)


def test_generate_heatmap_html():
    manifest = ProjectManifest(
        project=ProjectInfo(id="P1", name="Heatmap Test Project"),
        materials=[Material(id="Concrete", name="Concrete", category="CONCRETE", unit_cost_ref="CONCRETE")],
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 4.0}),
        spatial_structure=SpatialStructure(storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.0)]),
        elements=[
            IfcWall(
                tag="W1",
                placement=WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="FL1"),
                thickness=0.20,
                height=3.0,
                material="Concrete",
            )
        ]
    )
    resolved = resolve_manifest(manifest)

    pts = np.array([[0.5, 0.1, 1.0], [1.5, 0.1, 1.5], [2.5, 0.1, 2.0]], dtype=np.float64)
    devs = np.array([2.0, 12.0, -8.0], dtype=np.float64)

    html_content = generate_heatmap_html(resolved, pts, devs, tolerance_mm=10.0)

    assert "<!DOCTYPE html>" in html_content
    assert "Heatmap Test Project" in html_content
    assert "Deviation Tolerance Threshold:" in html_content
    assert "tolerance-slider" in html_content
    assert "applyToleranceColoring" in html_content


def test_cli_diff_view(tmp_path):
    # Create dummy PLY scan file
    scan_pts = np.array([
        [0.5, 0.1, 0.5],
        [1.5, 0.1, 1.0],
        [2.5, 0.1, 1.5],
        [3.5, 0.1, 2.0],
    ], dtype=np.float64)

    ply_path = tmp_path / "scan.ply"
    save_ply(ply_path, scan_pts, binary=True)

    house_path = Path("house.debim")
    if not house_path.exists():
        house_path = Path("examples/farnsworth_house/house.debim")

    out_html = tmp_path / "heatmap_view.html"

    cmd_args = [
        "diff",
        "view",
        "--scan",
        str(ply_path),
        "-m",
        str(house_path if house_path.exists() else "project.yaml"),
        "--tolerance",
        "10",
        "-o",
        str(out_html),
    ]

    try:
        main(cmd_args)
    except SystemExit as e:
        assert e.code == 0

    assert out_html.exists()
    assert (tmp_path / "colored_deviation.ply").exists()

    content = out_html.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Deviation Heatmap" in content
