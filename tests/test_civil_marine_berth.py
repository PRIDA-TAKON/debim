"""
Unit test suite for IFC4.3 Civil Marine Infrastructure: IfcMarinePart (BERTH, JETTY, QUAY, PIER).
Verifies schema validation, 3D spatial resolution, QTO calculation, IFC4.3 compilation,
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
    FootingPiles,
    Grids,
    IfcMarinePart,
    PileProfile,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_marine_part_schema_validation():
    """Test Pydantic v2 schema validation for IfcMarinePart and predefined types."""
    mp = IfcMarinePart(
        tag="BERTH-01",
        name="Container Terminal Berth 1",
        predefined_type="BERTH",
        length=100.0,
        width=25.0,
        deck_thickness=0.80,
        deck_elevation=2.5,
        depth=15.0,
        piles=FootingPiles(
            count=20,
            length=30.0,
            profile=PileProfile(shape="CIRCULAR", diameter=1.2),
        ),
        placement={"offset_x": 10.0, "offset_y": 20.0, "offset_z": 0.0},
    )
    assert mp.class_ == "IfcMarinePart"
    assert mp.tag == "BERTH-01"
    assert mp.predefined_type == "BERTH"
    assert mp.length == 100.0
    assert mp.width == 25.0
    assert mp.deck_thickness == 0.80
    assert mp.deck_elevation == 2.5
    assert mp.depth == 15.0
    assert mp.piles is not None
    assert mp.piles.count == 20
    assert mp.piles.length == 30.0

    # Test predefined types for IfcMarinePart
    for ptype in ["BERTH", "JETTY", "QUAY", "PIER", "USERDEFINED"]:
        p = IfcMarinePart(tag=f"MP-{ptype}", predefined_type=ptype)
        assert p.predefined_type == ptype

    # Test field aliases/validator
    mp_alias = IfcMarinePart(
        tag="QUAY-01",
        predefined_type="QUAY",
        thickness=0.60,
        elevation=1.5,
        pile_count=12,
        pile_length=25.0,
    )
    assert mp_alias.deck_thickness == 0.60
    assert mp_alias.deck_elevation == 1.5
    assert mp_alias.piles is not None
    assert mp_alias.piles.count == 12
    assert mp_alias.piles.length == 25.0


def test_marine_part_resolution_and_qto():
    """Test 3D spatial resolution and quantity take-off for marine infrastructure."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-01", name="Deepwater Container Terminal"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 30.0}),
        materials=[
            {"id": "MAT_MARINE_CONC", "name": "Marine Grade C50 Concrete", "category": "concrete", "unit_cost_ref": "MAT-CONC"},
        ],
        elements=[
            IfcMarinePart(
                tag="BERTH-MAIN",
                material="MAT_MARINE_CONC",
                predefined_type="BERTH",
                length=50.0,
                width=20.0,
                deck_thickness=0.70,
                deck_elevation=2.0,
                depth=12.0,
                piles=FootingPiles(
                    count=12,
                    length=20.0,
                    profile=PileProfile(shape="CIRCULAR", diameter=1.0),
                ),
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcMarinePart(
                tag="JETTY-01",
                material="MAT_MARINE_CONC",
                predefined_type="JETTY",
                length=30.0,
                width=10.0,
                deck_thickness=0.50,
                deck_elevation=1.0,
                depth=8.0,
                placement={"storey": "GROUND", "grid": ["1", "A"], "offset_x": 0.0, "offset_y": 0.0},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.marine_parts) == 2

    rmp = resolved.marine_parts[0]
    assert rmp.tag == "BERTH-MAIN"
    assert rmp.length == 50.0
    assert rmp.width == 20.0
    assert rmp.concrete_volume == 50.0 * 20.0 * 0.70  # 700.0 m3
    assert rmp.pile_count == 12
    assert rmp.pile_total_length == 12 * 20.0  # 240.0 m
    assert len(rmp.deck_boundary) == 4
    assert len(rmp.piles) == 12

    # QTO
    qto = calculate_qto(resolved)
    eqto = qto.get_element("BERTH-MAIN")
    assert eqto is not None
    assert eqto.concrete_volume == 700.0
    assert eqto.marine is not None
    assert eqto.marine.length == 50.0
    assert eqto.marine.width == 20.0
    assert eqto.marine.deck_concrete_volume == 700.0
    assert eqto.marine.pile_count == 12
    assert eqto.marine.pile_total_length == 240.0
    assert eqto.substructure is not None
    assert eqto.substructure.pile_count == 12
    assert eqto.substructure.pile_total_length == 240.0


def test_marine_part_ifc43_compilation_and_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape generation with ifcopenshell."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-02", name="Berth Geometry Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 40.0}, axes_y={"A": 0.0, "B": 15.0}),
        materials=[],
        elements=[
            IfcMarinePart(
                tag="QUAY-01",
                predefined_type="QUAY",
                length=40.0,
                width=15.0,
                deck_thickness=0.60,
                deck_elevation=1.5,
                depth=10.0,
                piles=FootingPiles(
                    count=6,
                    length=18.0,
                    profile=PileProfile(shape="CIRCULAR", diameter=0.80),
                ),
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
        ],
    )

    # 1. Compile to IFC4.3
    ifc_file = tmp_path / "marine_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    # 2. Verify IFC entity counts
    marine_parts = model.by_type("IfcMarinePart")
    piles = model.by_type("IfcPile")
    if not marine_parts:
        marine_parts = [e for e in model.by_type("IfcBuildingElementProxy") if "MarinePart" in (e.ObjectType or "")]

    assert len(marine_parts) == 1
    assert len(piles) >= 6 or len(model.by_type("IfcBuildingElementProxy")) >= 6

    # 3. Verify 3D geometry shape creation with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()

    shape_marine = ifcopenshell.geom.create_shape(settings, marine_parts[0])
    assert shape_marine is not None
    assert len(shape_marine.geometry.verts) > 0

    if piles:
        shape_pile = ifcopenshell.geom.create_shape(settings, piles[0])
        assert shape_pile is not None
        assert len(shape_pile.geometry.verts) > 0

    # 4. STEP physical file fallback export
    step_file = tmp_path / "marine_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCMARINEPART" in step_content or "IfcMarinePart" in step_content
    assert "IFCPILE" in step_content or "IfcPile" in step_content

    # 5. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcMarinePart" in html
    assert "QUAY-01" in html
