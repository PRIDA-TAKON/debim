"""
Unit & Integration Tests for Auto-Generated MEP Fittings (IfcPipeFitting and IfcJunctionBox)
in debim compiler (src/debim/compiler.py).
"""

from pathlib import Path
import pytest
import ifcopenshell

from debim.compiler import compile_to_ifc
from debim.resolver import resolve_manifest
from debim.schema import ProjectManifest


@pytest.fixture
def mep_manifest_data():
    return {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-FITTINGS", "name": "MEP Auto-Fittings Test Model"},
        "spatial_structure": {
            "storeys": [
                {"id": "STOREY-1", "name": "Level 1", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 5.0, "3": 10.0},
            "axes_y": {"A": 0.0, "B": 5.0, "C": 10.0},
        },
        "materials": [],
        "elements": [
            {
                "class": "IfcSanitaryTerminal",
                "tag": "SAN_BASIN_1",
                "terminal_type": "LAVATORY",
                "placement": {"grid": ["1", "B"], "storey": "STOREY-1", "offset_z": 0.8},
            },
            {
                "class": "IfcSanitaryTerminal",
                "tag": "SAN_WC_1",
                "terminal_type": "WATER_CLOSET",
                "placement": {"grid": ["2", "C"], "storey": "STOREY-1", "offset_z": 0.4},
            },
            {
                "class": "IfcElectricDistributionBoard",
                "tag": "DB_1",
                "board_type": "CONSUMER_UNIT",
                "circuits_count": 8,
                "placement": {"grid": ["1", "C"], "storey": "STOREY-1", "offset_z": 1.8},
            },
            {
                "class": "IfcBuildingElementProxy",
                "tag": "JB_1",
                "ifc_class": "IfcJunctionBox",
                "placement": {"grid": ["2", "C"], "storey": "STOREY-1", "offset_z": 2.8},
            },
            {
                "class": "IfcLightFixture",
                "tag": "LIGHT_1",
                "fixture_type": "DOWNLIGHT",
                "power_watts": 12.0,
                "placement": {"grid": ["3", "C"], "storey": "STOREY-1", "offset_z": 2.8},
            },
            {
                "class": "IfcLightFixture",
                "tag": "LIGHT_2",
                "fixture_type": "DOWNLIGHT",
                "power_watts": 12.0,
                "placement": {"grid": ["2", "B"], "storey": "STOREY-1", "offset_z": 2.8},
            },
        ],
        "mep_systems": [
            # 1. Supply Water Pipe System with 3-way Tee and Reducer
            {
                "id": "SYS_CW",
                "system_type": "DOMESTIC_COLD_WATER",
                "main_pipe": {
                    "tag": "PIPE_CW_MAIN_1",
                    "from": {"grid": ["1", "A"], "storey": "STOREY-1", "offset": [0.0, 0.0, 2.5]},
                    "to": {"grid": ["2", "A"], "storey": "STOREY-1", "offset": [0.0, 0.0, 2.5]},
                    "diameter": 0.025,
                },
                "branches": [
                    {
                        "tag": "BRANCH_CW_1",
                        "branch_from": "PIPE_CW_MAIN_1",
                        "target_fixture": "SAN_BASIN_1",
                        "diameter": 0.015,
                    }
                ],
            },
            # 2. Drainage Pipe System with 45-degree Sanitary Wye
            {
                "id": "SYS_DRAIN",
                "system_type": "SANITARY_DRAINAGE",
                "collector_pipe": {
                    "tag": "PIPE_DRAIN_MAIN",
                    "from": {"grid": ["1", "B"], "storey": "STOREY-1", "offset": [0.0, 0.0, 0.5]},
                    "to": {"grid": ["3", "B"], "storey": "STOREY-1", "offset": [0.0, 0.0, 0.4]},
                    "slope": 0.01,
                    "diameter": 0.100,
                },
                "gather_fixtures": [
                    {
                        "fixture": "SAN_WC_1",
                        "branch_diameter": 0.050,
                    }
                ],
            },
            # 3. Electrical Conduit System with Junction Box
            {
                "id": "SYS_ELEC",
                "system_type": "ELECTRICAL_CONDUIT",
                "home_run": {
                    "from_panel": "DB_1",
                    "to_junction_box": "JB_1",
                    "diameter": 0.020,
                },
                "distribution": {
                    "junction_box": "JB_1",
                    "drops": [
                        {
                            "to_element": "LIGHT_1",
                            "diameter": 0.020,
                        },
                        {
                            "to_element": "LIGHT_2",
                            "diameter": 0.020,
                        },
                    ],
                },
            },
        ],
    }


def test_ifcopenshell_mep_fittings_export(mep_manifest_data, tmp_path):
    """Verify IfcPipeFitting and IfcJunctionBox entities compiled via ifcopenshell backend."""
    manifest = ProjectManifest.model_validate(mep_manifest_data)
    out_ifc = tmp_path / "model_ifcopenshell.ifc"

    compiled_file = compile_to_ifc(manifest, output_path=out_ifc, force_fallback=False)
    assert compiled_file.exists()

    model = ifcopenshell.open(str(compiled_file))

    # Check IfcPipeFitting entities
    pipe_fittings = model.by_type("IfcPipeFitting")
    assert len(pipe_fittings) >= 2, "Expected at least 2 IfcPipeFitting entities (Tee/Wye and Reducer)"

    object_types = {getattr(f, "ObjectType", None) for f in pipe_fittings}
    predefined_types = {getattr(f, "PredefinedType", None) for f in pipe_fittings}

    assert "TEE" in object_types or "SANITARY_WYE_45" in object_types
    assert "CONCENTRIC_REDUCER" in object_types
    assert "JUNCTION" in predefined_types or "TRANSITION" in predefined_types

    # Check IfcJunctionBox entities
    jboxes = model.by_type("IfcJunctionBox")
    assert len(jboxes) >= 1, "Expected at least 1 IfcJunctionBox entity"
    assert any(getattr(j, "ObjectType", None) == "JUNCTION_BOX" for j in jboxes)


def test_step_serializer_mep_fittings_export(mep_manifest_data, tmp_path):
    """Verify IfcPipeFitting and IfcJunctionBox STEP physical file export via StepSerializer fallback."""
    manifest = ProjectManifest.model_validate(mep_manifest_data)
    out_ifc = tmp_path / "model_fallback.ifc"

    compiled_file = compile_to_ifc(manifest, output_path=out_ifc, force_fallback=True)
    assert compiled_file.exists()

    content = compiled_file.read_text(encoding="utf-8")

    # Verify IFC STEP text lines for IfcPipeFitting and IfcJunctionBox
    assert "IFCPIPEFITTING(" in content
    assert "IFCJUNCTIONBOX(" in content
    assert "CONCENTRIC_REDUCER" in content
    assert "JUNCTION_BOX" in content
    assert ".JUNCTION." in content or ".TRANSITION." in content
