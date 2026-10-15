"""
Unit tests for host-wall auto-punching and multi-storey window/door placement.
"""

import pytest
from debim.schema import ProjectManifest, IfcWall, IfcWindow, IfcDoor
from debim.resolver import resolve_manifest
from debim.compiler import compile_to_ifc


def test_host_wall_autopunch_single_storey():
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "p1", "name": "Test Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "STOREY-1", "name": "1st Floor", "elevation": 0.0, "height": 3.5},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 6.0},
            "axes_y": {"A": 0.0, "B": 6.0},
        },
        "materials": [
            {"id": "CONC", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "M-C"},
            {"id": "GLASS", "name": "Glass", "category": "GLASS", "unit_cost_ref": "M-G"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-1",
                "material": "CONC",
                "thickness": 0.20,
                "height": 3.5,
                "placement": {
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                    "storey": "STOREY-1",
                },
                "children": [],
            },
            {
                "class": "IfcWindow",
                "tag": "W1",
                "material": "GLASS",
                "dimensions": {"width": 1.20, "height": 1.50},
                "offset_distance": 2.0,
                "sill_height": 0.90,
                "host_wall": "WALL-1",
            },
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    assert len(resolved.walls) == 1
    r_wall = resolved.walls[0]
    assert r_wall.tag == "WALL-1"
    assert len(r_wall.children) == 1

    r_win = r_wall.children[0]
    assert r_win.tag == "W1"
    assert r_win.position == (2.0, 0.0, 0.90)

    # Test compiler output contains IfcOpeningElement for W1
    ifc_path = compile_to_ifc(manifest, "dist/test_host_single.ifc", force_fallback=True)
    content = ifc_path.read_text(encoding="utf-8")
    assert "W1_Opening" in content
    assert "IFCRELVOIDSELEMENT" in content
    assert "IFCRELFILLSELEMENT" in content


def test_multi_storey_window_span_storeys(tmp_path):
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "p1", "name": "Multi-storey Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "STOREY-1", "name": "1st Floor", "elevation": 0.0, "height": 3.5},
                {"id": "STOREY-2", "name": "2nd Floor", "elevation": 3.5, "height": 3.5},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 6.0},
            "axes_y": {"A": 0.0, "B": 6.0},
        },
        "materials": [
            {"id": "CONC", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "M-C"},
            {"id": "GLASS", "name": "Glass", "category": "GLASS", "unit_cost_ref": "M-G"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "STAIR-WALL",
                "material": "CONC",
                "thickness": 0.20,
                "height": 7.0,
                "placement": {
                    "from_grid": ["1", "A"],
                    "to_grid": ["1", "B"],
                    "storey": "STOREY-1",
                },
                "children": [],
            },
            {
                "class": "IfcWindow",
                "tag": "W5",
                "material": "GLASS",
                "dimensions": {"width": 1.40, "height": 2.90},
                "offset_distance": 1.5,
                "sill_height": 0.80,
                "host_wall": "STAIR-WALL",
                "span_storeys": ["STOREY-1", "STOREY-2"],
            },
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    assert len(resolved.walls) == 1
    r_wall = resolved.walls[0]
    assert r_wall.tag == "STAIR-WALL"
    assert len(r_wall.children) == 1

    r_win = r_wall.children[0]
    assert r_win.tag == "W5"
    assert r_win.position == (0.0, 1.5, 0.80)
    assert r_win.height == 2.90

    # Step Serializer compilation test
    out_step = tmp_path / "multi_storey.ifc"
    compile_to_ifc(manifest, out_step, force_fallback=True)
    content_step = out_step.read_text(encoding="utf-8")
    assert "W5_Opening" in content_step
    assert "IFCRELVOIDSELEMENT" in content_step

    # IfcOpenShell compilation test
    out_ifc = tmp_path / "multi_storey_ifc.ifc"
    compile_to_ifc(manifest, out_ifc, force_fallback=False)
    content_ifc = out_ifc.read_text(encoding="utf-8")
    assert "W5_Opening" in content_ifc


def test_invalid_host_wall_reference():
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "p1", "name": "Invalid Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "STOREY-1", "name": "1st Floor", "elevation": 0.0, "height": 3.5},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 6.0},
            "axes_y": {"A": 0.0, "B": 6.0},
        },
        "materials": [
            {"id": "GLASS", "name": "Glass", "category": "GLASS", "unit_cost_ref": "M-G"},
        ],
        "elements": [
            {
                "class": "IfcWindow",
                "tag": "W1",
                "material": "GLASS",
                "dimensions": {"width": 1.0, "height": 1.0},
                "offset_distance": 1.0,
                "host_wall": "NONEXISTENT-WALL",
            },
        ],
    }

    with pytest.raises(ValueError, match="unknown host_wall 'NONEXISTENT-WALL'"):
        ProjectManifest.model_validate(manifest_data)


def test_invalid_span_storeys_reference():
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "p1", "name": "Invalid Storey Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "STOREY-1", "name": "1st Floor", "elevation": 0.0, "height": 3.5},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 6.0},
            "axes_y": {"A": 0.0, "B": 6.0},
        },
        "materials": [
            {"id": "CONC", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "M-C"},
            {"id": "GLASS", "name": "Glass", "category": "GLASS", "unit_cost_ref": "M-G"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-1",
                "material": "CONC",
                "thickness": 0.20,
                "height": 3.5,
                "placement": {
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                    "storey": "STOREY-1",
                },
            },
            {
                "class": "IfcWindow",
                "tag": "W1",
                "material": "GLASS",
                "dimensions": {"width": 1.0, "height": 1.0},
                "offset_distance": 1.0,
                "host_wall": "WALL-1",
                "span_storeys": ["STOREY-1", "NONEXISTENT-STOREY"],
            },
        ],
    }

    with pytest.raises(ValueError, match="span_storeys references unknown storey 'NONEXISTENT-STOREY'"):
        ProjectManifest.model_validate(manifest_data)
