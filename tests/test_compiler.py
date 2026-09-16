"""
Unit tests for IFC4 Compiler and STEP exporter engine.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc, generate_ifc_guid, StepSerializer
from debim.resolver import resolve_manifest
from debim.schema import load_manifest


def test_generate_ifc_guid():
    guid1 = generate_ifc_guid()
    guid2 = generate_ifc_guid()
    assert len(guid1) == 22
    assert len(guid2) == 22
    assert guid1 != guid2


def test_compile_to_ifc_townhouse_default(tmp_path):
    manifest_path = Path("examples/townhouse/project.yaml")
    output_path = tmp_path / "model.ifc"

    result_path = compile_to_ifc(manifest_path, output_path)

    assert result_path.exists()
    assert result_path.stat().st_size > 0

    content = result_path.read_text(encoding="utf-8")
    assert "ISO-10303-21;" in content
    assert "IFC4" in content
    assert "IFCCOLUMN" in content
    assert "IFCBEAM" in content
    assert "IFCWALL" in content
    assert "IFCDOOR" in content


def test_compile_to_ifc_townhouse_fallback(tmp_path):
    manifest_path = Path("examples/townhouse/project.yaml")
    output_path = tmp_path / "model_fallback.ifc"

    result_path = compile_to_ifc(manifest_path, output_path, force_fallback=True)

    assert result_path.exists()
    assert result_path.stat().st_size > 0

    content = result_path.read_text(encoding="utf-8")
    assert "ISO-10303-21;" in content
    assert "IFC4" in content
    assert "IFCCOLUMN" in content
    assert "IFCBEAM" in content
    assert "IFCWALL" in content
    assert "IFCDOOR" in content


def test_compile_from_manifest_object(tmp_path):
    manifest = load_manifest("examples/townhouse/project.yaml")
    output_path = tmp_path / "from_obj.ifc"

    result_path = compile_to_ifc(manifest, output_path)
    assert result_path.exists()
    assert result_path.stat().st_size > 0


def test_compile_from_resolved_manifest_object(tmp_path):
    manifest = load_manifest("examples/townhouse/project.yaml")
    resolved = resolve_manifest(manifest)
    output_path = tmp_path / "from_resolved.ifc"

    result_path = compile_to_ifc(resolved, output_path)
    assert result_path.exists()
    assert result_path.stat().st_size > 0


def test_step_serializer_arg_formatting():
    serializer = StepSerializer()
    assert serializer._format_arg(None) == "$"
    assert serializer._format_arg(True) == ".T."
    assert serializer._format_arg(False) == ".F."
    assert serializer._format_arg("#123") == "#123"
    assert serializer._format_arg(".METRE.") == ".METRE."
    assert serializer._format_arg("Hello 'World'") == "'Hello ''World'''"
    assert serializer._format_arg(3.50) == "3.5"
    assert serializer._format_arg([1, 2, "a"]) == "(1,2,'a')"
