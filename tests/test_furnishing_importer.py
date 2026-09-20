from pathlib import Path
import tempfile
import ifcopenshell
from debim.importer import import_ifc_to_manifest
from debim.compiler import compile_to_ifc
from debim.schema import IfcCustomElement


def test_furnishing_element_importer():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "Duplex_A_20110907.ifc"
    manifest = import_ifc_to_manifest(fixture_path)

    # Filter custom elements with layer="interior/furniture"
    furnishing_elements = [
        e for e in manifest.elements
        if isinstance(e, IfcCustomElement) and e.layer == "interior/furniture"
    ]

    # 1. 61 furnishing elements extracted
    assert len(furnishing_elements) == 61

    # 2. Each has valid layer, position, and storey
    storey_ids = {s.id for s in manifest.spatial_structure.storeys}
    for furn in furnishing_elements:
        assert furn.layer == "interior/furniture"
        assert furn.source.startswith("assets/furniture/")
        assert furn.source.endswith(".glb")
        assert isinstance(furn.placement.position, tuple)
        assert len(furn.placement.position) == 3
        assert furn.placement.storey in storey_ids


def test_furnishing_element_compiler():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "Duplex_A_20110907.ifc"
    manifest = import_ifc_to_manifest(fixture_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_ifc = Path(tmpdir) / "recompiled_furniture.ifc"
        compile_to_ifc(manifest, out_ifc)

        assert out_ifc.exists()
        ifc_file = ifcopenshell.open(str(out_ifc))
        recomp_furns = ifc_file.by_type("IfcFurnishingElement")
        assert len(recomp_furns) == 61
