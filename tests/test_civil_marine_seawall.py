"""
Unit tests for IFC4.3 Civil Marine Infrastructure: Concrete Seawalls & Groynes (IfcMarinePart).
"""

import tempfile
from pathlib import Path
import pytest
import ifcopenshell
import ifcopenshell.geom

from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    SpatialStructure,
    Storey,
    Grids,
    IfcMarinePart,
)
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc, StepSerializer
from debim.viewer import generate_viewer_html


def test_marine_seawall_schema_validation():
    """Test schema validation for IfcMarinePart with predefined_type SEAWALL and GROYNE."""
    # Valid vertical seawall
    sw1 = IfcMarinePart(
        tag="SW-01",
        predefined_type="SEAWALL",
        material="MAT_MARINE_CONC",
        length=50.0,
        wall_height=4.5,
        crest_width=1.0,
        base_width=2.5,
        parapet_height=0.0,
        placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0},
    )
    assert sw1.wall_height == 4.5
    assert sw1.crest_width == 1.0
    assert sw1.base_width == 2.5
    assert sw1.parapet_height == 0.0

    # Valid recurved seawall with parapet
    sw2 = IfcMarinePart(
        tag="SW-02",
        predefined_type="SEAWALL",
        material="MAT_MARINE_CONC",
        length=100.0,
        wall_height=5.0,
        crest_width=1.2,
        base_width=3.0,
        parapet_height=0.8,
        placement={"offset_x": 10.0, "offset_y": 0.0, "offset_z": 0.0},
    )
    assert sw2.parapet_height == 0.8

    # Valid groyne
    gr1 = IfcMarinePart(
        tag="GR-01",
        predefined_type="GROYNE",
        material="MAT_MARINE_CONC",
        length=30.0,
        wall_height=3.0,
        crest_width=1.5,
        base_width=3.5,
        parapet_height=0.0,
        placement={"offset_x": 0.0, "offset_y": 50.0, "offset_z": 0.0},
    )
    assert gr1.predefined_type == "GROYNE"
    assert gr1.length == 30.0

    # Invalid missing seawall parameters
    with pytest.raises(ValueError, match="wall_height.*crest_width.*base_width"):
        IfcMarinePart(
            tag="SW-ERR",
            predefined_type="SEAWALL",
            length=20.0,
            # Missing wall_height, crest_width, base_width
        )


