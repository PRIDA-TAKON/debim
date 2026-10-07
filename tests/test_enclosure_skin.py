"""
Unit tests for Enclosure & Skin entities (IfcRoof, IfcCurtainWall, IfcPlate).
Validates Pydantic schema validation, 3D spatial resolution, QTO formulas,
IFC compilation, and 3D web viewer generation.
"""

import math
from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.schema import (
    CurtainWallPlacement,
    Grids,
    IfcCurtainWall,
    IfcPlate,
    IfcRoof,
    Material,
    PlatePlacement,
    ProjectInfo,
    ProjectManifest,
    RoofCoveringConfig,
    RoofFramingConfig,
    RoofPlacement,
    SpatialStructure,
    Storey,
    load_manifest,
)
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html


@pytest.fixture
def enclosure_skin_manifest() -> ProjectManifest:
    """Fixture providing a project manifest with roofs, curtain walls, and plates."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-SKIN-01", name="Enclosure & Skin Test Building"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Ground Level", elevation=0.0, height=3.5),
                Storey(id="L2", name="Second Floor", elevation=3.5, height=3.5),
                Storey(id="ROOF", name="Roof Level", elevation=7.0, height=2.0),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0, "3": 12.0},
            axes_y={"A": 0.0, "B": 8.0, "C": 16.0},
        ),
        materials=[
            Material(id="GLASS_FACADE", name="Double Glazed Glass", category="glass", unit_cost_ref="MAT-GLASS-01"),
            Material(id="ALUM_FRAME", name="Aluminum Frame", category="metal", unit_cost_ref="MAT-ALUM-01"),
            Material(id="STEEL_SS400", name="Structural Steel Plate", category="steel", unit_cost_ref="MAT-STEEL-01"),
            Material(id="CLAD_PANEL", name="ACP Cladding Panel", category="metal", unit_cost_ref="MAT-CLAD-01"),
            Material(id="CONC_TILE", name="Concrete Roof Tile", category="covering", unit_cost_ref="MAT-ROOF-TILE"),
        ],
        elements=[
            # 1. Hip Roof
            IfcRoof(
                tag="ROOF-01",
                material="CONC_TILE",
                roof_type="HIP",
                placement=RoofPlacement(
                    boundary=[("1", "A"), ("3", "A"), ("3", "C"), ("1", "C")],
                    storey="ROOF",
                    overhang=1.0,
                    ridge_orientation="X",
                ),
                covering=RoofCoveringConfig(
                    tile_type="CONCRETE_TILE",
                    pitch=30.0,
                    insulation=True,
                ),
                framing=RoofFramingConfig(
                    truss_type="STEEL_TRUSS",
                    material="STEEL_SS400",
                    spacing=1.0,
                    purlin_spacing=0.32,
                    steel_weight_per_sqm=20.0,
                ),
            ),
            # 2. Curtain Wall Facade
            IfcCurtainWall(
                tag="CW-01",
                material="GLASS_FACADE",
                predefined_type="POST_AND_BEAM",
                height=3.50,
                mullion_spacing_h=1.20,
                mullion_spacing_v=1.75,
                mullion_width=0.05,
                mullion_depth=0.15,
                glass_thickness=0.008,
                frame_material="ALUM_FRAME",
                placement=CurtainWallPlacement(
                    from_grid=("1", "A"),
                    to_grid=("3", "A"),
                    storey="L1",
                    offset_z=0.0,
                ),
            ),
            # 3. Base Plate (Steel Gusset / Anchor Plate)
            IfcPlate(
                tag="PLATE-BASE-01",
                material="STEEL_SS400",
                predefined_type="BASE_PLATE",
                thickness=0.025,
                width=0.50,
                depth=0.50,
                density_kg_m3=7850.0,
                placement=PlatePlacement(
                    storey="L1",
                    grid=("1", "A"),
                    offset_x=0.0,
                    offset_y=0.0,
                    offset_z=0.0,
                ),
            ),
            # 4. Cladding Panel Plate with boundary grid polygon
            IfcPlate(
                tag="PLATE-CLAD-01",
                material="CLAD_PANEL",
                predefined_type="SHEET",
                thickness=0.004,
                density_kg_m3=2700.0,
                placement=PlatePlacement(
                    storey="L2",
                    boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                    offset_z=0.0,
                ),
            ),
        ],
    )


def test_enclosure_schema_validation(enclosure_skin_manifest):
    """Test schema instantiation and validation for IfcRoof, IfcCurtainWall, and IfcPlate."""
    assert len(enclosure_skin_manifest.elements) == 4
    cw = [e for e in enclosure_skin_manifest.elements if isinstance(e, IfcCurtainWall)][0]
    plate = [e for e in enclosure_skin_manifest.elements if isinstance(e, IfcPlate) and e.tag == "PLATE-BASE-01"][0]

    assert cw.tag == "CW-01"
    assert cw.predefined_type == "POST_AND_BEAM"
    assert cw.height == 3.50
    assert cw.mullion_spacing_h == 1.20

    assert plate.tag == "PLATE-BASE-01"
    assert plate.predefined_type == "BASE_PLATE"
    assert plate.thickness == 0.025
    assert plate.width == 0.50
    assert plate.depth == 0.50


def test_enclosure_schema_invalid_reference():
    """Test that invalid storey or material references raise ValidationError."""
    with pytest.raises(ValidationError):
        ProjectManifest(
            project=ProjectInfo(id="PRJ-ERR", name="Error Building"),
            spatial_structure=SpatialStructure(
                storeys=[Storey(id="L1", name="Level 1", elevation=0.0, height=3.0)]
            ),
            grids=Grids(axes_x={"1": 0.0, "2": 5.0}, axes_y={"A": 0.0, "B": 5.0}),
            materials=[Material(id="GLASS", name="Glass", category="glass", unit_cost_ref="MAT-G")],
            elements=[
                IfcCurtainWall(
                    tag="CW-BAD",
                    material="UNKNOWN_MAT",  # Unknown material
                    placement=CurtainWallPlacement(
                        from_grid=("1", "A"),
                        to_grid=("2", "A"),
                        storey="L1",
                    ),
                )
            ],
        )


def test_curtain_wall_spatial_resolution(enclosure_skin_manifest):
    """Test 3D spatial resolution of curtain walls."""
    resolved = resolve_manifest(enclosure_skin_manifest)
    assert len(resolved.curtain_walls) == 1
    r_cw = resolved.curtain_walls[0]

    # Length along X grid 1 to 3 = 12.0m, Height = 3.5m
    assert math.isclose(r_cw.length, 12.0, rel_tol=1e-3)
    assert math.isclose(r_cw.height, 3.5, rel_tol=1e-3)

    # Gross facade area = 12.0 * 3.5 = 42.0 m2
    assert math.isclose(r_cw.gross_facade_area, 42.0, rel_tol=1e-3)

    # Horizontal bays: 12.0 / 1.2 = 10 bays -> 11 vertical mullions
    # Vertical bays: 3.5 / 1.75 = 2 bays -> 3 horizontal transoms
    # Panel count = 10 * 2 = 20 panels
    assert r_cw.glass_panels_count == 20

    # Grid lines = (11 vertical mullions of length 3.5m) + (3 horizontal transoms of length 12.0m)
    # Total mullion linear length = 11*3.5 + 3*12.0 = 38.5 + 36.0 = 74.5m
    assert math.isclose(r_cw.mullion_length, 74.5, rel_tol=1e-2)
    assert len(r_cw.mullion_grid_lines) == 14
    assert r_cw.layer == "architecture/facades/curtain_walls"


def test_plate_spatial_resolution(enclosure_skin_manifest):
    """Test 3D spatial resolution of rectangular base plates and polygon cladding plates."""
    resolved = resolve_manifest(enclosure_skin_manifest)
    assert len(resolved.plates) == 2

    # Base plate
    p_base = [p for p in resolved.plates if p.tag == "PLATE-BASE-01"][0]
    assert math.isclose(p_base.area, 0.25, rel_tol=1e-3)  # 0.5 * 0.5 = 0.25 m2
    assert math.isclose(p_base.volume, 0.25 * 0.025, rel_tol=1e-3)  # 0.00625 m3
    # Weight = 0.00625 m3 * 7850 kg/m3 = 49.0625 kg
    assert math.isclose(p_base.weight, 49.0625, rel_tol=1e-3)
    assert p_base.layer == "structure/plates"

    # Polygon Cladding Plate (boundary 0..6 in X, 0..8 in Y -> 48.0 m2)
    p_clad = [p for p in resolved.plates if p.tag == "PLATE-CLAD-01"][0]
    assert math.isclose(p_clad.area, 48.0, rel_tol=1e-3)
    assert math.isclose(p_clad.volume, 48.0 * 0.004, rel_tol=1e-3)  # 0.192 m3
    # Weight = 0.192 m3 * 2700 kg/m3 = 518.4 kg
    assert math.isclose(p_clad.weight, 518.4, rel_tol=1e-3)
    assert p_clad.layer == "architecture/cladding"


def test_qto_takeoff_aggregation(enclosure_skin_manifest):
    """Test QTO calculation and project-wide aggregation for enclosure and skin entities."""
    resolved = resolve_manifest(enclosure_skin_manifest)
    qto = calculate_qto(resolved)

    # Curtain Wall QTO
    cw_elem = qto.get_element("CW-01")
    assert cw_elem is not None
    assert cw_elem.curtain_wall is not None
    assert math.isclose(cw_elem.curtain_wall.facade_area, 42.0, rel_tol=1e-3)
    assert cw_elem.curtain_wall.glass_panels_count == 20
    assert cw_elem.curtain_wall.mullion_length > 70.0
    # Mullion weight = 74.5m * (0.05m * 0.15m) * 2700 kg/m3 = 1508.625 kg
    assert cw_elem.curtain_wall.mullion_weight > 1000.0

    # Plate QTO
    plate_base_elem = qto.get_element("PLATE-BASE-01")
    assert plate_base_elem is not None
    assert plate_base_elem.plate is not None
    assert math.isclose(plate_base_elem.plate.area, 0.25, rel_tol=1e-3)
    assert math.isclose(plate_base_elem.plate.weight, 49.0625, rel_tol=1e-3)

    # Project-wide Aggregation
    assert math.isclose(qto.total_curtain_wall_facade_area, 42.0, rel_tol=1e-3)
    assert qto.total_curtain_wall_glass_panels_count == 20
    assert qto.total_curtain_wall_mullion_length > 70.0

    assert math.isclose(qto.total_plate_area, 48.25, rel_tol=1e-3)  # 0.25 + 48.0 = 48.25 m2
    assert math.isclose(qto.total_plate_weight, 49.0625 + 518.4, rel_tol=1e-3)  # 567.4625 kg


def test_ifc_compilation(enclosure_skin_manifest, tmp_path):
    """Test compiling enclosure and skin manifest to IFC STEP file."""
    output_ifc = tmp_path / "enclosure_skin.ifc"
    compile_to_ifc(enclosure_skin_manifest, output_ifc)

    assert output_ifc.exists()
    content = output_ifc.read_text(encoding="utf-8")

    assert "IFCROOF" in content.upper()
    assert "IFCCURTAINWALL" in content.upper()
    assert "IFCPLATE" in content.upper()


def test_viewer_html_generation(enclosure_skin_manifest):
    """Test generating 3D Web Viewer HTML for enclosure and skin entities."""
    html = generate_viewer_html(enclosure_skin_manifest)

    assert "IfcRoofCovering" in html
    assert "IfcCurtainWall" in html
    assert "IfcPlate" in html
    assert "architecture/facades/curtain_walls" in html
    assert "architecture/cladding" in html
    assert "structure/plates" in html
