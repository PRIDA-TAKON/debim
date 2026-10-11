"""
Unit tests for IfcCovering 3D geometry and 2D cut-plane projection.
"""

import math
import pytest
from debim.schema import (
    CoveringPlacement,
    Grids,
    IfcCovering,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.resolver import resolve_manifest
from debim.draw.projection import slice_storey
from debim.viewer import generate_viewer_html
from tools.render_visual_regression import extract_all_resolved_meshes


@pytest.fixture
def covering_manifest() -> ProjectManifest:
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-COV-01", name="Covering Geometry Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Ground Floor", elevation=0.0, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[
            Material(id="MAT_TILES", name="Ceramic Floor Tiles", category="finish", unit_cost_ref="COST-TILES"),
            Material(id="MAT_GYPSUM", name="Gypsum Ceiling Board", category="finish", unit_cost_ref="COST-GYPSUM"),
        ],
        elements=[
            IfcCovering(
                tag="COV-FLOOR-01",
                material="MAT_TILES",
                covering_type="FLOORING",
                thickness=0.02,
                placement=CoveringPlacement(
                    boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                    storey="L1",
                    offset_z=0.0,
                ),
            ),
            IfcCovering(
                tag="COV-CEIL-01",
                material="MAT_GYPSUM",
                covering_type="CEILING",
                thickness=0.015,
                placement=CoveringPlacement(
                    boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                    storey="L1",
                    offset_z=3.0,
                ),
            ),
        ],
    )


def test_covering_resolver(covering_manifest):
    resolved = resolve_manifest(covering_manifest)
    assert len(resolved.coverings) == 2

    c_floor = next(c for c in resolved.coverings if c.tag == "COV-FLOOR-01")
    assert math.isclose(c_floor.area, 25.0, rel_tol=1e-3)
    assert c_floor.center[0] == 2.5
    assert c_floor.center[1] == 2.5
    assert c_floor.center[2] == 0.0

    c_ceil = next(c for c in resolved.coverings if c.tag == "COV-CEIL-01")
    assert math.isclose(c_ceil.area, 25.0, rel_tol=1e-3)
    assert c_ceil.center[2] == 3.0


def test_covering_2d_projection(covering_manifest):
    cut_plane = slice_storey(covering_manifest, storey_id="L1", cut_offset_z=1.2)
    cov_proj = [p for p in cut_plane.projection_elements if p.element_class == "IfcCovering"]
    assert len(cov_proj) >= 1
    tags = [p.tag for p in cov_proj]
    assert "COV-FLOOR-01" in tags


def test_covering_viewer_data(covering_manifest):
    html = generate_viewer_html(covering_manifest)
    assert "IfcCovering" in html
    assert "COV-FLOOR-01" in html
    assert "COV-CEIL-01" in html


def test_covering_visual_regression_mesh_extractor(covering_manifest):
    resolved = resolve_manifest(covering_manifest)
    meshes = extract_all_resolved_meshes(resolved)
    assert len(meshes) == 2
    # Check that meshes have bounding boxes matching the resolution
    for tag, (verts, faces) in meshes.items():
        min_b = verts.min(axis=0)
        max_b = verts.max(axis=0)
        dx = max_b[0] - min_b[0]
        dy = max_b[1] - min_b[1]
        dz = max_b[2] - min_b[2]
        assert math.isclose(dx, 5.0, abs_tol=0.01)
        assert math.isclose(dy, 5.0, abs_tol=0.01)
        assert math.isclose(dz, 0.02, abs_tol=0.01) or math.isclose(dz, 0.015, abs_tol=0.01)
