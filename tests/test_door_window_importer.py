"""
Unit tests for IfcDoor and IfcWindow extraction and wall opening QTO void deductions.
"""

from pathlib import Path
import pytest

from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_element_qto, calculate_qto
from debim.schema import (
    Dimensions,
    IfcDoor,
    IfcWall,
    IfcWindow,
    ProjectManifest,
    WallPlacement,
)


@pytest.fixture
def duplex_manifest():
    fixture_path = Path(__file__).parent / "fixtures" / "Duplex_A_20110907.ifc"
    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")
    return import_ifc_to_manifest(fixture_path)


def test_import_duplex_doors_and_windows(duplex_manifest):
    """Verify that IfcDoor and IfcWindow are extracted from Duplex IFC model and attached to IfcWall children."""
    walls = [e for e in duplex_manifest.elements if isinstance(e, IfcWall)]
    assert len(walls) > 0, "No walls found in imported manifest"

    walls_with_children = [w for w in walls if w.children]
    assert len(walls_with_children) > 0, "Expected walls with door/window children"

    extracted_doors = []
    extracted_windows = []

    for wall in walls:
        for child in wall.children:
            if isinstance(child, IfcDoor):
                extracted_doors.append(child)
            elif isinstance(child, IfcWindow):
                extracted_windows.append(child)

    assert len(extracted_doors) == 14, f"Expected 14 doors, got {len(extracted_doors)}"
    assert len(extracted_windows) >= 22, f"Expected at least 22 windows, got {len(extracted_windows)}"

    for door in extracted_doors:
        assert door.dimensions.width > 0.0
        assert door.dimensions.height > 0.0
        assert door.offset_distance >= 0.0

    for win in extracted_windows:
        assert win.dimensions.width > 0.0
        assert win.dimensions.height > 0.0
        assert win.offset_distance >= 0.0


def test_wall_qto_opening_void_deduction():
    """Verify that calculate_element_qto correctly deducts door and window openings from wall volume/area."""
    door = IfcDoor(
        tag="DOOR-01",
        dimensions=Dimensions(width=1.0, height=2.0),
        offset_distance=1.0,
    )
    window = IfcWindow(
        tag="WIN-01",
        dimensions=Dimensions(width=1.5, height=1.5),
        offset_distance=3.0,
        sill_height=0.8,
    )

    # Wall 5m length x 3m height x 0.2m thickness
    # Gross volume = 5 * 3 * 0.2 = 3.0 m³
    # Gross formwork = 2 * (5 * 3) = 30.0 m²
    # Opening area = (1.0 * 2.0) + (1.5 * 1.5) = 2.0 + 2.25 = 4.25 m²
    # Opening volume = 4.25 * 0.2 = 0.85 m³
    # Net volume = 3.0 - 0.85 = 2.15 m³
    # Net formwork = 30.0 - 2 * 4.25 = 21.5 m²

    wall = IfcWall(
        tag="WALL-WITH-OPENINGS",
        material="CONC_280",
        thickness=0.20,
        height=3.00,
        placement=WallPlacement(from_grid=("GX_1", "GY_1"), to_grid=("GX_2", "GY_1"), storey="GL"),
        children=[door, window],
    )

    manifest = ProjectManifest.model_validate({
        "schema": "IFC4-Minimal",
        "project": {"id": "TEST", "name": "Test Project"},
        "spatial_structure": {"storeys": [{"id": "GL", "name": "Ground Floor", "elevation": 0.0, "height": 3.0}]},
        "grids": {"axes_x": {"GX_1": 0.0, "GX_2": 5.0}, "axes_y": {"GY_1": 0.0}},
        "materials": [{"id": "CONC_280", "name": "Concrete 280", "category": "concrete", "unit_cost_ref": "REF"}],
        "elements": [wall],
    })

    resolved = resolve_manifest(manifest)
    r_wall = resolved.walls[0]

    eqto = calculate_element_qto(r_wall, manifest)

    assert pytest.approx(eqto.concrete_volume, abs=1e-3) == 2.15
    assert pytest.approx(eqto.formwork_area, abs=1e-3) == 21.5


def test_duplex_overall_wall_qto_reduction(duplex_manifest):
    """Verify that calculate_qto on Duplex manifest calculates wall volume in expected 205-215 m3 range."""
    project_qto = calculate_qto(duplex_manifest)
    wall_volume = sum(e.concrete_volume for e in project_qto.elements if e.element_class == "IfcWall")

    assert 205.0 <= wall_volume <= 215.0, f"Expected wall volume between 205 and 215 m3, got {wall_volume}"


