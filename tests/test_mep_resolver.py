"""
Unit tests for Topological MEP Router and Automatic Orthogonal Branch Projection
in debim resolver (src/debim/resolver.py).

Verifies perpendicular projection calculation, coordinate snapping, zero disconnection gap,
and full SpatialResolver integration for supply branching, drainage, and conduit distribution.
"""

import math
import pytest
from debim.schema import (
    IfcSanitaryTerminal,
    MepNetworkSystem,
    ProjectManifest,
)
from debim.resolver import (
    SpatialResolver,
    _project_point_onto_line_segment,
    resolve_mep_network,
    resolve_manifest,
)


def test_project_point_onto_line_segment_math():
    """Verify perpendicular projection parameter t and clamping math in 3D."""
    # Main line segment along Y axis: (0.2, 0.0, 2.6) to (0.2, 4.0, 2.6)
    a = (0.2, 0.0, 2.6)
    b = (0.2, 4.0, 2.6)

    # 1. Point at (1.0, 1.5, 4.0) -> projected y should be 1.5, x=0.2, z=2.6
    p1 = (1.0, 1.5, 4.0)
    j1 = _project_point_onto_line_segment(p1, a, b)
    assert j1 == (0.2, 1.5, 2.6)

    # 2. Point before segment start: y = -1.0 -> clamped to start point a
    p2 = (0.5, -1.0, 2.6)
    j2 = _project_point_onto_line_segment(p2, a, b)
    assert j2 == (0.2, 0.0, 2.6)

    # 3. Point after segment end: y = 5.0 -> clamped to end point b
    p3 = (0.5, 5.0, 2.6)
    j3 = _project_point_onto_line_segment(p3, a, b)
    assert j3 == (0.2, 4.0, 2.6)

    # 4. Sloped line in 3D: (0, 0, 0) to (10, 0, 10)
    a_slope = (0.0, 0.0, 0.0)
    b_slope = (10.0, 0.0, 10.0)
    p_slope = (5.0, 2.0, 0.0)  # Midpoint in X, offset in Y and Z
    j_slope = _project_point_onto_line_segment(p_slope, a_slope, b_slope)
    assert j_slope == (2.5, 0.0, 2.5)


