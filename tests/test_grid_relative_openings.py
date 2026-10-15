"""
Unit tests for grid-relative parametric placement of doors and windows in host walls.
"""

import pytest
from pydantic import ValidationError
from debim.schema import ProjectManifest, IfcDoor, IfcWindow
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc


def test_door_and_window_at_grid_x_axis():
    manifest_data = {
        "project": {"id": "TEST_OPENINGS_X", "name": "Test Grid Openings X"},
        "spatial_structure": {
            "storeys": [{"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 5.0},
        },
        "materials": [
            {"id": "CONCRETE", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "C1"},
            {"id": "BRICK", "name": "Brick", "category": "MASONRY", "unit_cost_ref": "M1"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-1",
                "material": "BRICK",
                "thickness": 0.15,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["3", "A"], "storey": "FL1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "DOOR-1",
                        "dimensions": {"width": 0.90, "height": 2.10},
                        "at_grid": "2 + 0.50",
                    },
                    {
                        "class": "IfcWindow",
                        "tag": "WIN-1",
                        "dimensions": {"width": 1.20, "height": 1.50},
                        "at_grid": "1 + 1.20",
                        "sill_height": 0.90,
                    },
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    door = resolved.doors[0]
    win = resolved.windows[0]

    assert door.tag == "DOOR-1"
    assert pytest.approx(door.offset_distance, abs=1e-3) == 4.50
    assert pytest.approx(door.position[0], abs=1e-3) == 4.50
    assert pytest.approx(door.position[1], abs=1e-3) == 0.0
    assert pytest.approx(door.position[2], abs=1e-3) == 0.0

    assert win.tag == "WIN-1"
    assert pytest.approx(win.offset_distance, abs=1e-3) == 1.20
    assert pytest.approx(win.position[0], abs=1e-3) == 1.20
    assert pytest.approx(win.position[1], abs=1e-3) == 0.0
    assert pytest.approx(win.position[2], abs=1e-3) == 0.90


def test_door_and_window_at_grid_y_axis():
    manifest_data = {
        "project": {"id": "TEST_OPENINGS_Y", "name": "Test Grid Openings Y"},
        "spatial_structure": {
            "storeys": [{"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 3.0},
            "axes_y": {"A": 0.0, "B": 5.0, "C": 10.0},
        },
        "materials": [
            {"id": "CONCRETE", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "C1"},
            {"id": "BRICK", "name": "Brick", "category": "MASONRY", "unit_cost_ref": "M1"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-Y",
                "material": "BRICK",
                "thickness": 0.20,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["1", "C"], "storey": "FL1"},
                "children": [
                    {
                        "class": "IfcWindow",
                        "tag": "WIN-Y1",
                        "dimensions": {"width": 1.50, "height": 1.20},
                        "at_grid": "B - 0.50",
                        "sill_height": 1.00,
                    }
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    win = resolved.windows[0]
    assert win.tag == "WIN-Y1"
    assert pytest.approx(win.offset_distance, abs=1e-3) == 4.50
    assert pytest.approx(win.position[0], abs=1e-3) == 0.0
    assert pytest.approx(win.position[1], abs=1e-3) == 4.50
    assert pytest.approx(win.position[2], abs=1e-3) == 1.00


def test_opening_dynamic_grid_update():
    manifest_data = {
        "project": {"id": "TEST_DYNAMIC", "name": "Test Dynamic Grid Update"},
        "spatial_structure": {
            "storeys": [{"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 5.0},
        },
        "materials": [
            {"id": "CONCRETE", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "C1"},
            {"id": "BRICK", "name": "Brick", "category": "MASONRY", "unit_cost_ref": "M1"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-DYN",
                "material": "BRICK",
                "thickness": 0.15,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["3", "A"], "storey": "FL1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "DOOR-DYN",
                        "dimensions": {"width": 1.0, "height": 2.0},
                        "at_grid": "2 + 1.00",
                    }
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)

    # Initial resolution: Grid 2 = 4.0 -> at_grid 2 + 1.00 = 5.00
    res1 = resolve_manifest(manifest)
    door1 = res1.doors[0]
    assert pytest.approx(door1.offset_distance, abs=1e-3) == 5.00
    assert pytest.approx(door1.position[0], abs=1e-3) == 5.00

    # Move Grid 2 from 4.0 to 6.0
    manifest.grids.axes_x["2"] = 6.0

    # Re-resolve manifest: Grid 2 = 6.0 -> at_grid 2 + 1.00 = 7.00
    res2 = resolve_manifest(manifest)
    door2 = res2.doors[0]
    assert pytest.approx(door2.offset_distance, abs=1e-3) == 7.00
    assert pytest.approx(door2.position[0], abs=1e-3) == 7.00


def test_opening_sloped_wall():
    manifest_data = {
        "project": {"id": "TEST_SLOPED", "name": "Test Sloped Wall Openings"},
        "spatial_structure": {
            "storeys": [{"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 3.0, "3": 6.0},
            "axes_y": {"A": 0.0, "B": 8.0},
        },
        "materials": [
            {"id": "CONCRETE", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "C1"},
            {"id": "BRICK", "name": "Brick", "category": "MASONRY", "unit_cost_ref": "M1"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-SLOPED",
                "material": "BRICK",
                "thickness": 0.15,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["3", "B"], "storey": "FL1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "DOOR-SLOPED",
                        "dimensions": {"width": 1.0, "height": 2.0},
                        "at_grid": "2",
                    }
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    door = resolved.doors[0]
    # Wall baseline: (0,0) to (6,8). Vector (6,8), length = 10, ux = 0.6, uy = 0.8
    # Grid 2 is X = 3.0. Scalar offset = (3.0 - 0) / 0.6 = 5.0
    assert pytest.approx(door.offset_distance, abs=1e-3) == 5.0
    assert pytest.approx(door.position[0], abs=1e-3) == 3.0
    assert pytest.approx(door.position[1], abs=1e-3) == 4.0


def test_opening_2d_grid_tuple():
    manifest_data = {
        "project": {"id": "TEST_2D_TUPLE", "name": "Test 2D Grid Tuple"},
        "spatial_structure": {
            "storeys": [{"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 3.0, "3": 6.0},
            "axes_y": {"A": 0.0, "B": 8.0},
        },
        "materials": [
            {"id": "CONCRETE", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "C1"},
            {"id": "BRICK", "name": "Brick", "category": "MASONRY", "unit_cost_ref": "M1"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-2D",
                "material": "BRICK",
                "thickness": 0.15,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["3", "B"], "storey": "FL1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "DOOR-2D",
                        "dimensions": {"width": 1.0, "height": 2.0},
                        "at_grid": ["2", "B"],
                    }
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    door = resolved.doors[0]
    # Point (3.0, 8.0), ux = 0.6, uy = 0.8.
    # Offset = 3.0 * 0.6 + 8.0 * 0.8 = 1.8 + 6.4 = 8.2
    assert pytest.approx(door.offset_distance, abs=1e-3) == 8.2
    assert pytest.approx(door.position[0], abs=1e-3) == 4.92
    assert pytest.approx(door.position[1], abs=1e-3) == 6.56


def test_opening_net_wall_qto_deduction():
    manifest_data = {
        "project": {"id": "TEST_QTO", "name": "Test Opening QTO Deduction"},
        "spatial_structure": {
            "storeys": [{"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 5.0},
        },
        "materials": [
            {"id": "MASONRY", "name": "Brick", "category": "MASONRY", "unit_cost_ref": "M1"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-QTO",
                "material": "MASONRY",
                "thickness": 0.15,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["3", "A"], "storey": "FL1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "D1",
                        "dimensions": {"width": 1.0, "height": 2.0},
                        "at_grid": "2",
                    },
                    {
                        "class": "IfcWindow",
                        "tag": "W1",
                        "dimensions": {"width": 1.5, "height": 1.2},
                        "at_grid": "1 + 1.0",
                        "sill_height": 0.9,
                    },
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)
    qto = calculate_qto(resolved)

    wall_qto = next(e for e in qto.elements if e.tag == "WALL-QTO")
    gross_area = 8.0 * 3.0  # 24.0 m2
    opening_area = (1.0 * 2.0) + (1.5 * 1.2)  # 2.0 + 1.8 = 3.8 m2
    net_area = gross_area - opening_area  # 20.2 m2
    expected_vol = net_area * 0.15  # 3.03 m3
    expected_formwork = 2.0 * net_area  # 40.4 m2

    assert pytest.approx(wall_qto.concrete_volume, abs=1e-3) == expected_vol
    assert pytest.approx(wall_qto.formwork_area, abs=1e-3) == expected_formwork


def test_opening_ifc_compilation(tmp_path):
    manifest_data = {
        "project": {"id": "TEST_COMPILER", "name": "Test IFC Compiler Openings"},
        "spatial_structure": {
            "storeys": [{"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 5.0},
        },
        "materials": [
            {"id": "CONCRETE", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "C1"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-IFC",
                "material": "CONCRETE",
                "thickness": 0.15,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["3", "A"], "storey": "FL1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "DOOR-IFC",
                        "dimensions": {"width": 1.0, "height": 2.0},
                        "at_grid": "2",
                    }
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    out_file = tmp_path / "model.ifc"
    compiled_path = compile_to_ifc(resolved, out_file)

    with open(compiled_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "IFCDOOR" in content or "IfcDoor" in content
    assert "IFCOPENINGELEMENT" in content or "IfcOpeningElement" in content
    assert "IFCRELVOIDSELEMENT" in content or "IfcRelVoidsElement" in content
    assert "IFCRELFILLSELEMENT" in content or "IfcRelFillsElement" in content


def test_opening_validation_error():
    # Door missing both offset_distance and at_grid
    door_dict = {
        "class": "IfcDoor",
        "tag": "BAD-DOOR",
        "dimensions": {"width": 0.9, "height": 2.1},
    }
    with pytest.raises(ValidationError):
        IfcDoor.model_validate(door_dict)

    # Window missing both offset_distance and at_grid
    win_dict = {
        "class": "IfcWindow",
        "tag": "BAD-WIN",
        "dimensions": {"width": 1.2, "height": 1.5},
    }
    with pytest.raises(ValidationError):
        IfcWindow.model_validate(win_dict)
