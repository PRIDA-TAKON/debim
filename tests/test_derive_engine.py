"""
Unit test suite for debim derive auto-framing engine.
Verifies automated derivation of Walls, Doors, Windows, Columns, Beams, Slabs, and Footings.
"""

import pytest
from debim.derive import derive_project_from_spaces
from debim.schema import IfcSpace, SpaceTouchingSpec, IfcWall, IfcDoor, IfcWindow, IfcColumn, IfcBeam, IfcSlab, IfcFooting


def test_derive_project_from_spaces_elements():
    floorplan_data = {
        "project": {
            "id": "PRJ-DERIVE-TEST",
            "name": "Derive Test House",
        },
        "spaces": [
            {
                "tag": "ROOM_A",
                "name": "Room A",
                "dimensions": [4.0, 4.0],
                "origin": [0.0, 0.0],
            },
            {
                "tag": "ROOM_B",
                "name": "Room B",
                "dimensions": [4.0, 4.0],
                "touching": {"target": "ROOM_A", "side": "EAST", "align": "BOTTOM"},
                "must_connect": ["ROOM_A"],
            },
        ],
    }

    manifest = derive_project_from_spaces(floorplan_data)

    # 1. Verify Grid axes creation
    assert "1" in manifest.grids.axes_x
    assert "2" in manifest.grids.axes_x
    assert "3" in manifest.grids.axes_x
    assert "A" in manifest.grids.axes_y
    assert "B" in manifest.grids.axes_y

    # 2. Verify Derived Element types
    walls = [e for e in manifest.elements if isinstance(e, IfcWall)]
    columns = [e for e in manifest.elements if isinstance(e, IfcColumn)]
    beams = [e for e in manifest.elements if isinstance(e, IfcBeam)]
    slabs = [e for e in manifest.elements if isinstance(e, IfcSlab)]
    footings = [e for e in manifest.elements if isinstance(e, IfcFooting)]

    assert len(walls) >= 7  # 6 exterior atomic walls + 1 shared internal wall
    assert len(columns) == 6  # 6 unique corner grid intersections
    assert len(footings) == 6
    assert len(slabs) == 2  # 1 per space
    assert len(beams) >= 14  # Ground tie beams + top ring beams

    # 3. Verify Doors and Windows in Wall children
    doors_count = 0
    windows_count = 0
    for w in walls:
        for child in w.children:
            if isinstance(child, IfcDoor):
                doors_count += 1
            elif isinstance(child, IfcWindow):
                windows_count += 1

    assert doors_count >= 1, "Expected at least 1 door generated on must_connect shared boundary"
    assert windows_count >= 1, "Expected exterior windows on exterior walls"


def test_derive_project_roundtrip_resolution_and_validation():
    from debim.resolver import resolve_manifest
    from debim.compliance import check_topological_continuity, detect_mep_structural_clashes

    floorplan = {
        "spaces": [
            {"tag": "BEDROOM", "dimensions": [4.0, 4.0], "origin": [0.0, 0.0]},
            {"tag": "BATHROOM", "dimensions": [2.0, 2.0], "touching": {"target": "BEDROOM", "side": "NORTH", "align": "LEFT"}, "must_connect": ["BEDROOM"]},
        ]
    }

    manifest = derive_project_from_spaces(floorplan)
    resolved = resolve_manifest(manifest)

    # Topological continuity check should pass cleanly
    topo_warnings = check_topological_continuity(resolved)
    assert len(topo_warnings) == 0

    mep_clashes = detect_mep_structural_clashes(resolved)
    assert len(mep_clashes) == 0
