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
