import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from debim.schema import ProjectManifest, ProjectInfo, SpatialStructure, Storey, Grids, Material, IfcCustomElement, CustomElementPlacement, Dimensions
from debim.resolver import SpatialResolver, ResolvedSweptDisk
from debim.viewer import generate_viewer_html
from debim.draw.projection import slice_storey
from tools.render_visual_regression import run_visual_regression


def test_ifc_flow_fitting_resolution_and_swept_disk():
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PROJ1", name="Test Fitting"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"GX1": 0.0}, axes_y={"GY1": 0.0}),
        materials=[Material(id="PVC", name="PVC Fitting", category="plastic", unit_cost_ref="MAT-PLASTIC-01")],
        elements=[
            IfcCustomElement(
                tag="Elbow-90-110mm",
                name="PVC Elbow 90 deg 110mm",
                source="test/fitting",
                placement=CustomElementPlacement(position=(2.0, 3.0, 0.5), storey="FL1"),
                dimensions=Dimensions(width=0.11, depth=0.11, height=0.11),
                layer="mep/fittings",
                material="PVC",
            )
        ]
    )

    resolved = SpatialResolver(manifest).resolve()
    assert len(resolved.custom_elements) == 1
    custom = resolved.custom_elements[0]
    assert custom.tag == "Elbow-90-110mm"
    assert custom.resolved_solid is not None
    assert isinstance(custom.resolved_solid, ResolvedSweptDisk)
    assert custom.resolved_solid.radius == 0.055
    assert len(custom.resolved_solid.directrix) == 3


def test_ifc_flow_fitting_viewer_html():
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PROJ1", name="Test Fitting Viewer"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"GX1": 0.0}, axes_y={"GY1": 0.0}),
        materials=[Material(id="PVC", name="PVC Fitting", category="plastic", unit_cost_ref="MAT-PLASTIC-01")],
        elements=[
            IfcCustomElement(
                tag="Tee-110mm",
                name="PVC Tee 110mm",
                source="test/fitting",
                placement=CustomElementPlacement(position=(1.0, 1.0, 0.0), storey="FL1"),
                dimensions=Dimensions(width=0.15, depth=0.11, height=0.11),
                layer="mep/fittings",
                material="PVC",
            )
        ]
    )

    resolved = SpatialResolver(manifest).resolve()
    html_out = generate_viewer_html(resolved)
    assert "Tee-110mm" in html_out
    assert "swept_disk" in html_out
    assert "IfcFlowFitting" in html_out


def test_ifc_flow_fitting_2d_projection():
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PROJ1", name="Test Fitting Projection"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"GX1": 0.0}, axes_y={"GY1": 0.0}),
        materials=[Material(id="PVC", name="PVC Fitting", category="plastic", unit_cost_ref="MAT-PLASTIC-01")],
        elements=[
            IfcCustomElement(
                tag="Elbow-Floor1",
                name="Floor 1 Elbow",
                source="test/fitting",
                placement=CustomElementPlacement(position=(5.0, 5.0, 1.2), storey="FL1"),
                dimensions=Dimensions(width=0.1, depth=0.1, height=0.1),
                layer="mep/fittings",
                material="PVC",
            )
        ]
    )

    res = slice_storey(manifest, storey_id="FL1", cut_offset_z=1.2)
    fitting_cuts = [e for e in res.cut_elements if e.element_class == "IfcFlowFitting"]
    assert len(fitting_cuts) == 1
    assert fitting_cuts[0].tag == "Elbow-Floor1"


def test_ifc_flow_fitting_visual_regression():
    ifc_path = Path("tests/fixtures/Duplex_MEP_20110907.ifc")
    if not ifc_path.exists():
        pytest.skip("Fixture Duplex_MEP_20110907.ifc not found.")

    res = run_visual_regression(
        ifc_path=ifc_path,
        output_dir=Path("dist/test_visual_reg"),
        max_elements_per_type=2,
        limit_total=10,
        save_images=False,
    )

    summary = res.get("class_summary", {})
    assert "IfcFlowFitting" in summary
    fitting_summary = summary["IfcFlowFitting"]
    assert fitting_summary["avg_iou"] >= 95.0
    assert fitting_summary["avg_match"] >= 85.0
