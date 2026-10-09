"""
Unit test suite for IFC4.3 Civil Marine Infrastructure: Rubble Mound Breakwaters & Revetments (IfcMarinePart).
Validates schema validation, 3D spatial resolution, trapezoidal QTO volume/tonnage calculations,
and IFC compilation with 3D shape generation using ifcopenshell.geom.create_shape.
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
    IfcMarinePart,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_breakwater_revetment_schema_validation():
    """Test Pydantic v2 schema validation for breakwater and revetment elements."""
    bw = IfcMarinePart(
        tag="BW-01",
        name="Main Breakwater North Arm",
        predefined_type="BREAKWATER",
        length=200.0,
        crest_width=8.0,
        crest_elevation=5.0,
        depth=12.0,
        slope_ratio=1.5,
        armor_weight_tons=12500.0,
        placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0},
    )
    assert bw.class_ == "IfcMarinePart"
    assert bw.tag == "BW-01"
    assert bw.predefined_type == "BREAKWATER"
    assert bw.length == 200.0
    assert bw.crest_width == 8.0
    assert bw.width == 8.0
    assert bw.crest_elevation == 5.0
    assert bw.deck_elevation == 5.0
    assert bw.depth == 12.0
    assert bw.slope_ratio == 1.5
    assert bw.armor_weight_tons == 12500.0

    rev = IfcMarinePart(
        tag="REV-01",
        name="Coastal Protection Revetment",
        predefined_type="REVETMENT",
        length=150.0,
        crest_width=4.0,
        base_width=28.0,
        crest_elevation=3.0,
        depth=8.0,
        armor_weight_tons=4200.0,
    )
    assert rev.predefined_type == "REVETMENT"
    assert rev.crest_width == 4.0
    assert rev.base_width == 28.0
    assert rev.armor_weight_tons == 4200.0


def test_breakwater_trapezoidal_resolution_and_qto():
    """Test 3D spatial resolution and QTO calculation for trapezoidal breakwater cross-section."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-BW", name="Port Harbor Protection"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="SEA_LEVEL", name="Mean Sea Level", elevation=0.0, height=0.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[
            {"id": "MAT_ROCK_CORE", "name": "Quarry Run Core Rock", "category": "rock", "unit_cost_ref": "MAT-ROCK"},
        ],
        elements=[
            IfcMarinePart(
                tag="BW-MAIN",
                material="MAT_ROCK_CORE",
                predefined_type="BREAKWATER",
                length=100.0,
                crest_width=6.0,
                crest_elevation=4.0,
                depth=10.0,
                slope_ratio=1.5,
                armor_weight_tons=5000.0,
                placement={"storey": "SEA_LEVEL", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcMarinePart(
                tag="REV-SOUTH",
                material="MAT_ROCK_CORE",
                predefined_type="REVETMENT",
                length=50.0,
                crest_width=3.0,
                base_width=27.0,
                crest_elevation=2.0,
                depth=6.0,
                armor_weight_tons=1800.0,
                placement={"storey": "SEA_LEVEL", "grid": ["1", "B"]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.marine_parts) == 2

    rbw = resolved.marine_parts[0]
    assert rbw.tag == "BW-MAIN"
    assert rbw.length == 100.0
    assert rbw.crest_width == 6.0
    # H = 10.0 + 4.0 = 14.0 m
    # base_width = 6.0 + 2 * 14.0 * 1.5 = 48.0 m
    # cross_section_area = (6.0 + 48.0) / 2 * 14.0 = 378.0 m2
    # core_rock_volume = 378.0 * 100.0 = 37,800.0 m3
    assert rbw.base_width == 48.0
    assert rbw.cross_section_area == 378.0
    assert rbw.core_rock_volume == 37800.0

    rrev = resolved.marine_parts[1]
    assert rrev.tag == "REV-SOUTH"
    assert rrev.base_width == 27.0
    # H = 6.0 + 2.0 = 8.0 m
    # cross_section_area = (3.0 + 27.0) / 2 * 8.0 = 120.0 m2
    # core_rock_volume = 120.0 * 50.0 = 6,000.0 m3
    assert rrev.cross_section_area == 120.0
    assert rrev.core_rock_volume == 6000.0

    # QTO Take-Off
    qto = calculate_qto(resolved)
    eqto_bw = qto.get_element("BW-MAIN")
    assert eqto_bw is not None
    assert eqto_bw.marine is not None
    assert eqto_bw.marine.crest_width == 6.0
    assert eqto_bw.marine.base_width == 48.0
    assert eqto_bw.marine.core_rock_volume == 37800.0
    assert eqto_bw.marine.armor_rock_tonnage == 5000.0

    eqto_rev = qto.get_element("REV-SOUTH")
    assert eqto_rev is not None
    assert eqto_rev.marine is not None
    assert eqto_rev.marine.core_rock_volume == 6000.0
    assert eqto_rev.marine.armor_rock_tonnage == 1800.0


def test_breakwater_ifc_export_and_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape generation for breakwater and revetment."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-BW-IFC", name="Breakwater IFC Model Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="SEA_LEVEL", name="Mean Sea Level", elevation=0.0, height=0.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 80.0}, axes_y={"A": 0.0, "B": 20.0}),
        materials=[],
        elements=[
            IfcMarinePart(
                tag="BW-01",
                predefined_type="BREAKWATER",
                length=80.0,
                crest_width=5.0,
                crest_elevation=3.0,
                depth=7.0,
                slope_ratio=1.5,
                armor_weight_tons=3500.0,
                placement={"storey": "SEA_LEVEL", "grid": ["1", "A"]},
            ),
        ],
    )

    # 1. Compile to IFC4.3
    ifc_file = tmp_path / "breakwater_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    marine_parts = model.by_type("IfcMarinePart")
    if not marine_parts:
        marine_parts = [e for e in model.by_type("IfcBuildingElementProxy") if "MarinePart" in (e.ObjectType or "")]

    assert len(marine_parts) == 1

    # 2. Verify 3D geometry shape creation with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()
    shape_bw = ifcopenshell.geom.create_shape(settings, marine_parts[0])
    assert shape_bw is not None
    assert len(shape_bw.geometry.verts) > 0

    # 3. Fallback STEP file export
    step_file = tmp_path / "breakwater_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCMARINEPART" in step_content or "IfcMarinePart" in step_content

    # 4. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcMarinePart" in html
    assert "BW-01" in html
    assert "BREAKWATER" in html
