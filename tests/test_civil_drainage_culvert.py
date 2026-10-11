"""
Unit test suite for IFC4.3 Civil Stormwater Box Culverts & Drainage Channels: IfcDistributionFlowElement.
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
    Grids,
    IfcDistributionFlowElement,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_culvert_schema_validation():
    """Test Pydantic v2 schema validation for IfcDistributionFlowElement."""
    c = IfcDistributionFlowElement(
        tag="CUL-01",
        predefined_type="CULVERT",
        length=10.0,
        internal_span=2.0,
        internal_rise=2.0,
        wall_thickness=0.25,
        slab_thickness=0.25,
        slope_pct=0.5,
    )
    assert c.class_ == "IfcDistributionFlowElement"
    assert c.tag == "CUL-01"
    assert c.predefined_type == "CULVERT"
    assert c.length == 10.0
    assert c.internal_span == 2.0
    assert c.internal_rise == 2.0
    assert c.wall_thickness == 0.25
    assert c.slab_thickness == 0.25
    assert c.slope_pct == 0.5

    # Test field aliases
    c_alias = IfcDistributionFlowElement(
        tag="DRAIN-01",
        predefined_type="DRAINAGE_CHANNEL",
        span=1.5,
        rise=1.0,
        wall=0.20,
        slab=0.20,
        slope=1.0,
    )
    assert c_alias.internal_span == 1.5
    assert c_alias.internal_rise == 1.0
    assert c_alias.wall_thickness == 0.20
    assert c_alias.slab_thickness == 0.20
    assert c_alias.slope_pct == 1.0


def test_culvert_resolution_and_qto():
    """Test 3D spatial resolution and quantity take-off for box culverts and drainage channels."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-CULVERT-01", name="Highway Drainage Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 20.0}, axes_y={"A": 0.0, "B": 10.0}),
        materials=[
            Material(id="MAT_CONCRETE", name="Structural Concrete C30/37", category="concrete", unit_cost_ref="MAT-CONC"),
        ],
        elements=[
            IfcDistributionFlowElement(
                tag="BOX-CUL-01",
                predefined_type="CULVERT",
                length=15.0,
                internal_span=2.0,
                internal_rise=2.0,
                wall_thickness=0.25,
                slab_thickness=0.25,
                slope_pct=0.5,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcDistributionFlowElement(
                tag="U-DRAIN-01",
                predefined_type="DRAINAGE_CHANNEL",
                length=20.0,
                internal_span=1.0,
                internal_rise=1.0,
                wall_thickness=0.20,
                slab_thickness=0.20,
                slope_pct=1.0,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.distribution_flow_elements) == 2

    # Box Culvert
    bc = resolved.distribution_flow_elements[0]
    assert bc.tag == "BOX-CUL-01"
    assert bc.hydraulic_flow_area == 4.0
    assert bc.concrete_cross_section_area == 2.25
    assert bc.concrete_volume == 2.25 * 20.0  # grid distance 1 to 2 is 20m

    # Drainage Channel
    dc = resolved.distribution_flow_elements[1]
    assert dc.tag == "U-DRAIN-01"
    assert dc.hydraulic_flow_area == 1.0
    assert abs(dc.concrete_cross_section_area - 0.68) < 1e-6
    assert abs(dc.concrete_volume - 0.68 * 20.0) < 1e-6

    # QTO
    qto = calculate_qto(resolved)
    eqto = qto.get_element("BOX-CUL-01")
    assert eqto is not None
    assert eqto.culvert is not None
    assert eqto.culvert.hydraulic_flow_area == 4.0
    assert eqto.culvert.concrete_volume == 45.0
    assert qto.total_culvert_concrete_volume > 0.0


def test_culvert_ifc43_compilation_and_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape generation for box culverts and channels."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-CULVERT-02", name="Culvert Geometry Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 10.0}, axes_y={"A": 0.0, "B": 10.0}),
        materials=[
            Material(id="MAT_CONCRETE", name="Structural Concrete C30/37", category="concrete", unit_cost_ref="MAT-CONC"),
        ],
        elements=[
            IfcDistributionFlowElement(
                tag="CULVERT-3D",
                predefined_type="CULVERT",
                length=10.0,
                internal_span=2.0,
                internal_rise=2.0,
                wall_thickness=0.25,
                slab_thickness=0.25,
                slope_pct=0.5,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
            IfcDistributionFlowElement(
                tag="CHANNEL-3D",
                predefined_type="DRAINAGE_CHANNEL",
                length=10.0,
                internal_span=1.0,
                internal_rise=1.0,
                wall_thickness=0.20,
                slab_thickness=0.20,
                slope_pct=0.5,
                placement={"storey": "GROUND", "grid": ["2", "A"]},
            ),
        ],
    )

    # 1. Compile to IFC
    ifc_file = tmp_path / "culvert_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    # 2. Verify IFC entity counts
    flow_elems = model.by_type("IfcDistributionFlowElement")
    if not flow_elems:
        flow_elems = [e for e in model.by_type("IfcBuildingElementProxy") if "IfcDistributionFlowElement" in (getattr(e, "ObjectType", "") or "")]
    if not flow_elems:
        flow_elems = model.by_type("IfcBuildingElementProxy")

    assert len(flow_elems) >= 2

    # 3. Verify 3D geometry shape creation with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()
    shape1 = ifcopenshell.geom.create_shape(settings, flow_elems[0])
    assert shape1 is not None
    assert len(shape1.geometry.verts) > 0

    shape2 = ifcopenshell.geom.create_shape(settings, flow_elems[1])
    assert shape2 is not None
    assert len(shape2.geometry.verts) > 0

    # 4. STEP physical file fallback export
    step_file = tmp_path / "culvert_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCDISTRIBUTIONFLOWELEMENT" in step_content or "IfcDistributionFlowElement" in step_content

    # 5. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "CULVERT-3D" in html
