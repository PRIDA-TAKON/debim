"""
Unit tests for Precision Geometric Extraction (Rotation, Exact Dimensions, True Elevation)
for OpenBIM Models in debim.
"""

from pathlib import Path
import pytest

from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.schema import Dimensions


DUPLEX_A_PATH = Path(__file__).parent / "fixtures" / "Duplex_A_20110907.ifc"


def test_precision_rotation_extraction():
    """Test that furniture and custom elements have non-trivial rotation angles extracted."""
    manifest = import_ifc_to_manifest(DUPLEX_A_PATH)
    furniture_elements = [
        e for e in manifest.elements if getattr(e, "layer", "") == "interior/furniture"
    ]
    assert len(furniture_elements) > 0

    rotations = [e.placement.rotation for e in furniture_elements if e.placement.rotation]
    assert len(rotations) > 0

    # Ensure various rotation angles (e.g. 90, 180 degrees in radians ~ 1.57, 3.14) are extracted
    has_non_zero_rot = any(
        any(abs(angle) > 0.01 for angle in rot) for rot in rotations
    )
    assert has_non_zero_rot, "Expected furniture to have extracted rotation angles"


def test_precision_elevation_correctness():
    """Test elevation correctness: upper level furniture sits at z ~ 3.10m, not double-elevated at 6.20m+."""
    manifest = import_ifc_to_manifest(DUPLEX_A_PATH)
    resolved = resolve_manifest(manifest)

    # Find upper floor furniture (e.g. beds with tag M_Bed-Standard)
    beds = [
        c for c in resolved.custom_elements if "Bed" in c.tag
    ]
    assert len(beds) > 0

    for bed in beds:
        world_z = bed.position[2]
        # Bed on level 2 should be at elevation ~3.10m, NOT double-elevated (6.20m+)
        assert 3.0 <= world_z <= 3.5, f"Expected bed elevation around 3.10m, got {world_z}"


def test_precision_bounding_box_dimensions():
    """Test that exact bounding box dimensions (width, depth, height) are populated on custom elements."""
    manifest = import_ifc_to_manifest(DUPLEX_A_PATH)
    furniture_elements = [
        e for e in manifest.elements if getattr(e, "layer", "") == "interior/furniture"
    ]

    elements_with_dims = [e for e in furniture_elements if e.dimensions is not None]
    assert len(elements_with_dims) > 0

    for elem in elements_with_dims:
        dims = elem.dimensions
        assert isinstance(dims, Dimensions)
        assert dims.width > 0.0
        assert dims.depth is not None and dims.depth > 0.0
        assert dims.height > 0.0


def _create_test_ifc_with_plates_and_parts(tmp_path: Path) -> Path:
    import ifcopenshell
    import ifcopenshell.api

    f = ifcopenshell.file(schema="IFC4")
    project = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="Plate Project")
    u_length = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[u_length])

    context = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body_context = ifcopenshell.api.run(
        "context.add_context",
        f,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )

    site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name="Building")
    storey = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Level 1")
    storey.Elevation = 0.0

    ifcopenshell.api.run("aggregate.assign_object", f, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[building], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[storey], relating_object=building)

    # 1. Horizontal Plate
    horiz_plate = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcPlate", name="HorizontalGussetPlate")
    ifcopenshell.api.run("spatial.assign_container", f, products=[horiz_plate], relating_structure=storey)

    profile_h = f.createIfcRectangleProfileDef("AREA", None, f.createIfcAxis2Placement2D(f.createIfcCartesianPoint((0.0, 0.0))), 2.0, 1.5)
    solid_h = f.createIfcExtrudedAreaSolid(
        profile_h,
        f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((1.0, 2.0, 0.0))),
        f.createIfcDirection((0.0, 0.0, 1.0)),
        0.02
    )
    rep_h = f.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid_h])
    ifcopenshell.api.run("geometry.assign_representation", f, product=horiz_plate, representation=rep_h)

    # 2. Vertical Plate
    vert_plate = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcPlate", name="VerticalConnectionPlate")
    ifcopenshell.api.run("spatial.assign_container", f, products=[vert_plate], relating_structure=storey)

    profile_v = f.createIfcRectangleProfileDef("AREA", None, f.createIfcAxis2Placement2D(f.createIfcCartesianPoint((0.0, 0.0))), 0.3, 0.4)
    solid_v = f.createIfcExtrudedAreaSolid(
        profile_v,
        f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((3.0, 2.0, 0.5))),
        f.createIfcDirection((1.0, 0.0, 0.0)),
        0.015
    )
    rep_v = f.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid_v])
    ifcopenshell.api.run("geometry.assign_representation", f, product=vert_plate, representation=rep_v)

    # 3. Building Element Part
    part_elem = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingElementPart", name="PrecastConnectionPart")
    ifcopenshell.api.run("spatial.assign_container", f, products=[part_elem], relating_structure=storey)

    profile_p = f.createIfcRectangleProfileDef("AREA", None, f.createIfcAxis2Placement2D(f.createIfcCartesianPoint((0.0, 0.0))), 0.5, 0.5)
    solid_p = f.createIfcExtrudedAreaSolid(
        profile_p,
        f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((5.0, 2.0, 0.0))),
        f.createIfcDirection((0.0, 0.0, 1.0)),
        0.05
    )
    rep_p = f.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid_p])
    ifcopenshell.api.run("geometry.assign_representation", f, product=part_elem, representation=rep_p)

    out_path = tmp_path / "test_plates.ifc"
    f.write(str(out_path))
    return out_path


def test_import_horizontal_and_vertical_ifc_plates(tmp_path: Path):
    """Test parsing and extraction of horizontal and vertical IfcPlate elements."""
    ifc_file_path = _create_test_ifc_with_plates_and_parts(tmp_path)
    manifest = import_ifc_to_manifest(ifc_file_path)

    plates = [e for e in manifest.elements if getattr(e, "layer", "") == "structure/plates"]
    assert len(plates) == 2

    # Horizontal plate
    horiz_plate = next((p for p in plates if p.name == "HorizontalGussetPlate"), None)
    assert horiz_plate is not None
    assert horiz_plate.dimensions is not None
    assert horiz_plate.dimensions.width == 2.0
    assert horiz_plate.dimensions.depth == 1.5
    assert horiz_plate.dimensions.height == 0.02

    # Vertical plate
    vert_plate = next((p for p in plates if p.name == "VerticalConnectionPlate"), None)
    assert vert_plate is not None
    assert vert_plate.dimensions is not None
    assert vert_plate.dimensions.width == 0.015
    assert vert_plate.dimensions.depth == 0.3
    assert vert_plate.dimensions.height == 0.4


def test_import_ifc_building_element_parts(tmp_path: Path):
    """Test parsing and extraction of IfcBuildingElementPart elements."""
    ifc_file_path = _create_test_ifc_with_plates_and_parts(tmp_path)
    manifest = import_ifc_to_manifest(ifc_file_path)

    parts = [e for e in manifest.elements if getattr(e, "layer", "") == "structure/parts"]
    assert len(parts) == 1

    part = parts[0]
    assert part.name == "PrecastConnectionPart"
    assert part.dimensions is not None
    assert part.dimensions.width == 0.5
    assert part.dimensions.depth == 0.5
    assert part.dimensions.height == 0.05
