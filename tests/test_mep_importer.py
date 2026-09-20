"""
Unit tests for MEP distribution & generic proxy element extraction and re-compilation.
"""

from pathlib import Path
import sys
import pytest
import ifcopenshell
import ifcopenshell.api

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from debim.importer import import_ifc_to_manifest
from debim.compiler import compile_to_ifc, derive_custom_ifc_class
from debim.schema import IfcCustomElement
from tools.compare_ifc import count_ifc_elements


def test_legacy_schema_unsupported(tmp_path: Path):
    """Verify that unsupported legacy IFC schemas raise a clean ValueError."""
    ifc_file = ifcopenshell.file(schema="IFC2X3")
    test_ifc_path = tmp_path / "legacy.ifc"
    ifc_file.write(str(test_ifc_path))

    # Replace schema string in raw IFC STEP file
    content = test_ifc_path.read_text(encoding="utf-8")
    legacy_content = content.replace("FILE_SCHEMA(('IFC2X3'));", "FILE_SCHEMA(('IFC2X_FINAL'));")
    test_ifc_path.write_text(legacy_content, encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported legacy IFC schema 'IFC2X_FINAL'"):
        import_ifc_to_manifest(test_ifc_path)


def test_derive_custom_ifc_class_mep_and_proxies():
    """Verify derive_custom_ifc_class correctly maps layer keywords to IFC entity classes."""
    assert derive_custom_ifc_class("architecture/proxies") == "IfcBuildingElementProxy"
    assert derive_custom_ifc_class("architecture/chimneys") == "IfcChimney"
    assert derive_custom_ifc_class("structure/accessories") == "IfcDiscreteAccessory"
    assert derive_custom_ifc_class("mep/ducts") == "IfcDuctSegment"
    assert derive_custom_ifc_class("mep/pipes") == "IfcPipeSegment"
    assert derive_custom_ifc_class("mep/terminals") == "IfcAirTerminal"
    assert derive_custom_ifc_class("mep/fittings") == "IfcFlowFitting"


def test_mep_and_proxy_extraction_and_recompilation(tmp_path: Path):
    """Test creation, extraction, and re-compilation of MEP and proxy elements."""
    model = ifcopenshell.file(schema="IFC4")
    proj = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="MEP Test")
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    bldg = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Bldg")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Level 1")

    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=proj)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[bldg], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[storey], relating_object=bldg)

    # Create test elements
    duct = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDuctSegment", name="Duct-01")
    term = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcAirTerminal", name="Diffuser-01")
    fit = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcFlowFitting", name="Elbow-01")
    proxy = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingElementProxy", name="Proxy-01")
    chimney = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcChimney", name="Chimney-01")
    acc = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDiscreteAccessory", name="Shoe-01")

    elems = [duct, term, fit, proxy, chimney, acc]
    ifcopenshell.api.run("spatial.assign_container", model, products=elems, relating_structure=storey)

    orig_ifc_path = tmp_path / "orig_mep.ifc"
    model.write(str(orig_ifc_path))

    # 1. Import to manifest
    manifest = import_ifc_to_manifest(orig_ifc_path)
    assert len(manifest.elements) == 6

    layers = [e.layer for e in manifest.elements if isinstance(e, IfcCustomElement)]
    assert "mep/ducts" in layers
    assert "mep/terminals" in layers
    assert "mep/fittings" in layers
    assert "architecture/proxies" in layers
    assert "architecture/chimneys" in layers
    assert "structure/accessories" in layers

    # 2. Re-compile to IFC
    recomp_ifc_path = tmp_path / "recomp_mep.ifc"
    compile_to_ifc(manifest, recomp_ifc_path)

    orig_count, orig_breakdown = count_ifc_elements(orig_ifc_path)
    recomp_count, recomp_breakdown = count_ifc_elements(recomp_ifc_path)

    assert orig_count == 6
    assert recomp_count == 6
    assert recomp_breakdown["IfcDuctSegment"] == 1
    assert recomp_breakdown["IfcAirTerminal"] == 1
    assert recomp_breakdown["IfcFlowFitting"] == 1
    assert recomp_breakdown["IfcBuildingElementProxy"] == 1
    assert recomp_breakdown["IfcChimney"] == 1
    assert recomp_breakdown["IfcDiscreteAccessory"] == 1
