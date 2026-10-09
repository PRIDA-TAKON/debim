"""
Unit test suite for IFC4.3 Civil Bridge Components & Structural Parts: IfcBridgePart and IfcBearing.
Verifies schema validation, 3D spatial resolution, QTO calculation, IFC4.3 compilation,
spatial decomposition hierarchy (IfcProject -> IfcSite -> IfcBridge -> IfcBridgePart -> IfcBearing),
and 3D shape generation with ifcopenshell.geom.create_shape.
"""

from pathlib import Path
import pytest
import ifcopenshell
import ifcopenshell.geom

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcBearing,
    IfcBridge,
    IfcBridgePart,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_bridge_part_and_bearing_schema_validation():
    """Test Pydantic v2 schema validation for IfcBridgePart and IfcBearing."""
    # 1. IfcBridgePart
    part = IfcBridgePart(
        tag="BP-SUPER-01",
        name="Superstructure Deck Girder",
        predefined_type="SUPERSTRUCTURE",
        bridge="BRIDGE-01",
        span_length=35.0,
        part_width=12.0,
        part_thickness=0.40,
        part_height=2.5,
    )
    assert part.class_ == "IfcBridgePart"
    assert part.tag == "BP-SUPER-01"
    assert part.predefined_type == "SUPERSTRUCTURE"
    assert part.bridge == "BRIDGE-01"
    assert part.span_length == 35.0
    assert part.width == 12.0
    assert part.height == 2.5

    # Test predefined types for IfcBridgePart
    for ptype in ["SUBSTRUCTURE", "SUPERSTRUCTURE", "DECK", "PIER", "ABUTMENT", "FOUNDATION"]:
        p = IfcBridgePart(tag=f"BP-{ptype}", predefined_type=ptype)
        assert p.predefined_type == ptype

    # 2. IfcBearing
    bearing = IfcBearing(
        tag="BR-ELAST-01",
        predefined_type="ELASTOMERIC",
        bridge_part="BP-SUPER-01",
        width=0.60,
        depth=0.60,
        height=0.25,
        placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 6.0},
    )
    assert bearing.class_ == "IfcBearing"
    assert bearing.tag == "BR-ELAST-01"
    assert bearing.predefined_type == "ELASTOMERIC"
    assert bearing.bridge_part == "BP-SUPER-01"
    assert bearing.width == 0.60
    assert bearing.height == 0.25

    # Test predefined types for IfcBearing
    for btype in ["BRIDGEBEARING", "ELASTOMERIC", "POT", "ROLLER", "SPHERICAL"]:
        b = IfcBearing(tag=f"BEAR-{btype}", predefined_type=btype)
        assert b.predefined_type == btype


