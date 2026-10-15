"""Unit tests for L-shaped composite hip roof geometry, multi-level eaves, dual ridge heights,

intersecting hips/valleys 3D solver, structural framing synthesis, QTO, and IFC compilation.
"""

import math
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
def l_shape_roof_manifest() -> ProjectManifest:
    """Fixture providing a project manifest with a non-convex L-shaped composite hip roof."""
    axes_x = {"1": 0.00, "2": 4.00, "3": 8.00}
    axes_y = {"A": 0.00, "B": 4.00, "C": 10.00}

    roof = IfcRoof(
        tag="ROOF-L-SHAPE",
        material="CONCRETE_TILE",
        roof_type="L_SHAPE_HIP",
        pitch_deg=30.0,
        placement=RoofPlacement(
            boundary=[
                ("1", "A"),
                ("3", "A"),
                ("3", "B"),
                ("2", "B"),
                ("2", "C"),
                ("1", "C"),
            ],
            storey="ST-02",
            offset_z=0.0,
            overhang=1.0,
            porch_eaves_level=-0.50,
            main_ridge_height=3.50,
            porch_ridge_height=2.50,
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
            profiles={
                "rafter": "C100x50x20x3.2",
                "purlin": "C75x45x15x2.3",
                "ridge": "2C150x50x20x3.2",
                "hip": "2C150x50x20x3.2",
                "valley": "2C150x50x20x3.2",
                "wall_plate": "C150x50x20x3.2",
            },
        ),
    )

    return ProjectManifest(
        project=ProjectInfo(id="PRJ-LROOF", name="L-Shape Roof Test Project"),
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


def test_l_shape_roof_geometry_resolution(l_shape_roof_manifest):
    """Test 3D spatial resolution of L-shaped composite hip roof with hips and valleys."""
    resolved = resolve_manifest(l_shape_roof_manifest)
    assert len(resolved.roofs) == 1
    r_roof = resolved.roofs[0]

    assert r_roof.tag == "ROOF-L-SHAPE"
    assert r_roof.roof_type == "L_SHAPE_HIP"
    assert r_roof.pitch == 30.0

    # L-shape footprint: Main Wing (1..3 x A..B = 8x4m) + Porch Wing (1..2 x B..C = 4x6m) = 32m2
    # Plus overhang (1.0m)
    assert r_roof.total_footprint_area > 32.0

    # Verify intersecting hips (สันตะเข้) and valleys (ตะเข้ราง) presence
    ridges_by_type = {}
    for r in r_roof.ridges:
        ridges_by_type.setdefault(r.ridge_type, []).append(r)

    assert "VALLEY" in ridges_by_type
    assert len(ridges_by_type["VALLEY"]) >= 1
    assert r_roof.total_valley_length > 0.0

    assert "HIP" in ridges_by_type
    assert len(ridges_by_type["HIP"]) >= 4
    assert r_roof.total_hip_length > 0.0

    assert "RIDGE" in ridges_by_type
    assert len(ridges_by_type["RIDGE"]) >= 1
    assert r_roof.total_ridge_length > 0.0

    assert "EAVE" in ridges_by_type
    assert len(ridges_by_type["EAVE"]) == 6


def test_l_shape_roof_framing_takeoff(l_shape_roof_manifest):
    """Test structural steel framing synthesis (wall plates, ridge/hip/valley rafters, purlins)."""
    resolved = resolve_manifest(l_shape_roof_manifest)
    r_roof = resolved.roofs[0]

    member_types = {m.member_type for m in r_roof.framing_members}

    assert "WALL_PLATE" in member_types
    assert "RIDGE_BEAM" in member_types
    assert "HIP_RAFTER" in member_types
    assert "VALLEY_RAFTER" in member_types
    assert "COMMON_RAFTER" in member_types or "JACK_RAFTER" in member_types
    assert "PURLIN" in member_types
    assert "KING_POST" in member_types

    # Check non-zero total steel framing weight
    qto = calculate_qto(resolved)
    roof_elem_qto = qto.get_element("ROOF-L-SHAPE")

    assert roof_elem_qto is not None
    assert roof_elem_qto.roof is not None
    assert roof_elem_qto.roof.purlin_length > 0.0
    assert roof_elem_qto.roof.rafter_length > 0.0
    assert roof_elem_qto.roof.valley_cap_length > 0.0
    assert qto.total_roof_valley_length == roof_elem_qto.roof.valley_cap_length


def test_l_shape_roof_ifc_compilation(l_shape_roof_manifest, tmp_path: Path):
    """Test compiling L-shaped roof model to standard IFC file."""
    out_ifc = tmp_path / "l_shape_roof.ifc"
    compile_to_ifc(l_shape_roof_manifest, out_ifc)

    assert out_ifc.exists()
    assert out_ifc.stat().st_size > 1000

    content = out_ifc.read_text(encoding="utf-8")
    assert "IFCROOF" in content or "IfcRoof" in content