def test_marine_seawall_spatial_resolution():
    """Test spatial resolution of vertical and recurved seawall cross-sections."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-SEAWALL-01", name="Seawall Test Project"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST-0", name="Ground", elevation=0.0, height=5.0)]),
        grids=Grids(axes_x={}, axes_y={}),
        materials=[
            {"id": "MAT_MARINE_CONC", "name": "Marine Grade C35 Concrete", "category": "concrete", "unit_cost_ref": "MAT-CONC"}
        ],
        elements=[
            IfcMarinePart(
                tag="SW-VERT",
                predefined_type="SEAWALL",
                material="MAT_MARINE_CONC",
                length=40.0,
                wall_height=4.0,
                crest_width=1.0,
                base_width=2.5,
                parapet_height=0.0,
                placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0, "rotation": 0.0},
            ),
            IfcMarinePart(
                tag="SW-RECURVED",
                predefined_type="SEAWALL",
                material="MAT_MARINE_CONC",
                length=60.0,
                wall_height=5.0,
                crest_width=1.2,
                base_width=3.0,
                parapet_height=1.0,
                placement={"offset_x": 0.0, "offset_y": 20.0, "offset_z": 0.0, "rotation": 0.0},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.marine_parts) == 2

    # Vertical seawall checks
    res_vert = resolved.marine_parts[0]
    assert res_vert.tag == "SW-VERT"
    assert res_vert.wall_height == 4.0
    assert res_vert.crest_width == 1.0
    assert res_vert.base_width == 2.5
    assert res_vert.parapet_height == 0.0
    assert len(res_vert.wall_profile_points) == 4  # Trap: (0,0), (2.5,0), (1.0,4.0), (0,4.0)

    # Area = (1.0 + 2.5)/2 * 4.0 = 7.0 m2
    # Concrete Volume = 7.0 * 40.0 = 280.0 m3
    assert abs(res_vert.concrete_volume - 280.0) < 1e-3
    assert res_vert.foundation_key_trench_volume > 0.0

    # Recurved seawall checks
    res_rec = resolved.marine_parts[1]
    assert res_rec.tag == "SW-RECURVED"
    assert res_rec.parapet_height == 1.0
    assert len(res_rec.wall_profile_points) == 6  # Recurved profile polygon has 6 vertices
    # Section area: Main stem = (1.2 + 3.0)/2 * 5.0 = 10.5 m2, parapet = 1.2 * 1.0 = 1.2 m2 -> total 11.7 m2
    # Concrete volume = 11.7 * 60.0 = 708.0 m3
    assert abs(res_rec.concrete_volume - 708.0) < 1e-3
    assert res_rec.formwork_area > 0.0


def test_marine_seawall_qto():
    """Test QTO calculation for seawalls and groynes."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-QTO", name="Marine QTO Project"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST-0", name="Ground", elevation=0.0, height=5.0)]),
        grids=Grids(axes_x={}, axes_y={}),
        materials=[
            {"id": "MAT_MARINE_CONC", "name": "Marine Grade C35 Concrete", "category": "concrete", "unit_cost_ref": "MAT-CONC"}
        ],
        elements=[
            IfcMarinePart(
                tag="SW-QTO",
                predefined_type="SEAWALL",
                material="MAT_MARINE_CONC",
                length=100.0,
                wall_height=5.0,
                crest_width=1.0,
                base_width=3.0,
                parapet_height=0.5,
                placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0},
            ),
            IfcMarinePart(
                tag="GR-QTO",
                predefined_type="GROYNE",
                material="MAT_MARINE_CONC",
                length=25.0,
                wall_height=3.0,
                crest_width=1.0,
                base_width=2.0,
                parapet_height=0.0,
                placement={"offset_x": 0.0, "offset_y": 50.0, "offset_z": 0.0},
            ),
        ],
    )

    qto_result = calculate_qto(manifest)
    eqto_sw = qto_result.get_element("SW-QTO")
    assert eqto_sw is not None
    assert eqto_sw.marine is not None
    assert eqto_sw.marine.wall_height == 5.0
    assert eqto_sw.marine.crest_width == 1.0
    assert eqto_sw.marine.base_width == 3.0
    assert eqto_sw.marine.parapet_height == 0.5
    assert eqto_sw.marine.deck_concrete_volume > 0.0
    assert eqto_sw.marine.formwork_area > 0.0
    assert eqto_sw.marine.foundation_key_trench_volume > 0.0

    eqto_gr = qto_result.get_element("GR-QTO")
    assert eqto_gr is not None
    assert eqto_gr.marine is not None
    assert eqto_gr.marine.deck_concrete_volume == 1.5 * 3.0 * 25.0  # (1+2)/2 * 3 * 25 = 112.5 m3
    assert eqto_gr.marine.foundation_key_trench_volume > 0.0


