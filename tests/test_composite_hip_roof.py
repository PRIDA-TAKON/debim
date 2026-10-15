"""Unit tests for native L-shaped and T-shaped composite hip roof 3D geometry solver,

valley/hip seams, framing takeoff, QTO, and IFC compilation.
"""

from pathlib import Path
import pytest

from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    SpatialStructure,
    Storey,
    Grids,
    Material,
    IfcRoof,
    RoofPlacement,
    RoofCoveringConfig,
    RoofFramingConfig,
)
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc


@pytest.fixture
def t_shape_roof_manifest() -> ProjectManifest:
    """Fixture providing a project manifest with a non-convex T-shaped composite hip roof."""
    axes_x = {"1": 0.00, "2": 4.00, "3": 8.00, "4": 12.00}
    axes_y = {"A": 0.00, "B": 4.00, "C": 8.00}

    # T-shape: Main Wing (1..4 x A..B = 12x4m) + Stem/Porch (2..3 x B..C = 4x4m)
    roof = IfcRoof(
        tag="ROOF-T-SHAPE",
        material="CONCRETE_TILE",
        roof_type="T_SHAPE_HIP",
        pitch_deg=30.0,
        placement=RoofPlacement(
            boundary=[
                ("1", "A"),
                ("4", "A"),
                ("4", "B"),
                ("3", "B"),  # Re-entrant corner R0
                ("3", "C"),
                ("2", "C"),
                ("2", "B"),  # Re-entrant corner R1
                ("1", "B"),
            ],
            storey="ST-02",
            offset_z=0.0,
            overhang=1.0,
            porch_eaves_level=0.00,
            main_ridge_height=3.00,
            porch_ridge_height=3.00,
        ),
        covering=RoofCoveringConfig(
            tile_type="CONCRETE_TILE",
            pitch=30.0,
            insulation=True,
            fascia_board=True,
            ridge_cap=True,
        ),
        framing=RoofFramingConfig(
            truss_type="STEEL_TRUSS",
            spacing=1.0,
            purlin_spacing=0.32,
            steel_weight_per_sqm=18.0,
        ),
    )

    return ProjectManifest(
        project=ProjectInfo(id="PRJ-TROOF", name="T-Shape Roof Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="ST-01", name="First Floor", elevation=0.0, height=3.5),
                Storey(id="ST-02", name="Second Floor / Roof Level", elevation=3.5, height=3.0),
            ]
        ),
        grids=Grids(axes_x=axes_x, axes_y=axes_y),
        materials=[
            Material(id="CONCRETE_TILE", name="Concrete Roof Tile", category="roofing", unit_cost_ref="MAT-TILE"),
            Material(id="STEEL_SS400", name="Structural Steel", category="steel", unit_cost_ref="MAT-STEEL"),
        ],
        elements=[roof],
    )


def test_t_shape_roof_3d_geometry_resolution(t_shape_roof_manifest):
    """Test 3D spatial resolution of T-shaped composite hip roof with hips and dual valleys."""
    resolved = resolve_manifest(t_shape_roof_manifest)
    assert len(resolved.roofs) == 1
    r_roof = resolved.roofs[0]

    assert r_roof.tag == "ROOF-T-SHAPE"
    assert r_roof.roof_type == "T_SHAPE_HIP"
    assert r_roof.pitch == 30.0

    # T-shape base area: Main (12x4 = 48m2) + Stem (4x4 = 16m2) = 64m2
    # Plus overhang (1.0m)
    assert r_roof.total_footprint_area > 64.0

    # Check ridges, hips, and valleys
    ridges_by_type = {}
    for r in r_roof.ridges:
        ridges_by_type.setdefault(r.ridge_type, []).append(r)

    # T-shape has 2 re-entrant corners producing 2 valley lines
    assert "VALLEY" in ridges_by_type
    assert len(ridges_by_type["VALLEY"]) >= 2
    assert r_roof.total_valley_length > 0.0

    # T-shape has 6 convex outer corners producing 6 hip lines
    assert "HIP" in ridges_by_type
    assert len(ridges_by_type["HIP"]) >= 6
    assert r_roof.total_hip_length > 0.0

    # T-shape has main ridge and porch/stem ridge
    assert "RIDGE" in ridges_by_type
    assert len(ridges_by_type["RIDGE"]) >= 2
    assert r_roof.total_ridge_length > 0.0

    # 8 eave perimeter segments
    assert "EAVE" in ridges_by_type
    assert len(ridges_by_type["EAVE"]) == 8

    # Check 3D sloped planes watertightness (8 planes covering the 8 footprint edges)
    assert len(r_roof.planes) == 8
    for p in r_roof.planes:
        assert p.area > 0.0
        assert len(p.polygon) in (3, 4)


def test_t_shape_roof_qto_and_framing(t_shape_roof_manifest):
    """Test QTO and steel framing synthesis for T-shaped hip roof."""
    resolved = resolve_manifest(t_shape_roof_manifest)
    r_roof = resolved.roofs[0]

    member_types = {m.member_type for m in r_roof.framing_members}
    assert "WALL_PLATE" in member_types
    assert "RIDGE_BEAM" in member_types
    assert "HIP_RAFTER" in member_types
    assert "VALLEY_RAFTER" in member_types
    assert "PURLIN" in member_types

    qto = calculate_qto(resolved)
    roof_qto = qto.get_element("ROOF-T-SHAPE")
    assert roof_qto is not None
    assert roof_qto.roof is not None
    assert roof_qto.roof.valley_cap_length > 0.0
    assert roof_qto.roof.hip_cap_length > 0.0
    assert qto.total_roof_valley_length == roof_qto.roof.valley_cap_length


def test_t_shape_roof_ifc_export(t_shape_roof_manifest, tmp_path: Path):
    """Test compiling T-shaped roof model to standard IFC file."""
    out_ifc = tmp_path / "t_shape_roof.ifc"
    compile_to_ifc(t_shape_roof_manifest, out_ifc)

    assert out_ifc.exists()
    assert out_ifc.stat().st_size > 1000

    content = out_ifc.read_text(encoding="utf-8")
    assert "IFCROOF" in content or "IfcRoof" in content
