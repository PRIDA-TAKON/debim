"""
Unit tests for debim Exemplar Manifest Generator and Thai Workmanship Spec Library.
"""

import json
from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner

from debim.cli import app
from debim.docs.exemplar import (
    generate_exemplar_element,
    generate_exemplar_manifest,
    get_supported_exemplar_classes,
)
from debim.docs.thai_specs import (
    get_masterformat_code,
    get_thai_spec_clause,
    THAI_SPEC_LIBRARY,
)
from debim.schema import ProjectManifest

runner = CliRunner()


def test_supported_classes_list():
    classes = get_supported_exemplar_classes()
    assert isinstance(classes, list)
    assert len(classes) >= 40
    assert "IfcColumn" in classes
    assert "IfcWall" in classes
    assert "IfcPipeSegment" in classes
    assert "IfcPump" in classes


def test_generate_exemplar_element_all():
    classes = get_supported_exemplar_classes()
    for cls_name in classes:
        elem = generate_exemplar_element(cls_name)
        assert isinstance(elem, dict)
        assert "tag" in elem
        assert "class" in elem or "ifc_class" in elem
        assert "placement" in elem


def test_generate_exemplar_manifest_single():
    manifest = generate_exemplar_manifest(class_name="IfcColumn")
    assert isinstance(manifest, ProjectManifest)
    assert len(manifest.elements) == 1
    assert manifest.elements[0].class_ == "IfcColumn"


def test_generate_exemplar_manifest_all():
    manifest = generate_exemplar_manifest(class_name="ALL")
    assert isinstance(manifest, ProjectManifest)
    assert len(manifest.elements) >= 40
    # Confirm every element validates and is well-formed
    dict_dump = manifest.model_dump(by_alias=True, exclude_none=True)
    revalidated = ProjectManifest.model_validate(dict_dump)
    assert len(revalidated.elements) == len(manifest.elements)


def test_thai_spec_library():
    assert len(THAI_SPEC_LIBRARY) >= 8
    clause = get_thai_spec_clause("IfcColumn")
    assert clause.masterformat_code == "03 30 00"
    assert "คอนกรีต" in clause.masterformat_title
    assert "มอก." in clause.material_standards or "ASTM" in clause.material_standards
    assert "การบ่ม" in clause.workmanship_requirements or "การเข้าแบบ" in clause.workmanship_requirements
    assert "Slump" in clause.testing_inspection or "Compressive" in clause.testing_inspection

    clause_pipe = get_thai_spec_clause("IfcPipeSegment")
    assert clause_pipe.masterformat_code == "22 11 00"
    assert "Hydrostatic" in clause_pipe.testing_inspection or "แรงดันน้ำ" in clause_pipe.testing_inspection


def test_cli_docs_exemplar_stdout():
    result = runner.invoke(app, ["docs", "exemplar", "--class-name", "IfcWall"])
    assert result.exit_code == 0
    assert "IfcWall" in result.stdout
    assert "WALL-01" in result.stdout


def test_cli_docs_exemplar_file(tmp_path):
    out_file = tmp_path / "wall_exemplar.yaml"
    result = runner.invoke(app, ["docs", "exemplar", "-c", "IfcWall", "-o", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "IfcWall" in content


def test_cli_docs_export_data(tmp_path):
    out_dir = tmp_path / "docs_export"
    result = runner.invoke(app, ["docs", "export-data", "-o", str(out_dir)])
    assert result.exit_code == 0
    assert (out_dir / "exemplar_all.debim.yaml").exists()
    assert (out_dir / "exemplars" / "ifccolumn.yaml").exists()
    assert (out_dir / "specs_thai").exists()
    assert len(list((out_dir / "specs_thai").glob("*.md"))) >= 8