def test_marine_seawall_ifcopenshell_compilation_and_geometry():
    """Test compilation of IfcMarinePart (SEAWALL/GROYNE) and 3D geometry shape creation with IfcOpenShell."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-IFC", name="Marine IFC Project"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST-0", name="Ground", elevation=0.0, height=5.0)]),
        grids=Grids(axes_x={}, axes_y={}),
        materials=[
            {"id": "MAT_MARINE_CONC", "name": "Marine Grade C35 Concrete", "category": "concrete", "unit_cost_ref": "MAT-CONC"}
        ],
        elements=[
            IfcMarinePart(
                tag="SW-IFC-01",
                predefined_type="SEAWALL",
                material="MAT_MARINE_CONC",
                length=30.0,
                wall_height=4.0,
                crest_width=1.0,
                base_width=2.5,
                parapet_height=0.6,
                placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0, "rotation": 0.0},
            ),
            IfcMarinePart(
                tag="GR-IFC-01",
                predefined_type="GROYNE",
                material="MAT_MARINE_CONC",
                length=20.0,
                wall_height=3.0,
                crest_width=1.2,
                base_width=2.2,
                parapet_height=0.0,
                placement={"offset_x": 10.0, "offset_y": 0.0, "offset_z": 0.0, "rotation": 90.0},
            ),
        ],
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_ifc = Path(tmp_dir) / "seawall_model.ifc"
        compile_to_ifc(manifest, output_path=output_ifc)
        assert output_ifc.exists()

        model = ifcopenshell.open(str(output_ifc))

        # Retrieve IfcMarinePart entities (or IfcBuildingElementProxy fallback)
        try:
            marine_parts = model.by_type("IfcMarinePart")
        except RuntimeError:
            marine_parts = [e for e in model.by_type("IfcBuildingElementProxy") if "MarinePart" in (e.ObjectType or "")]

        assert len(marine_parts) == 2

        tags = [p.Name or p.Tag for p in marine_parts]
        assert "SW-IFC-01" in tags
        assert "GR-IFC-01" in tags

        sw_entity = [p for p in marine_parts if (p.Name or p.Tag) == "SW-IFC-01"][0]
        gr_entity = [p for p in marine_parts if (p.Name or p.Tag) == "GR-IFC-01"][0]

        # Validate 3D shape generation using ifcopenshell.geom
        settings = ifcopenshell.geom.settings()

        shape_sw = ifcopenshell.geom.create_shape(settings, sw_entity)
        assert shape_sw is not None
        assert len(shape_sw.geometry.verts) > 0
        assert len(shape_sw.geometry.faces) > 0

        shape_gr = ifcopenshell.geom.create_shape(settings, gr_entity)
        assert shape_gr is not None
        assert len(shape_gr.geometry.verts) > 0
        assert len(shape_gr.geometry.faces) > 0


def test_marine_seawall_step_serializer():
    """Test STEP fallback serialization for seawalls and groynes."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-STEP", name="STEP Project"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST-0", name="Ground", elevation=0.0, height=5.0)]),
        grids=Grids(axes_x={}, axes_y={}),
        materials=[
            {"id": "MAT_MARINE_CONC", "name": "Marine Grade C35 Concrete", "category": "concrete", "unit_cost_ref": "MAT-CONC"}
        ],
        elements=[
            IfcMarinePart(
                tag="SW-STEP-01",
                predefined_type="SEAWALL",
                material="MAT_MARINE_CONC",
                length=15.0,
                wall_height=3.5,
                crest_width=0.8,
                base_width=2.0,
                parapet_height=0.0,
                placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    serializer = StepSerializer()
    step_content = serializer.serialize(resolved)

    assert "IFCMARINEPART" in step_content
    assert ".SEAWALL." in step_content
    assert "IFCEXTRUDEDAREASOLID" in step_content
    assert "IFCARBITRARYCLOSEDPROFILEDEF" in step_content


def test_marine_seawall_viewer_html():
    """Test 3D web viewer generation containing seawall data."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-VIEWER", name="Viewer Project"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST-0", name="Ground", elevation=0.0, height=5.0)]),
        grids=Grids(axes_x={}, axes_y={}),
        materials=[
            {"id": "MAT_MARINE_CONC", "name": "Marine Grade C35 Concrete", "category": "concrete", "unit_cost_ref": "MAT-CONC"}
        ],
        elements=[
            IfcMarinePart(
                tag="SW-VIEW-01",
                predefined_type="SEAWALL",
                material="MAT_MARINE_CONC",
                length=25.0,
                wall_height=4.2,
                crest_width=1.1,
                base_width=2.6,
                parapet_height=0.5,
                placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0},
            ),
        ],
    )

    html = generate_viewer_html(manifest)
    assert "IfcMarinePart" in html
    assert "SEAWALL" in html
    assert "SW-VIEW-01" in html
    assert "wall_height" in html
    assert "foundation_key_trench_volume" in html