def test_door_window_dual_sub_mesh_structure():
    """Verify that ResolvedDoor and ResolvedWindow compute dual geometric sub-meshes (frame_box & panel_box)."""
    door = IfcDoor(
        tag="DOOR-DUAL-01",
        dimensions=Dimensions(width=0.90, height=2.10),
        offset_distance=1.0,
        frame_thickness=0.060,
    )
    window = IfcWindow(
        tag="WIN-DUAL-01",
        dimensions=Dimensions(width=1.20, height=1.50),
        offset_distance=2.5,
        frame_thickness=0.050,
        sill_height=0.80,
    )

    wall = IfcWall(
        tag="WALL-DUAL-TEST",
        material="CONC_280",
        thickness=0.15,
        height=3.00,
        placement=WallPlacement(from_grid=("GX_1", "GY_1"), to_grid=("GX_2", "GY_1"), storey="GL"),
        children=[door, window],
    )

    manifest = ProjectManifest.model_validate({
        "schema": "IFC4-Minimal",
        "project": {"id": "DUAL_TEST", "name": "Dual Sub-Mesh Test Project"},
        "spatial_structure": {"storeys": [{"id": "GL", "name": "Ground Floor", "elevation": 0.0, "height": 3.0}]},
        "grids": {"axes_x": {"GX_1": 0.0, "GX_2": 5.0}, "axes_y": {"GY_1": 0.0}},
        "materials": [{"id": "CONC_280", "name": "Concrete 280", "category": "concrete", "unit_cost_ref": "REF"}],
        "elements": [wall],
    })

    resolved = resolve_manifest(manifest)
    r_door = resolved.doors[0]
    r_win = resolved.windows[0]

    # Check ResolvedDoor sub-mesh structure
    assert r_door.frame_thickness == 0.060
    assert r_door.frame_width == 0.050
    assert r_door.panel_recess == 0.015
    assert r_door.panel_thickness == 0.035

    assert r_door.frame_box == {"width": 0.90, "depth": 0.060, "height": 2.10}
    assert r_door.panel_box == {
        "width": pytest.approx(0.80),
        "depth": 0.035,
        "height": pytest.approx(2.05),
        "offset_y": 0.015,
    }
    assert "frame" in r_door.sub_meshes and "panel" in r_door.sub_meshes

    # Check ResolvedWindow sub-mesh structure
    assert r_win.frame_thickness == 0.050
    assert r_win.frame_width == 0.050
    assert r_win.panel_recess == 0.015
    assert r_win.panel_thickness == 0.015

    assert r_win.frame_box == {"width": 1.20, "depth": 0.050, "height": 1.50}
    assert r_win.panel_box == {
        "width": pytest.approx(1.10),
        "depth": 0.015,
        "height": pytest.approx(1.40),
        "offset_y": 0.015,
    }
    assert "frame" in r_win.sub_meshes and "panel" in r_win.sub_meshes


def test_reversed_wall_door_window_placement(tmp_path):
    """Test that doors and windows on reversed walls calculate inverted offset_distance and flipped orientation."""
    import ifcopenshell
    import ifcopenshell.api

    f = ifcopenshell.file(schema="IFC4")
    project = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="Test Project")
    ifcopenshell.api.run("unit.assign_unit", f)
    storey = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Level 1")

    # Reversed Wall (local matrix at (5,0,0), Axis vector going from (0,0,0) to (-5,0,0) in local coords)
    wall_reversed = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="WALL-REV")
    ifcopenshell.api.run("spatial.assign_container", f, relating_structure=storey, products=[wall_reversed])

    pt_loc = f.createIfcCartesianPoint((5.0, 0.0, 0.0))
    place_rev = f.createIfcAxis2Placement3D(Location=pt_loc)
    wall_reversed.ObjectPlacement = f.createIfcLocalPlacement(RelativePlacement=place_rev)

    pt1 = f.createIfcCartesianPoint((0.0, 0.0, 0.0))
    pt2 = f.createIfcCartesianPoint((-5.0, 0.0, 0.0))
    poly = f.createIfcPolyline((pt1, pt2))
    context = f.createIfcGeometricRepresentationContext(ContextType="Model", CoordinateSpaceDimension=3, Precision=1e-5)
    rep_axis = f.createIfcShapeRepresentation(
        ContextOfItems=context,
        RepresentationIdentifier="Axis",
        RepresentationType="Curve2D",
        Items=[poly],
    )
    wall_reversed.Representation = f.createIfcProductDefinitionShape(Representations=[rep_axis])

    door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor", name="DOOR-REV")
    door.OverallWidth = 1.0
    door.OverallHeight = 2.1
    door.OperationType = "SINGLE_SWING_LEFT"

    opening = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcOpeningElement", name="OPENING-REV")
    pt_open = f.createIfcCartesianPoint((1.0, 0.0, 0.0))
    place_open = f.createIfcAxis2Placement3D(Location=pt_open)
    opening.ObjectPlacement = f.createIfcLocalPlacement(PlacementRelTo=wall_reversed.ObjectPlacement, RelativePlacement=place_open)
    door.ObjectPlacement = f.createIfcLocalPlacement(PlacementRelTo=opening.ObjectPlacement, RelativePlacement=f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 0.0))))

    f.createIfcRelVoidsElement(GlobalId=ifcopenshell.guid.new(), RelatingBuildingElement=wall_reversed, RelatedOpeningElement=opening)
    f.createIfcRelFillsElement(GlobalId=ifcopenshell.guid.new(), RelatingOpeningElement=opening, RelatedBuildingElement=door)

    ifc_file_path = tmp_path / "reversed_wall_test.ifc"
    f.write(str(ifc_file_path))

    manifest = import_ifc_to_manifest(ifc_file_path)
    door_extracted = None
    for elem in manifest.elements:
        if isinstance(elem, IfcWall):
            for child in elem.children:
                if child.tag == "DOOR-REV":
                    door_extracted = child

    assert door_extracted is not None
    assert door_extracted.flipped is True
    assert door_extracted.operation_type == "SINGLE_SWING_LEFT"
    # Wall length = 5.0, raw dx = 1.0, width = 1.0
    # Reversed wall offset = 5.0 - 1.0 - 1.0 = 3.0
    assert pytest.approx(door_extracted.offset_distance, abs=1e-2) == 3.0
