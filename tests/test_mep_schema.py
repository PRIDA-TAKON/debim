"""
Unit tests for Declarative MEP Network Topology and Branching models in debim schema.
Verifies Pydantic validation for supply branching, drainage converging, electrical conduits,
and backward compatibility with standalone IfcPipeSegment.
"""

import pytest
from debim.schema import (
    IfcPipeSegment,
    MepNetworkSystem,
    ProjectManifest,
)


def test_supply_branching_pydantic_validation():
    """Verify validation of 1-to-N supply branching manifest."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-SUPPLY", "name": "MEP Supply Branching Project"},
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
                "material": "PPR",
                "placement": {"grid": ["1", "B"], "storey": "L2"},
            },
            {
                "class": "IfcSanitaryTerminal",
                "tag": "SAN_WC_01",
                "terminal_type": "WATER_CLOSET",
                "material": "PPR",
                "placement": {"grid": ["1", "C"], "storey": "L2"},
            },
        ],
        "mep_systems": [
            {
                "id": "SYS_CW_BATH_L2",
                "system_type": "DOMESTIC_COLD_WATER",
                "material": "PPR",
                "main_pipe": {
                    "tag": "PIPE_CW_MAIN",
                    "from": {"grid": ["1", "B"], "offset": [0.2, 0.0, 2.6]},
                    "to": {"grid": ["1", "D"], "offset": [0.2, 0.0, 2.6]},
                    "diameter": 0.025,
                },
                "branches": [
                    {
                        "tag": "BRANCH_BASIN",
                        "branch_from": "PIPE_CW_MAIN",
                        "target_fixture": "SAN_BASIN_01",
                        "target_port": "CW_INLET",
                        "diameter": 0.015,
                        "auto_reducer": True,
                    },
                    {
                        "tag": "BRANCH_WC",
                        "branch_from": "PIPE_CW_MAIN",
                        "target_fixture": "SAN_WC_01",
                        "target_port": "CW_INLET",
                        "diameter": 0.015,
                        "auto_reducer": True,
                    },
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    assert len(manifest.mep_systems) == 1

    sys = manifest.mep_systems[0]
    assert isinstance(sys, MepNetworkSystem)
    assert sys.id == "SYS_CW_BATH_L2"
    assert sys.main_pipe is not None
    assert sys.main_pipe.tag == "PIPE_CW_MAIN"
    assert sys.main_pipe.diameter == 0.025
    assert len(sys.branches) == 2

    b1 = sys.branches[0]
    assert b1.tag == "BRANCH_BASIN"
    assert b1.branch_from == "PIPE_CW_MAIN"
    assert b1.target_fixture == "SAN_BASIN_01"
    assert b1.target_port == "CW_INLET"
    assert b1.diameter == 0.015
    assert b1.auto_reducer is True


def test_drainage_converging_pydantic_validation():
    """Verify validation of N-to-1 converging drainage/soil manifest."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-DRAIN", "name": "MEP Drainage Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "L2", "name": "Level 2", "elevation": 3.5, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0},
            "axes_y": {"A": 0.0, "B": 4.0},
        },
        "materials": [
            {"id": "PVC_CLASS_8.5", "name": "PVC Pipe", "category": "plastic", "unit_cost_ref": "MAT-PVC"}
        ],
        "elements": [],
        "mep_systems": [
            {
                "id": "SYS_SOIL_WASTE_L2",
                "system_type": "SANITARY_DRAINAGE",
                "material": "PVC_CLASS_8.5",
                "collector_pipe": {
                    "tag": "PIPE_SOIL_MAIN",
                    "discharge_to": "RISER_STACK_01",
                    "slope": 0.01,
                    "diameter": 0.100,
                },
                "gather_fixtures": [
                    {
                        "fixture": "SAN_WC_01",
                        "branch_diameter": 0.100,
                        "fitting_type": "SANITARY_WYE_45",
                    },
                    {
                        "fixture": "SAN_BASIN_01",
                        "branch_diameter": 0.050,
                        "slope": 0.01,
                        "fitting_type": "SANITARY_TEE_REDUCER",
                    },
                ],
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    assert len(manifest.mep_systems) == 1

    sys = manifest.mep_systems[0]
    assert sys.id == "SYS_SOIL_WASTE_L2"
    assert sys.collector_pipe is not None
    assert sys.collector_pipe.tag == "PIPE_SOIL_MAIN"
    assert sys.collector_pipe.discharge_to == "RISER_STACK_01"
    assert sys.collector_pipe.slope == 0.01
    assert sys.collector_pipe.diameter == 0.100

    assert len(sys.gather_fixtures) == 2
    g1 = sys.gather_fixtures[0]
    assert g1.fixture == "SAN_WC_01"
    assert g1.target_fixture == "SAN_WC_01"  # Synced via model validator
    assert g1.branch_diameter == 0.100
    assert g1.fitting_type == "SANITARY_WYE_45"


def test_electrical_conduit_distribution_validation():
    """Verify validation of electrical conduit distribution network manifest."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-ELEC", "name": "MEP Electrical Conduit Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "L2", "name": "Level 2", "elevation": 3.5, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0},
            "axes_y": {"A": 0.0, "B": 4.0},
        },
        "materials": [
            {"id": "WHITE_UPVC", "name": "uPVC Conduit", "category": "plastic", "unit_cost_ref": "MAT-UPVC"}
        ],
        "elements": [],
        "mep_systems": [
            {
                "id": "SYS_CONDUIT_LIGHTING_L2",
                "system_type": "ELECTRICAL_CONDUIT",
                "material": "WHITE_UPVC",
                "home_run": {
                    "from_panel": "DB_L2",
                    "to_junction_box": "JB_ROOM_01",
                    "diameter": 0.020,
                },
                "distribution": {
                    "junction_box": "JB_ROOM_01",
                    "drops": [
                        {"to_element": "SW_2GANG_01", "diameter": 0.020},
                        {"to_element": "LIGHT_DOWNLIGHT_01", "diameter": 0.020},
                        {"to_element": "LIGHT_DOWNLIGHT_02", "diameter": 0.020},
                    ],
                },
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    assert len(manifest.mep_systems) == 1

    sys = manifest.mep_systems[0]
    assert sys.id == "SYS_CONDUIT_LIGHTING_L2"
    assert sys.home_run is not None
    assert sys.home_run.from_panel == "DB_L2"
    assert sys.home_run.to_junction_box == "JB_ROOM_01"
    assert sys.home_run.diameter == 0.020

    assert sys.distribution is not None
    assert sys.distribution.junction_box == "JB_ROOM_01"
    assert len(sys.distribution.drops) == 3
    assert sys.distribution.drops[0].to_element == "SW_2GANG_01"


def test_backward_compatibility_ifc_pipe_segment():
    """Verify that existing standalone IfcPipeSegment continues to work without error."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-STANDALONE", "name": "Standalone Pipe Test"},
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0},
            "axes_y": {"A": 0.0, "B": 4.0},
        },
        "materials": [
            {"id": "PPR", "name": "PPR Pipe", "category": "plastic", "unit_cost_ref": "MAT-PPR"}
        ],
        "elements": [
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-CW-STANDALONE",
                "system_type": "COLD_WATER",
                "material": "PPR",
                "nominal_diameter": 0.020,
                "placement": {
                    "storey": "L1",
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                },
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    assert len(manifest.elements) == 1
    elem = manifest.elements[0]
    assert isinstance(elem, IfcPipeSegment)
    assert elem.tag == "PIPE-CW-STANDALONE"
    assert elem.nominal_diameter == 0.020


def test_alias_mep_network_systems():
    """Verify that mep_network_systems field alias is automatically mapped to mep_systems."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-ALIAS", "name": "MEP Alias Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0},
            "axes_y": {"A": 0.0, "B": 4.0},
        },
        "materials": [],
        "elements": [],
        "mep_network_systems": [
            {
                "id": "SYS_CW_ALIAS",
                "system_type": "DOMESTIC_COLD_WATER",
                "main_pipe": {
                    "tag": "MAIN_01",
                    "from": {"grid": ["1", "A"]},
                    "to": {"grid": ["2", "A"]},
                    "diameter": 0.025,
                },
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_data)
    assert len(manifest.mep_systems) == 1
    assert manifest.mep_systems[0].id == "SYS_CW_ALIAS"