def test_bridge_parts_resolution_and_qto():
    """Test 3D spatial resolution and quantity take-off for bridge parts and bearings."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-BRIDGE-01", name="Advanced Bridge Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 50.0}, axes_y={"A": 0.0, "B": 12.0}),
        materials=[
            {"id": "MAT_CONC", "name": "Concrete C40", "category": "concrete", "unit_cost_ref": "BRIDGE-RC-DECK"},
            {"id": "MAT_RUBBER", "name": "Elastomeric Rubber", "category": "rubber", "unit_cost_ref": "BEARING-PAD"},
        ],
        elements=[
            IfcBridge(
                tag="BRIDGE-01",
                material="MAT_CONC",
                predefined_type="GIRDER",
                span_length=50.0,
                deck_width=12.0,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBridgePart(
                tag="BP-SUPER-01",
                material="MAT_CONC",
                predefined_type="SUPERSTRUCTURE",
                bridge="BRIDGE-01",
                span_length=50.0,
                part_width=12.0,
                part_thickness=0.35,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBridgePart(
                tag="BP-SUB-01",
                material="MAT_CONC",
                predefined_type="SUBSTRUCTURE",
                bridge="BRIDGE-01",
                span_length=12.0,
                part_width=2.0,
                part_thickness=1.5,
                placement={"storey": "GROUND", "grid": ["1", "A"], "offset_z": 0.0},
            ),
            IfcBearing(
                tag="BEAR-01",
                material="MAT_RUBBER",
                predefined_type="ELASTOMERIC",
                bridge_part="BP-SUPER-01",
                width=0.60,
                depth=0.60,
                height=0.20,
                placement={"storey": "GROUND", "grid": ["1", "A"], "offset_z": 6.0},
            ),
            IfcBearing(
                tag="BEAR-02",
                material="MAT_RUBBER",
                predefined_type="ELASTOMERIC",
                bridge_part="BP-SUPER-01",
                width=0.60,
                depth=0.60,
                height=0.20,
                placement={"storey": "GROUND", "grid": ["2", "A"], "offset_z": 6.0},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.bridges) == 1
    assert len(resolved.bridge_parts) == 2
    assert len(resolved.bearings) == 2

    bp_super = resolved.bridge_parts[0]
    assert bp_super.tag == "BP-SUPER-01"
    assert bp_super.span_length == 50.0
    assert bp_super.width == 12.0
    assert bp_super.concrete_volume == 50.0 * 12.0 * 0.35  # 210.0 m3

    br1 = resolved.bearings[0]
    assert br1.tag == "BEAR-01"
    assert br1.position == (0.0, 0.0, 6.0)

    # QTO
    qto = calculate_qto(resolved)
    assert len(qto.elements) == 5
    eqto_bp = qto.get_element("BP-SUPER-01")
    assert eqto_bp is not None
    assert eqto_bp.concrete_volume == 210.0

    eqto_br = qto.get_element("BEAR-01")
    assert eqto_br is not None
    assert eqto_br.mep is not None
    assert eqto_br.mep.count == 1


def test_bridge_parts_ifc43_compilation_and_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation, spatial hierarchy, and 3D shape generation with ifcopenshell."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-BRIDGE-02", name="Bridge Geometry Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 40.0}, axes_y={"A": 0.0, "B": 10.0}),
        materials=[],
        elements=[
            IfcBridge(
                tag="BRIDGE-01",
                predefined_type="GIRDER",
                span_length=40.0,
                deck_width=10.0,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBridgePart(
                tag="BP-DECK-01",
                predefined_type="DECK",
                bridge="BRIDGE-01",
                span_length=40.0,
                part_width=10.0,
                part_thickness=0.30,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBridgePart(
                tag="BP-PIER-01",
                predefined_type="PIER",
                bridge="BRIDGE-01",
                span_length=10.0,
                part_width=1.5,
                part_thickness=1.5,
                part_height=6.0,
                placement={"storey": "GROUND", "grid": ["1", "A"], "offset_z": 0.0},
            ),
            IfcBearing(
                tag="BEAR-01",
                predefined_type="ELASTOMERIC",
                bridge_part="BP-DECK-01",
                width=0.80,
                depth=0.80,
                height=0.25,
                placement={"storey": "GROUND", "grid": ["1", "A"], "offset_z": 6.0},
            ),
        ],
    )

    # 1. Compile to IFC4.3
    ifc_file = tmp_path / "bridge_parts_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    # 2. Verify IFC entity counts and spatial hierarchy
    bridges = model.by_type("IfcBridge")
    bridge_parts = model.by_type("IfcBridgePart")
    bearings = model.by_type("IfcBearing")

    assert len(bridges) == 1
    assert len(bridge_parts) == 2
    assert len(bearings) == 1

    site = model.by_type("IfcSite")[0]
    bridge_obj = bridges[0]
    deck_part_obj = [p for p in bridge_parts if p.Name == "BP-DECK-01"][0]
    bearing_obj = bearings[0]

    # Site decomposes into Bridge
    assert len(site.IsDecomposedBy) > 0
    assert bridge_obj in site.IsDecomposedBy[0].RelatedObjects

    # Bridge decomposes into BridgeParts
    assert len(bridge_obj.IsDecomposedBy) > 0
    decomposed_parts = bridge_obj.IsDecomposedBy[0].RelatedObjects
    assert deck_part_obj in decomposed_parts

    # BridgePart contains Bearing
    assert len(deck_part_obj.ContainsElements) > 0
    contained_elements = deck_part_obj.ContainsElements[0].RelatedElements
    assert bearing_obj in contained_elements

    # 3. Verify 3D geometry shape creation with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()

    shape_deck = ifcopenshell.geom.create_shape(settings, deck_part_obj)
    assert shape_deck is not None
    assert len(shape_deck.geometry.verts) > 0

    shape_bearing = ifcopenshell.geom.create_shape(settings, bearing_obj)
    assert shape_bearing is not None
    assert len(shape_bearing.geometry.verts) > 0

    # 4. STEP physical file fallback export
    step_file = tmp_path / "bridge_parts_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCBRIDGEPART" in step_content
    assert "IFCBEARING" in step_content

    # 5. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcBridgePart" in html
    assert "IfcBearing" in html
    assert "BP-DECK-01" in html
    assert "BEAR-01" in html
