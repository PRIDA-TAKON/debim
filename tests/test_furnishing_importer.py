from pathlib import Path
import tempfile
import ifcopenshell
from debim.importer import import_ifc_to_manifest
from debim.compiler import compile_to_ifc
from debim.schema import IfcCustomElement


from debim.draw.projection import slice_storey
from debim.resolver import resolve_manifest
from debim.schema import Dimensions, FurniturePlacement, IfcFurnishingElement, IfcFurniture
from debim.viewer import generate_viewer_html


def test_furnishing_element_importer():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "Duplex_A_20110907.ifc"
    manifest = import_ifc_to_manifest(fixture_path)

    # Filter elements with layer="interior/furniture"
    furnishing_elements = [
        e for e in manifest.elements
        if e.layer == "interior/furniture"
    ]

    # 1. 61 furnishing elements extracted
    assert len(furnishing_elements) == 61

    # 2. Each has valid layer, position, and storey
    storey_ids = {s.id for s in manifest.spatial_structure.storeys}
    for furn in furnishing_elements:
        assert furn.layer == "interior/furniture"
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


def test_ifc_furniture_schema_and_resolution():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "Building-Architecture.ifc"
    manifest = import_ifc_to_manifest(fixture_path)

    furn_elements = [e for e in manifest.elements if isinstance(e, (IfcFurniture, IfcFurnishingElement))]
    assert len(furn_elements) >= 1

    furn = furn_elements[0]
    assert isinstance(furn, IfcFurniture)
    assert furn.tag == "kitchen"
    assert furn.dimensions.width == 1.6
    assert furn.dimensions.depth == 0.6
    assert furn.dimensions.height == 0.9
    assert furn.placement.position == (8.1497, 7.0992, 0.0)

    # Test spatial resolver
    resolved = resolve_manifest(manifest)
    assert len(resolved.furniture) >= 1

    res_furn = resolved.furniture[0]
    assert res_furn.tag == "kitchen"
    assert res_furn.position == (8.1497, 7.0992, 0.0)
    assert res_furn.dimensions == (1.6, 0.6, 0.9)
    assert res_furn.bounding_box["volume"] == 1.6 * 0.6 * 0.9

    # Test 3D Web Viewer payload
    html = generate_viewer_html(resolved)
    assert "IfcFurniture" in html
    assert "kitchen" in html

    # Test 2D cut-plane projection
    cut_res = slice_storey(resolved, "00 groundfloor", cut_offset_z=1.2)
    furn_proj = [p for p in cut_res.projection_elements if p.element_class in ("IfcFurniture", "IfcFurnishingElement")]
    assert len(furn_proj) >= 1
    assert furn_proj[0].tag == "kitchen"
