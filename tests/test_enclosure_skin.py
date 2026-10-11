"""
Unit tests for Enclosure & Skin Entities (IfcRoof, IfcCurtainWall, IfcPlate).
"""

import pytest
from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    CurtainWallPlacement,
    IfcCurtainWall,
    IfcPlate,
    IfcRoof,
    PlatePlacement,
    ProjectManifest,
    RoofCoveringConfig,
    RoofFramingConfig,
    RoofPlacement,
)
from debim.viewer import generate_viewer_html


@pytest.fixture
def base_manifest_data():
    return {
        "schema": "IFC4-Minimal",
        "project": {
            "id": "PROJ-SKIN-01",
            "name": "Enclosure Skin Test Project",
            "location": "Bangkok",
        },
        "spatial_structure": {
            "site": "Main Site",
            "building": "Facade Building",
            "storeys": [
                {"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.5},
                {"id": "FL2", "name": "Floor 2", "elevation": 3.5, "height": 3.5},
            ],
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 6.0, "3": 12.0},
            "axes_y": {"A": 0.0, "B": 8.0},
        },
        "materials": [
            {"id": "CONC_280", "name": "Concrete 280kcm", "category": "Concrete", "unit_cost_ref": "C280"},
            {"id": "ALUM_FRAME", "name": "Aluminium Frame", "category": "Metal", "unit_cost_ref": "AL01"},
            {"id": "GLASS_CLEAR", "name": "Clear Glass 10mm", "category": "Glass", "unit_cost_ref": "GL01"},
            {"id": "STEEL_SS400", "name": "Structural Steel SS400", "category": "Steel", "unit_cost_ref": "ST01"},
        ],
    }


def test_roof_expanded_predefined_types(base_manifest_data):
    manifest_data = dict(base_manifest_data)
    manifest_data["elements"] = [
        IfcRoof(
            tag="ROOF-01",
            material="CONC_280",
            roof_type="GABLE_ROOF",
            predefined_type="GABLE_ROOF",
            placement=RoofPlacement(
                boundary=[("1", "A"), ("3", "A"), ("3", "B"), ("1", "B")],
                storey="FL2",
                offset_z=3.5,
                overhang=1.0,
            ),
            covering=RoofCoveringConfig(pitch=30.0, tile_type="CONCRETE_TILE"),
            framing=RoofFramingConfig(truss_type="STEEL_TRUSS", material="STEEL_SS400"),
        )
    ]

    manifest = ProjectManifest(**manifest_data)
    resolved = resolve_manifest(manifest)

    assert len(resolved.roofs) == 1
    roof = resolved.roofs[0]
    assert roof.roof_type == "GABLE_ROOF"
    assert roof.total_footprint_area == (12.0 + 2.0) * (8.0 + 2.0)  # 14 * 10 = 140 m2
    assert roof.total_sloped_area > roof.total_footprint_area
    assert roof.total_ridge_length == 14.0 or roof.total_ridge_length == 10.0

    qto = calculate_qto(resolved)
    assert qto.total_roof_covering_area > 0.0
    assert qto.total_roof_purlin_length > 0.0


def test_curtain_wall_resolution_and_qto(base_manifest_data):
    manifest_data = dict(base_manifest_data)
    manifest_data["elements"] = [
        IfcCurtainWall(
            tag="CW-01",
            name="Main Entrance Glass Facade",
            predefined_type="POST_AND_BEAM",
            height=3.5,
            mullion_spacing_h=1.5,
            mullion_spacing_v=1.75,
            mullion_width=0.06,
            mullion_depth=0.12,
            glass_thickness=0.012,
            frame_material="ALUM_FRAME",
            glass_material="GLASS_CLEAR",
            placement=CurtainWallPlacement(
                from_grid=("1", "A"),
                to_grid=("3", "A"),
                storey="FL1",
                offset_z=0.0,
            ),
        )
    ]

    manifest = ProjectManifest(**manifest_data)
    resolved = resolve_manifest(manifest)

    assert len(resolved.curtain_walls) == 1
    cw = resolved.curtain_walls[0]
    assert cw.length == 12.0
    assert cw.height == 3.5
    assert cw.gross_facade_area == 42.0  # 12 * 3.5
    assert cw.glass_panel_count == 8 * 2  # 8 bays x 2 tiers = 16 panels
    assert cw.total_mullion_length > 0.0

    qto = calculate_qto(resolved)
    assert qto.total_curtain_wall_facade_area == 42.0
    assert qto.total_curtain_wall_glass_panel_count == 16
    assert qto.total_curtain_wall_mullion_length > 0.0


