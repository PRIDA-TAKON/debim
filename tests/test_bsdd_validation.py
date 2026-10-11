"""
Unit tests for buildingSMART bSDD Property Set validation engine and CLI integration.
"""

from pathlib import Path
import tempfile
import yaml
from typer.testing import CliRunner

from debim.bsdd import (
    PsetValidationStatus,
    STANDARD_IFC4_PSETS,
    coerce_pset_properties,
    get_property_expected_type,
    validate_element_psets,
    validate_manifest_psets,
)
from debim.cli import app
from debim.compiler import compile_to_ifc
from debim.schema import IfcWall, ProjectManifest

runner = CliRunner()


def test_valid_standard_pset():
    wall = IfcWall.model_validate(
        {
            "class": "IfcWall",
            "tag": "W1",
            "material": "CONC",
            "thickness": 0.2,
            "height": 3.0,
            "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "ST1"},
            "properties": {
                "Pset_WallCommon": {
                    "LoadBearing": True,
                    "ThermalTransmittance": 0.25,
                    "Reference": "WALL-01",
                }
            },
        }
    )
    results = validate_element_psets(wall)
    assert len(results) == 3
    for r in results:
        assert r.status == PsetValidationStatus.VALID


def test_invalid_data_types_in_pset():
    wall = IfcWall.model_validate(
        {
            "class": "IfcWall",
            "tag": "W2",
            "material": "CONC",
            "thickness": 0.2,
            "height": 3.0,
            "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "ST1"},
            "properties": {
                "Pset_WallCommon": {
                    "LoadBearing": "not_a_bool",
                    "ThermalTransmittance": "invalid_float",
                }
            },
        }
    )
    results = validate_element_psets(wall)
    assert len(results) == 2
    for r in results:
        assert r.status == PsetValidationStatus.ERROR


def test_non_standard_properties_and_psets():
    wall = IfcWall.model_validate(
        {
            "class": "IfcWall",
            "tag": "W3",
            "material": "CONC",
            "thickness": 0.2,
            "height": 3.0,
            "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "ST1"},
            "properties": {
                "Pset_WallCommon": {
                    "UnknownProperty": 123,
                },
                "CustomPset": {
                    "MyAttribute": "CustomValue",
                },
            },
        }
    )
    results = validate_element_psets(wall)
    assert len(results) == 2
    for r in results:
        assert r.status == PsetValidationStatus.NON_STANDARD


def test_cli_validate_bsdd_flag():
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "P1", "name": "bSDD Test Project"},
        "spatial_structure": {"storeys": [{"id": "ST1", "name": "L1", "elevation": 0.0, "height": 3.0}]},
        "grids": {"axes_x": {"1": 0.0, "2": 5.0}, "axes_y": {"A": 0.0, "B": 5.0}},
        "materials": [{"id": "CONC", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "C1"}],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "W101",
                "material": "CONC",
                "thickness": 0.2,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "ST1"},
                "properties": {
                    "Pset_WallCommon": {
                        "LoadBearing": True,
                        "ThermalTransmittance": 0.25,
                    }
                },
            }
        ],
    }

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(manifest_data, f)
        tmp_yaml = Path(f.name)

    res = runner.invoke(app, ["validate", "-m", str(tmp_yaml), "--bsdd"], env={"COLUMNS": "200"})
    assert res.exit_code == 0
    assert "buildingSMART bSDD Property Set Validation" in res.output
    assert "Pset_WallCommon" in res.output


def test_coerce_pset_properties_and_compiler():
    props = {"LoadBearing": "true", "ThermalTransmittance": "0.35"}
    coerced = coerce_pset_properties("Pset_WallCommon", props)
    assert coerced["LoadBearing"] is True
    assert isinstance(coerced["ThermalTransmittance"], float)
    assert coerced["ThermalTransmittance"] == 0.35
