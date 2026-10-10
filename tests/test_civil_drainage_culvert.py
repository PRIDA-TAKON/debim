"""
Unit test suite for IFC4.3 Civil Stormwater & Drainage Infrastructure:
IfcDistributionFlowElement precast and in-situ reinforced concrete box culverts.
Verifies schema validation, multi-cell geometries, spatial slope resolution,
hydraulic QTO take-off, IFC4.3 compilation, and 3D web viewer generation.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcDistributionFlowElement,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_drainage_culvert_schema_validation():
    """Test Pydantic schema validation and automatic defaults for CULVERT."""
    culvert = IfcDistributionFlowElement(
        tag="CULV-01",
        name="Main Stormwater Box Culvert",
        predefined_type="CULVERT",
        internal_span=2.5,
        internal_rise=2.0,
        wall_thickness=0.30,
        slab_thickness=0.35,
        cell_count=2,
        placement={"storey": "GROUND", "grid_start": ["1", "A"], "grid_end": ["2", "A"]},
    )
    assert culvert.class_ == "IfcDistributionFlowElement"
    assert culvert.tag == "CULV-01"
    assert culvert.predefined_type == "CULVERT"
    assert culvert.internal_span == 2.5
    assert culvert.internal_rise == 2.0
    assert culvert.wall_thickness == 0.30
    assert culvert.slab_thickness == 0.35
    assert culvert.cell_count == 2
    assert culvert.placement.grid_start == ("1", "A")
    assert culvert.placement.grid_end == ("2", "A")

    # Verify single-cell default geometry
    single_cell = IfcDistributionFlowElement(
        tag="CULV-SINGLE",
        predefined_type="CULVERT",
    )
    assert single_cell.internal_span == 2.0
    assert single_cell.internal_rise == 2.0
    assert single_cell.wall_thickness == 0.25
    assert single_cell.slab_thickness == 0.25
    assert single_cell.cell_count == 1


def test_drainage_culvert_spatial_slope_resolution():
    """Test culvert spatial coordinate resolution along grid with hydraulic slope."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-CULVERT-01", name="Drainage Culvert Placement Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 50.0}, axes_y={"A": 10.0, "B": 10.0}),
        materials=[],
        elements=[
            IfcDistributionFlowElement(
                tag="CULV-RUN-01",
                predefined_type="CULVERT",
                internal_span=3.0,
                internal_rise=2.5,
                wall_thickness=0.25,
                slab_thickness=0.30,
                cell_count=1,
                placement={
                    "storey": "GROUND",
                    "grid_start": ["1", "A"],
                    "grid_end": ["2", "A"],
                    "inlet_elevation": -1.0,
                    "outlet_elevation": -1.5,
                },
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.distribution_flow_elements) == 1

    culv_res = resolved.distribution_flow_elements[0]
    assert culv_res.tag == "CULV-RUN-01"
    assert culv_res.predefined_type == "CULVERT"

    # Outer dimensions:
    # outer_width = 1 * 3.0 + (1 + 1) * 0.25 = 3.50 m
    # outer_height = 2.5 + 2 * 0.30 = 3.10 m
    assert culv_res.outer_width == pytest.approx(3.50, abs=1e-3)
    assert culv_res.outer_height == pytest.approx(3.10, abs=1e-3)

    # Coordinates: start=(0.0, 10.0, -1.0), end=(50.0, 10.0, -1.5)
    assert culv_res.start_point == (0.0, 10.0, -1.0)
    assert culv_res.end_point == (50.0, 10.0, -1.5)
    # Length: sqrt(50^2 + 0^2 + (-0.5)^2) = approx 50.0025 m
    assert culv_res.length == pytest.approx(50.0025, abs=1e-2)

    # Hydraulic slope percent: (0.5 / 50.0) * 100 = 1.0%
    assert culv_res.slope_percent == pytest.approx(1.0, abs=1e-2)
    assert "drainage" in culv_res.layer


def test_drainage_culvert_qto_metrics():
    """Test QTO calculation of concrete volume, formwork area, and hydraulic waterway flow area."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-CULVERT-QTO", name="Culvert QTO Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 20.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[
            # Twin cell culvert (2 cells):
            # Span = 2.0 m, Rise = 2.0 m, Tw = 0.25 m, Ts = 0.25 m, Length = 20.0 m
            # Outer width = 2 * 2.0 + (2 + 1) * 0.25 = 4.0 + 0.75 = 4.75 m
            # Outer height = 2.0 + 2 * 0.25 = 2.50 m
            # Void area (hydraulic flow) = 2 cells * (2.0 * 2.0) = 8.0 m2
            # Concrete section area = (4.75 * 2.50) - 8.0 = 11.875 - 8.0 = 3.875 m2
            # Concrete volume = 3.875 * 20.0 = 77.5 m3
            # Formwork area = (2 * (outer_w + outer_h) + 2 * (span + rise) * cells) * length
            #               = (2 * 7.25 + 2 * 4.0 * 2) * 20.0 = (14.5 + 16.0) * 20.0 = 30.5 * 20.0 = 610.0 m2
            IfcDistributionFlowElement(
                tag="CULV-TWIN-01",
                predefined_type="CULVERT",
                internal_span=2.0,
                internal_rise=2.0,
                wall_thickness=0.25,
                slab_thickness=0.25,
                cell_count=2,
                placement={
                    "storey": "GROUND",
                    "grid_start": ["1", "A"],
                    "grid_end": ["2", "A"],
                },
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    qto = calculate_qto(resolved)

    assert qto.total_culverts_count == 1
    assert qto.total_culvert_length == pytest.approx(20.0, abs=1e-3)
    assert qto.total_culvert_hydraulic_area == pytest.approx(8.0, abs=1e-3)
    assert qto.total_culvert_concrete_volume == pytest.approx(77.5, abs=1e-3)
    assert qto.total_culvert_formwork_area == pytest.approx(610.0, abs=1.0)

    eqto = qto.get_element("CULV-TWIN-01")
    assert eqto is not None
    assert eqto.distribution_flow is not None
    assert eqto.distribution_flow.cell_count == 2
    assert eqto.distribution_flow.hydraulic_flow_area == pytest.approx(8.0, abs=1e-3)
    assert eqto.distribution_flow.concrete_volume == pytest.approx(77.5, abs=1e-3)
    assert eqto.distribution_flow.formwork_area == pytest.approx(610.0, abs=1.0)


def test_drainage_culvert_compiler_and_viewer(tmp_path: Path):
    """Test IFC export and 3D web viewer generation for stormwater culverts."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-CULVERT-IFC", name="Culvert IFC Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 30.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[
            IfcDistributionFlowElement(
                tag="CULV-EXP-01",
                predefined_type="CULVERT",
                internal_span=2.0,
                internal_rise=2.0,
                placement={
                    "storey": "GROUND",
                    "grid_start": ["1", "A"],
                    "grid_end": ["2", "A"],
                },
            ),
        ],
    )

    resolved = resolve_manifest(manifest)

    # 1. Test fallback pure Python compiler
    step_file = tmp_path / "culvert_fallback.ifc"
    compile_to_ifc(resolved, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    content = step_file.read_text(encoding="utf-8")
    assert "IfcDistributionFlowElement.CULVERT" in content
    assert "IFCEXTRUDEDAREASOLID" in content

    # 2. Test 3D Web Viewer generation
    html = generate_viewer_html(resolved)
    assert "IfcDistributionFlowElement" in html
    assert "CULVERT" in html
    assert "internal_span" in html
    assert "CULV-EXP-01" in html
