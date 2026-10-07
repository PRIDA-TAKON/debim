"""
Unit tests for buildingSMART bSDD (Building Data Dictionary) Pset validation engine and CLI integration.
"""

import pytest
from typer.testing import CliRunner
import yaml

from debim.bsdd import (
    BSDD_STANDARD_PSETS,
    PropertyValidationStatus,
    PsetValidationResult,
    validate_element_psets,
    validate_manifest_psets,
    validate_pset,
)
from debim.cli import app
from debim.schema import (
    IfcBuildingElementProxy,
    ProxyPlacement,
    ProjectManifest,
    ProjectInfo,
    SpatialStructure,
    Storey,
    Grids,
)

runner = CliRunner()


def test_standard_psets_dictionary():
    assert "Pset_WallCommon" in BSDD_STANDARD_PSETS
    assert "Pset_DoorCommon" in BSDD_STANDARD_PSETS
    assert "Pset_WindowCommon" in BSDD_STANDARD_PSETS
    assert "Pset_ChillerTypeCommon" in BSDD_STANDARD_PSETS

    wall_schema = BSDD_STANDARD_PSETS["Pset_WallCommon"]
    assert wall_schema["LoadBearing"]["type"] == "Boolean"
    assert wall_schema["ThermalTransmittance"]["type"] == "Float"


def test_valid_standard_pset():
    data = {
        "Reference": "WALL-101",
        "IsExternal": True,
        "LoadBearing": True,
        "ThermalTransmittance": 0.25,
    }
    results = validate_pset("Pset_WallCommon", data, element_tag="W1")

    assert len(results) == 4
    for r in results:
        assert r.status == PropertyValidationStatus.VALID


def test_invalid_data_type_detection():
    data = {
        "LoadBearing": "YES",  # String instead of Boolean
        "ThermalTransmittance": "high",  # String instead of Float
    }
    results = validate_pset("Pset_WallCommon", data, element_tag="W2")

    assert len(results) == 2
    for r in results:
        assert r.status == PropertyValidationStatus.TYPE_MISMATCH
        assert r.expected_type in ("Boolean", "Float")


def test_enum_constraint_validation():
    data = {
        "OperationType": "SINGLE_SWING_LEFT",
    }
    results_valid = validate_pset("Pset_DoorCommon", data, element_tag="D1")
    assert results_valid[0].status == PropertyValidationStatus.VALID

    data_invalid = {
        "OperationType": "MAGIC_SLIDE_UNKNOWN",
    }
    results_invalid = validate_pset("Pset_DoorCommon", data_invalid, element_tag="D2")
    assert results_invalid[0].status == PropertyValidationStatus.VALUE_CONSTRAINT_VIOLATION


def test_non_standard_properties_and_custom_psets():
    # Standard Pset with non-standard property
    data = {
        "LoadBearing": True,
        "CustomRevitParam": "12345",
    }
    results = validate_pset("Pset_WallCommon", data, element_tag="W3")
    statuses = [r.status for r in results]
    assert PropertyValidationStatus.VALID in statuses
    assert PropertyValidationStatus.NON_STANDARD_PROPERTY in statuses

    # Custom non-Pset_ property set
    custom_pset_data = {"CustomCode": "A1"}
    custom_results = validate_pset("Pset_MyCustomSet", custom_pset_data, element_tag="W4")
    assert custom_results[0].status == PropertyValidationStatus.NON_STANDARD_PSET


def test_validate_element_psets_and_manifest():
    proxy = IfcBuildingElementProxy(
        tag="CHILLER-01",
        class_="IfcChiller",
        placement=ProxyPlacement(storey="ROOF"),
        properties={
            "Pset_ChillerTypeCommon": {
                "Reference": "CH-01",
                "NominalCapacity": 500.0,
                "RefrigerantClass": "R134a",
            }
        },
    )

    results = validate_element_psets(proxy)
    assert len(results) == 3
    assert all(r.status == PropertyValidationStatus.VALID for r in results)

    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-01", name="Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="ROOF", name="Roof Floor", elevation=10.0, height=3.0)]
        ),
        grids=Grids(axes_x={"A": 0.0}, axes_y={"1": 0.0}),
        materials=[],
        elements=[],
        proxies=[proxy],
    )

    manifest_results = validate_manifest_psets(manifest)
    assert len(manifest_results) == 3


def test_cli_validate_bsdd_integration(tmp_path):
    manifest_data = {
        "project": {"id": "PROJ-01", "name": "bSDD CLI Test"},
        "spatial_structure": {"storeys": [{"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0}]},
        "grids": {"axes_x": {"A": 0.0}, "axes_y": {"1": 0.0}},
        "materials": [],
        "elements": [],
        "proxies": [
            {
                "tag": "DOOR-01",
                "class": "IfcDoor",
                "placement": {"storey": "L1"},
                "properties": {
                    "Pset_DoorCommon": {
                        "IsExternal": True,
                        "FireRating": "2 Hours",
                    }
                },
            }
        ],
    }

    manifest_file = tmp_path / "project.yaml"
    with open(manifest_file, "w", encoding="utf-8") as f:
        yaml.dump(manifest_data, f)

    res = runner.invoke(app, ["validate", "-m", str(manifest_file), "--bsdd"])
    assert res.exit_code == 0, f"Exit code was {res.exit_code}, output:\n{res.stdout}"
    assert "buildingSMART bSDD Pset Validation Summary" in res.stdout
    assert "DOOR-01" in res.stdout

    # Test with strict mode failure on type mismatch
    invalid_manifest_data = {
        "project": {"id": "PROJ-02", "name": "bSDD CLI Failure Test"},
        "spatial_structure": {"storeys": [{"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0}]},
        "grids": {"axes_x": {"A": 0.0}, "axes_y": {"1": 0.0}},
        "materials": [],
        "elements": [],
        "proxies": [
            {
                "tag": "WALL-01",
                "class": "IfcWall",
                "placement": {"storey": "L1"},
                "properties": {
                    "Pset_WallCommon": {
                        "LoadBearing": "NOT_A_BOOLEAN",
                    }
                },
            }
        ],
    }
    invalid_file = tmp_path / "invalid_project.yaml"
    with open(invalid_file, "w", encoding="utf-8") as f:
        yaml.dump(invalid_manifest_data, f)

    res_strict = runner.invoke(app, ["validate", "-m", str(invalid_file), "--strict-psets"])
    assert res_strict.exit_code == 1
    assert "TYPE_MISMA" in res_strict.stdout or "expects type 'Boolean'" in res_strict.stdout
    assert "Strict Pset Validation Failed!" in res_strict.stdout
