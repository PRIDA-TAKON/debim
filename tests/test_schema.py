"""
Unit tests for debim.schema parsing and manifest validation.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError
import yaml

from debim.schema import (
    IfcBeam,
    IfcColumn,
    IfcCustomElement,
    IfcWall,
    ProjectManifest,
    load_manifest,
)


def test_load_townhouse_manifest():
    manifest_path = Path("examples/townhouse/project.yaml")
    manifest = load_manifest(manifest_path)
    assert isinstance(manifest, ProjectManifest)
    assert manifest.project.id == "PRJ-2026-001"
    assert manifest.project.name == "Townhouse-Feasibility"
    assert len(manifest.spatial_structure.storeys) == 2
    assert len(manifest.materials) == 2
    assert len(manifest.elements) == 4

    # Verify element instances
    classes = [elem.class_ for elem in manifest.elements]
    assert classes == ["IfcColumn", "IfcBeam", "IfcWall", "IfcCustomElement"]

    column = manifest.elements[0]
    assert isinstance(column, IfcColumn)
    assert column.tag == "C-A1"

    beam = manifest.elements[1]
    assert isinstance(beam, IfcBeam)
    assert beam.tag == "B-A1_B1"

    wall = manifest.elements[2]
    assert isinstance(wall, IfcWall)
    assert wall.tag == "W-A1_A2"
    assert len(wall.children) == 1
    assert wall.children[0].class_ == "IfcDoor"

    custom = manifest.elements[3]
    assert isinstance(custom, IfcCustomElement)
    assert custom.tag == "ST-01"


def test_invalid_storey_reference():
    with open("examples/townhouse/project.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Change column base_storey to non-existent storey L99
    data["elements"][0]["placement"]["base_storey"] = "L99"

    with pytest.raises(ValidationError) as exc_info:
        ProjectManifest.model_validate(data)
    assert "references unknown base_storey 'L99'" in str(exc_info.value)


def test_invalid_grid_reference():
    with open("examples/townhouse/project.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Change beam from_grid X axis to unknown axis Z
    data["elements"][1]["placement"]["from_grid"] = ["Z", "1"]

    with pytest.raises(ValidationError) as exc_info:
        ProjectManifest.model_validate(data)
    assert "references unknown X grid 'Z'" in str(exc_info.value)


def test_invalid_material_reference():
    with open("examples/townhouse/project.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Change wall material to unknown material MAT_999
    data["elements"][2]["material"] = "MAT_999"

    with pytest.raises(ValidationError) as exc_info:
        ProjectManifest.model_validate(data)
    assert "references unknown material 'MAT_999'" in str(exc_info.value)


def test_missing_file_raises_error():
    with pytest.raises(FileNotFoundError):
        load_manifest("non_existent_file.yaml")