def test_supply_branching_coordinate_snapping():
    """Verify that branch start coordinates strictly match projected point on main pipe."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-SNAP", "name": "MEP Coordinate Snapping Test"},
        "spatial_structure": {
            "storeys": [
                {"id": "L2", "name": "Level 2", "elevation": 3.5, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0},
            "axes_y": {"B": 0.0, "C": 2.0, "D": 4.0},
        },
        "materials": [
            {"id": "PPR", "name": "PPR Pipe", "category": "plastic", "unit_cost_ref": "MAT-PPR"}
        ],
        "elements": [
            {
                "class": "IfcSanitaryTerminal",
                "tag": "SAN_BASIN_01",
                "terminal_type": "LAVATORY",
                "placement": {"grid": ["1", "C"], "storey": "L2", "offset_x": 1.0, "offset_y": 0.5, "offset_z": 0.8},
            },
            {
                "class": "IfcSanitaryTerminal",
                "tag": "SAN_WC_01",
                "terminal_type": "WATER_CLOSET",
                "placement": {"grid": ["1", "D"], "storey": "L2", "offset_x": 1.0, "offset_y": -0.5, "offset_z": 0.4},
            },
        ],
        "mep_systems": [
            {
                "id": "SYS_CW_BATH_L2",
                "system_type": "DOMESTIC_COLD_WATER",
                "material": "PPR",
                "main_pipe": {
                    "tag": "PIPE_CW_MAIN",
                    "from": {"grid": ["1", "B"], "storey": "L2", "offset": [0.2, 0.0, 2.6]},
                    "to": {"grid": ["1", "D"], "storey": "L2", "offset": [0.2, 0.0, 2.6]},
                    "diameter": 0.025,
                },
                "branches": [
                    {
                        "tag": "BRANCH_BASIN",
                        "branch_from": "PIPE_CW_MAIN",
                        "target_fixture": "SAN_BASIN_01",
                        "diameter": 0.015,
                        "auto_reducer": True,
                    },
                    {
                        "tag": "BRANCH_WC",
                        "branch_from": "PIPE_CW_MAIN",
                        "target_fixture": "SAN_WC_01",
                        "diameter": 0.015,
                        "auto_reducer": True,
                    },
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolver = SpatialResolver(manifest)
    resolved_segs = resolver.resolve_mep_network(manifest.mep_systems[0])

    # 1 Main pipe + 2 branches = 3 resolved segments
    assert len(resolved_segs) == 3

    r_main = resolved_segs[0]
    r_b1 = resolved_segs[1]
    r_b2 = resolved_segs[2]

    assert r_main.tag == "PIPE_CW_MAIN"
    assert r_main.start_point == (0.2, 0.0, 6.1)  # 3.5 storey + 2.6 offset
    assert r_main.end_point == (0.2, 4.0, 6.1)

    # Check BASIN fixture position: grid ["1", "C"] is (0.0, 2.0, 3.5), offsets (1.0, 0.5, 0.8) -> (1.0, 2.5, 4.3)
    # Projected onto main pipe (0.2, 0.0, 6.1) to (0.2, 4.0, 6.1):
    # Projected y = 2.5 -> Junction = (0.2, 2.5, 6.1)
    assert r_b1.tag == "BRANCH_BASIN"
    assert r_b1.start_point == (0.2, 2.5, 6.1)  # Strictly matches projected junction on main pipe
    assert r_b1.end_point == (1.0, 2.5, 4.3)    # Matches fixture position

    # Check orthogonal waypoints for BRANCH_BASIN:
    # Waypoints: (0.2, 2.5, 6.1) -> (1.0, 2.5, 6.1) -> (1.0, 2.5, 4.3)
    assert r_b1.waypoints[0] == (0.2, 2.5, 6.1)
    assert r_b1.waypoints[-1] == (1.0, 2.5, 4.3)
    assert len(r_b1.waypoints) >= 2

    # Check WC fixture position: grid ["1", "D"] is (0.0, 4.0, 3.5), offsets (1.0, -0.5, 0.4) -> (1.0, 3.5, 3.9)
    # Projected onto main pipe -> Junction = (0.2, 3.5, 6.1)
    assert r_b2.tag == "BRANCH_WC"
    assert r_b2.start_point == (0.2, 3.5, 6.1)  # Strictly matches projected junction on main pipe
    assert r_b2.end_point == (1.0, 3.5, 3.9)


def test_drainage_converging_mep_resolver():
    """Verify N-to-1 converging drainage system with slope and coordinate snapping."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-DRAIN-RES", "name": "MEP Drainage Resolver Test"},
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0},
            "axes_y": {"A": 0.0, "B": 2.0, "C": 4.0},
        },
        "materials": [],
        "elements": [
            {
                "class": "IfcSanitaryTerminal",
                "tag": "WC_01",
                "terminal_type": "WATER_CLOSET",
                "placement": {"grid": ["1", "A"], "storey": "L1", "offset_x": 1.5, "offset_y": 0.0, "offset_z": 0.0},
            },
            {
                "class": "IfcSanitaryTerminal",
                "tag": "BASIN_01",
                "terminal_type": "LAVATORY",
                "placement": {"grid": ["1", "B"], "storey": "L1", "offset_x": 1.5, "offset_y": 0.0, "offset_z": 0.0},
            },
        ],
        "mep_systems": [
            {
                "id": "SYS_DRAIN_L1",
                "system_type": "SANITARY_DRAINAGE",
                "collector_pipe": {
                    "tag": "MAIN_DRAIN",
                    "from": {"grid": ["1", "A"], "offset": [0.0, 0.0, -0.20]},
                    "to": {"grid": ["1", "C"], "offset": [0.0, 0.0, -0.24]},
                    "slope": 0.01,
                    "diameter": 0.100,
                },
                "gather_fixtures": [
                    {"fixture": "WC_01", "branch_diameter": 0.100, "slope": 0.02},
                    {"fixture": "BASIN_01", "branch_diameter": 0.050, "slope": 0.01},
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolver = SpatialResolver(manifest)
    segs = resolver.resolve_mep_network(manifest.mep_systems[0])

    assert len(segs) == 3
    r_coll = segs[0]
    r_wc = segs[1]
    r_basin = segs[2]

    # Main collector goes along Y axis at X=0.0
    assert r_coll.start_point == (0.0, 0.0, -0.20)
    assert r_coll.end_point == (0.0, 4.0, -0.24)

    # WC_01 fixture is at (1.5, 0.0, 0.0) -> projected y=0.0 -> Junction = (0.0, 0.0, -0.20)
    assert r_wc.start_point == (0.0, 0.0, -0.20)
    assert r_wc.end_point == (1.5, 0.0, 0.0)

    # BASIN_01 fixture is at (1.5, 2.0, 0.0) -> projected onto sloped main pipe -> Junction approx (0.0, 2.0, -0.22)
    assert r_basin.start_point[0] == 0.0
    assert r_basin.start_point[1] == pytest.approx(2.0, abs=1e-2)
    assert r_basin.start_point[2] == pytest.approx(-0.22, abs=1e-2)
    assert r_basin.end_point == (1.5, 2.0, 0.0)


def test_electrical_conduit_distribution_mep_resolver():
    """Verify electrical conduit home run and distribution drops resolution."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-ELEC-RES", "name": "MEP Electrical Resolver Test"},
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 5.0},
            "axes_y": {"A": 0.0, "B": 5.0},
        },
        "materials": [],
        "elements": [
            {
                "class": "IfcElectricDistributionBoard",
                "tag": "DB_L1",
                "board_type": "CONSUMER_UNIT",
                "circuits_count": 12,
                "placement": {"grid": ["1", "A"], "storey": "L1", "offset_z": 1.8},
            },
            {
                "class": "IfcBuildingElementProxy",
                "tag": "JB_01",
                "ifc_class": "IfcJunctionBox",
                "placement": {"grid": ["1", "B"], "storey": "L1", "offset_z": 2.8},
            },
            {
                "class": "IfcLightFixture",
                "tag": "LIGHT_01",
                "fixture_type": "DOWNLIGHT",
                "power_watts": 12.0,
                "placement": {"grid": ["2", "B"], "storey": "L1", "offset_z": 2.8},
            },
        ],
        "mep_systems": [
            {
                "id": "SYS_ELEC_L1",
                "system_type": "ELECTRICAL_CONDUIT",
                "home_run": {
                    "from_panel": "DB_L1",
                    "to_junction_box": "JB_01",
                    "diameter": 0.020,
                },
                "distribution": {
                    "junction_box": "JB_01",
                    "drops": [
                        {"to_element": "LIGHT_01", "diameter": 0.020}
                    ],
                },
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolver = SpatialResolver(manifest)
    segs = resolver.resolve_mep_network(manifest.mep_systems[0])

    assert len(segs) == 2
    r_hr = segs[0]
    r_drop = segs[1]

    # Home run connects DB_L1 (0.0, 0.0, 1.8) to JB_01 (0.0, 5.0, 2.8)
    assert r_hr.start_point == (0.0, 0.0, 1.8)
    assert r_hr.end_point == (0.0, 5.0, 2.8)

    # Distribution drop connects JB_01 (0.0, 5.0, 2.8) to LIGHT_01 (5.0, 5.0, 2.8)
    assert r_drop.start_point == (0.0, 5.0, 2.8)
    assert r_drop.end_point == (5.0, 5.0, 2.8)


def test_full_manifest_resolve_manifest_with_mep_systems():
    """Verify that resolve_manifest auto-populates resolved_manifest.pipes and elements from mep_systems."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-FULL-MEP", "name": "Full Manifest MEP Test"},
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0},
            "axes_y": {"A": 0.0, "B": 3.0},
        },
        "materials": [],
        "elements": [
            {
                "class": "IfcSanitaryTerminal",
                "tag": "SINK_01",
                "terminal_type": "KITCHEN_SINK",
                "placement": {"grid": ["1", "B"], "storey": "L1", "offset_x": 1.0},
            }
        ],
        "mep_systems": [
            {
                "id": "SYS_SINK_CW",
                "system_type": "DOMESTIC_COLD_WATER",
                "main_pipe": {
                    "tag": "MAIN_CW",
                    "from": {"grid": ["1", "A"], "offset": [0.0, 0.0, 2.0]},
                    "to": {"grid": ["1", "B"], "offset": [0.0, 0.0, 2.0]},
                    "diameter": 0.025,
                },
                "branches": [
                    {
                        "tag": "BRANCH_SINK",
                        "branch_from": "MAIN_CW",
                        "target_fixture": "SINK_01",
                        "diameter": 0.015,
                    }
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    # Pipes should contain MAIN_CW and BRANCH_SINK
    assert len(resolved.pipes) >= 2
    pipe_tags = {p.tag for p in resolved.pipes}
    assert "MAIN_CW" in pipe_tags
    assert "BRANCH_SINK" in pipe_tags

    branch_pipe = next(p for p in resolved.pipes if p.tag == "BRANCH_SINK")
    main_pipe = next(p for p in resolved.pipes if p.tag == "MAIN_CW")

    # Main pipe runs from (0, 0, 2) to (0, 3, 2)
    # SINK_01 is at (1.0, 3.0, 0.0) -> projected y=3.0 -> Junction = (0, 3.0, 2.0)
    assert branch_pipe.start_point == (0.0, 3.0, 2.0)
    assert branch_pipe.start_point == main_pipe.end_point
