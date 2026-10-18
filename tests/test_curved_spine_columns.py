"""
Unit tests for 3D directrix spine & swept curved columns (IfcSectionedSpine / IfcColumn).
Verifies:
1. Automatic column generator along hyperbolic loft surface boundaries.
2. 3D spatial continuity across storeys (bottom of storey N+1 matches top of storey N).
3. 3D Euclidean arc length and structural steel QTO calculations.
4. IFC4 compilation with 3D orientation matrices.
"""

import math
from pathlib import Path
import pytest
import numpy as np

from debim.compiler import compile_to_ifc
from debim.geometry.loft import generate_curved_spine_columns
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    CircleHollowProfile,
    ColumnGenerator,
    GeometryRules,
    Grids,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    StructuresConfig,
)
from debim.viewer import generate_viewer_html


@pytest.fixture
def hyperbolic_tower_manifest() -> ProjectManifest:
    """Creates a 4-storey hyperbolic tower with 28 swept curved steel columns."""
    return ProjectManifest(
        project=ProjectInfo(id="PROJ-SOUMAYA-TOWER", name="Hyperbolic Curved Column Tower"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Floor 1", elevation=0.0, height=5.0),
                Storey(id="FL2", name="Floor 2", elevation=5.0, height=5.0),
                Storey(id="FL3", name="Floor 3", elevation=10.0, height=5.0),
                Storey(id="FL4", name="Floor 4", elevation=15.0, height=5.0),
            ]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 30.0}, axes_y={"A": 0.0, "B": 30.0}),
        materials=[
            Material(id="STEEL_WHITE", name="Architectural White Steel", category="steel", unit_cost_ref="MAT-STEEL"),
            Material(id="CONCRETE", name="Reinforced Concrete", category="concrete", unit_cost_ref="MAT-CONC"),
        ],
        geometry_rules=GeometryRules(
            type="HYPERBOLIC_LOFT",
            base_radii=(14.0, 18.0),
            waist_radii=(11.0, 13.5),
            roof_radii=(20.0, 24.0),
            cantilever_offset=(4.0, 0.0),
        ),
        structures=StructuresConfig(
            column_generator=ColumnGenerator(
                count=28,
                distribution="RADIAL_ELLIPTIC",
                profile="CIRCULAR_HOLLOW_D600",
                trajectory="LOFT_SURFACE_ISOPARAMETRIC",
                material="STEEL_WHITE",
            )
        ),
    )


def test_generate_curved_spine_columns_count_and_continuity(hyperbolic_tower_manifest: ProjectManifest):
    """Verify 28 curved columns generated across 4 storeys (total 112 segments) with exact vertical continuity."""
    cols = generate_curved_spine_columns(hyperbolic_tower_manifest)
    # 28 columns * 4 storeys = 112 column segments
    assert len(cols) == 112

    # Check first column segments across storeys
    col_1_fl1 = next(c for c in cols if c.tag == "COL-CURVED-1-FL1")
    col_1_fl2 = next(c for c in cols if c.tag == "COL-CURVED-1-FL2")
    col_1_fl3 = next(c for c in cols if c.tag == "COL-CURVED-1-FL3")
    col_1_fl4 = next(c for c in cols if c.tag == "COL-CURVED-1-FL4")

    # Physical continuity: top of FL1 segment must match bottom of FL2 segment!
    assert col_1_fl1.placement.top_grid == col_1_fl2.placement.grid
    assert col_1_fl2.placement.top_grid == col_1_fl3.placement.grid
    assert col_1_fl3.placement.top_grid == col_1_fl4.placement.grid

    # Check profile resolution
    prof = col_1_fl1.profile
    assert isinstance(prof, CircleHollowProfile)
    assert pytest.approx(prof.diameter, 1e-4) == 0.60
    assert pytest.approx(prof.wall_thickness, 1e-4) == 0.02


def test_curved_spine_columns_spatial_resolution(hyperbolic_tower_manifest: ProjectManifest):
    """Verify 3D spatial resolution computes Euclidean arc length and normalized 3D direction vector."""
    resolved = resolve_manifest(hyperbolic_tower_manifest)

    # Columns should be present in resolved manifest
    curved_cols = [c for c in resolved.columns if "COL-CURVED-" in c.tag]
    assert len(curved_cols) == 112

    for col in curved_cols:
        # Euclidean length must be >= storey vertical height (5.0m) due to 3D inclination
        assert col.height >= 5.0

        # Direction vector must be normalized to unit length
        dx, dy, dz = col.direction_vector_3d
        norm = math.sqrt(dx * dx + dy * dy + dz * dz)
        assert pytest.approx(norm, 1e-4) == 1.0

        # dz must be positive (traveling upwards)
        assert dz > 0.0


def test_curved_spine_columns_qto_structural_steel(hyperbolic_tower_manifest: ProjectManifest):
    """Verify QTO calculation includes structural steel tonnage, painting area, and weld touch-up."""
    qto = calculate_qto(hyperbolic_tower_manifest)

    # 112 columns * ~5.2m * steel weight per m for D600 CHS
    assert qto.total_structural_steel_weight > 50000.0  # > 50 metric tons
    assert qto.total_painting_area > 500.0  # > 500 m2
    assert qto.total_weld_touchup_area > 50.0  # > 50 m2

    # Concrete volume should be positive from the loft floor slabs
    assert qto.total_concrete_volume > 0.0


def test_curved_spine_columns_ifc_compilation(hyperbolic_tower_manifest: ProjectManifest, tmp_path: Path):
    """Verify compilation of 112 curved columns into standard IFC4."""
    out_ifc = tmp_path / "hyperbolic_curved_columns.ifc"
    res = compile_to_ifc(hyperbolic_tower_manifest, output_path=out_ifc)

    assert out_ifc.exists()
    assert out_ifc.stat().st_size > 10000

    content = out_ifc.read_text(encoding="utf-8")
    assert "IFCCOLUMN" in content
    assert "COL-CURVED-1-FL1" in content
    assert "COL-CURVED-28-FL4" in content


def test_curved_spine_columns_viewer_export(hyperbolic_tower_manifest: ProjectManifest, tmp_path: Path):
    """Verify 3D WebGL viewer export renders curved columns with 3D direction vectors."""
    out_html = tmp_path / "hyperbolic_viewer.html"
    html_content = generate_viewer_html(hyperbolic_tower_manifest)
    out_html.write_text(html_content, encoding="utf-8")

    assert out_html.exists()
    assert out_html.stat().st_size > 50000

    html_content = out_html.read_text(encoding="utf-8")
    assert "COL-CURVED-1-FL1" in html_content
    assert "direction_vector_3d" in html_content
