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
    manifest_path = Path("tests/fixtures/townhouse/project.yaml")
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
    manifest_path = Path("tests/fixtures/townhouse/project.yaml")
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
    manifest = load_manifest("tests/fixtures/townhouse/project.yaml")
    output_path = tmp_path / "from_obj.ifc"

    result_path = compile_to_ifc(manifest, output_path)
    assert result_path.exists()
    assert result_path.stat().st_size > 0


def test_compile_from_resolved_manifest_object(tmp_path):
    manifest = load_manifest("tests/fixtures/townhouse/project.yaml")
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


def test_compile_custom_element_geometry_default(tmp_path):
    import ifcopenshell
    from debim.schema import ProjectManifest

    manifest_dict = {
        "schema": "IFC4-Minimal",
        "project": {"id": "P1", "name": "Custom Test Project"},
        "spatial_structure": {
            "storeys": [{"id": "L1", "name": "Level 1", "elevation": 3.0, "height": 3.5}]
        },
        "grids": {"axes_x": {"1": 0.0, "2": 5.0}, "axes_y": {"A": 0.0, "B": 5.0}},
        "materials": [{"id": "M1", "name": "Wood", "category": "timber", "unit_cost_ref": "REF1"}],
        "elements": [
            {
                "class": "IfcCustomElement",
                "tag": "SOFA-01",
                "name": "Sofa",
                "source": "assets/sofa.glb",
                "placement": {
                    "position": [2.0, 3.0, 0.5],
                    "storey": "L1",
                    "rotation": [0.0, 0.0, 90.0],
                },
                "dimensions": {"width": 1.8, "depth": 0.9, "height": 0.8},
                "layer": "interior/furniture",
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_dict)
    output_path = tmp_path / "custom_model.ifc"

    compile_to_ifc(manifest, output_path)

    assert output_path.exists()
    model = ifcopenshell.open(output_path)

    customs = model.by_type("IfcFurnishingElement")
    assert len(customs) == 1
    sofa = customs[0]

    # Local placement relative to storey
    assert sofa.ObjectPlacement is not None
    assert sofa.ObjectPlacement.PlacementRelTo is not None
    coords = sofa.ObjectPlacement.RelativePlacement.Location.Coordinates
    assert pytest.approx(coords[0], abs=1e-3) == 2.0
    assert pytest.approx(coords[1], abs=1e-3) == 3.0
    assert pytest.approx(coords[2], abs=1e-3) == 0.5

    # Shape representation
    assert sofa.Representation is not None
    assert sofa.Representation.is_a("IfcProductDefinitionShape")
    reps = sofa.Representation.Representations
    assert len(reps) == 1
    rep = reps[0]
    assert rep.RepresentationIdentifier == "Body"
    assert rep.RepresentationType == "SweptSolid"

    items = rep.Items
    assert len(items) == 1
    solid = items[0]
    assert solid.is_a("IfcExtrudedAreaSolid")
    assert pytest.approx(solid.Depth, abs=1e-3) == 0.8


def test_compile_custom_element_geometry_fallback(tmp_path):
    from debim.schema import ProjectManifest

    manifest_dict = {
        "schema": "IFC4-Minimal",
        "project": {"id": "P1", "name": "Custom Test Project"},
        "spatial_structure": {
            "storeys": [{"id": "L1", "name": "Level 1", "elevation": 3.0, "height": 3.5}]
        },
        "grids": {"axes_x": {"1": 0.0, "2": 5.0}, "axes_y": {"A": 0.0, "B": 5.0}},
        "materials": [{"id": "M1", "name": "Wood", "category": "timber", "unit_cost_ref": "REF1"}],
        "elements": [
            {
                "class": "IfcCustomElement",
                "tag": "SOFA-01",
                "name": "Sofa",
                "source": "assets/sofa.glb",
                "placement": {
                    "position": [2.0, 3.0, 0.5],
                    "storey": "L1",
                    "rotation": [0.0, 0.0, 0.0],
                },
                "dimensions": {"width": 1.8, "depth": 0.9, "height": 0.8},
                "layer": "interior/furniture",
            }
        ],
    }

    manifest = ProjectManifest.model_validate(manifest_dict)
    output_path = tmp_path / "custom_model_fallback.ifc"

    compile_to_ifc(manifest, output_path, force_fallback=True)

    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "IFCFURNISHINGELEMENT" in content
    assert "IFCRECTANGLEPROFILEDEF" in content
    assert "IFCEXTRUDEDAREASOLID" in content
    assert "IFCSHAPEREPRESENTATION" in content
    assert "IFCPRODUCTDEFINITIONSHAPE" in content