def test_plate_resolution_and_qto(base_manifest_data):
    manifest_data = dict(base_manifest_data)
    manifest_data["elements"] = [
        IfcPlate(
            tag="PLATE-01",
            name="Aluminium Composite Cladding Panel",
            predefined_type="SHEET",
            material="ALUM_FRAME",
            thickness=0.004,
            width=2.0,
            depth=3.0,
            density=2700.0,
            placement=PlatePlacement(
                grid=("2", "A"),
                storey="FL1",
                offset_z=1.0,
            ),
        ),
        IfcPlate(
            tag="PLATE-GUSSET-01",
            name="Steel Connection Flange Plate",
            predefined_type="FLANGE_PLATE",
            material="STEEL_SS400",
            thickness=0.020,
            width=0.4,
            depth=0.4,
            density=7850.0,
            placement=PlatePlacement(
                grid=("1", "B"),
                storey="FL2",
            ),
        ),
    ]

    manifest = ProjectManifest(**manifest_data)
    resolved = resolve_manifest(manifest)

    assert len(resolved.plates) == 2
    p1 = resolved.plates[0]
    assert p1.area == 6.0  # 2.0 * 3.0
    assert pytest.approx(p1.volume, 1e-4) == 0.024
    assert pytest.approx(p1.weight, 1e-2) == 0.024 * 2700.0

    p2 = resolved.plates[1]
    assert pytest.approx(p2.area, 1e-4) == 0.16
    assert pytest.approx(p2.weight, 1e-2) == 0.16 * 0.020 * 7850.0

    qto = calculate_qto(resolved)
    assert pytest.approx(qto.total_plate_area, 1e-2) == 6.16
    assert qto.total_plate_weight > 0.0


def test_enclosure_skin_ifc_compilation(base_manifest_data, tmp_path):
    manifest_data = dict(base_manifest_data)
    manifest_data["elements"] = [
        IfcRoof(
            tag="ROOF-01",
            material="CONC_280",
            roof_type="HIP_ROOF",
            placement=RoofPlacement(
                boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                storey="FL2",
            ),
        ),
        IfcCurtainWall(
            tag="CW-01",
            predefined_type="UNITIZED",
            placement=CurtainWallPlacement(
                from_grid=("1", "A"),
                to_grid=("2", "A"),
                storey="FL1",
            ),
        ),
        IfcPlate(
            tag="PLATE-01",
            predefined_type="CURTAIN_PANEL",
            placement=PlatePlacement(
                grid=("1", "A"),
                storey="FL1",
            ),
        ),
    ]

    manifest = ProjectManifest(**manifest_data)
    resolved = resolve_manifest(manifest)

    # STEP Text compilation
    step_file = compile_to_ifc(resolved, output_path=tmp_path / "step.ifc", force_fallback=True)
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCROOF" in step_content.upper()
    assert "IFCCURTAINWALL" in step_content.upper()
    assert "IFCPLATE" in step_content.upper()

    # IfcOpenShell compilation
    ifc_file = compile_to_ifc(resolved, output_path=tmp_path / "ifcopenshell.ifc", force_fallback=False)
    import ifcopenshell
    ifc_model = ifcopenshell.open(str(ifc_file))
    assert len(ifc_model.by_type("IfcRoof")) >= 1
    assert len(ifc_model.by_type("IfcCurtainWall")) >= 1
    assert len(ifc_model.by_type("IfcPlate")) >= 1


def test_viewer_data_generation_for_enclosure(base_manifest_data):
    manifest_data = dict(base_manifest_data)
    manifest_data["elements"] = [
        IfcCurtainWall(
            tag="CW-01",
            placement=CurtainWallPlacement(
                from_grid=("1", "A"),
                to_grid=("2", "A"),
                storey="FL1",
            ),
        ),
        IfcPlate(
            tag="PLATE-01",
            placement=PlatePlacement(
                grid=("1", "A"),
                storey="FL1",
            ),
        ),
    ]

    manifest = ProjectManifest(**manifest_data)
    resolved = resolve_manifest(manifest)

    html_output = generate_viewer_html(resolved)
    assert "IfcPlate" in html_output or "CW-01" in html_output
    assert "CW-01" in html_output
    assert "PLATE-01" in html_output
