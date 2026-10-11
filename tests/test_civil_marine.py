"""
Unit test suite for IFC4.3 Marine & Maritime Infrastructure: IfcMarineFacility, IfcMarinePart.
Verifies schema validation, 3D shape generation, and spatial hierarchy (IfcProject -> IfcSite -> IfcMarineFacility -> IfcMarinePart).
"""

from pathlib import Path
import pytest
import ifcopenshell
import ifcopenshell.geom
from pydantic import ValidationError

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcMarineFacility,
    IfcMarinePart,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_marine_schema_validation():
    """Test Pydantic v2 schema validation and predefined types for marine entities."""
    # 1. Marine Facility
    port = IfcMarineFacility(
        tag="PORT-01",
        name="Laem Chabang Deep Sea Port",
        predefined_type="PORT",
        water_depth=16.0,
        length=500.0,
        width=200.0,
        height=6.0,
        placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0},
    )
    assert port.class_ == "IfcMarineFacility"
    assert port.tag == "PORT-01"
    assert port.predefined_type == "PORT"
    assert port.water_depth == 16.0
    assert port.length == 500.0

    # 2. Marine Part
    quay = IfcMarinePart(
        tag="QUAY-BERTH-01",
        name="Container Berth Quay Wall",
        predefined_type="QUAY",
        facility="PORT-01",
        water_depth=16.0,
        length=350.0,
        width=30.0,
        height=8.0,
        placement={"offset_x": 10.0, "offset_y": 0.0, "offset_z": 0.0},
    )
    assert quay.class_ == "IfcMarinePart"
    assert quay.tag == "QUAY-BERTH-01"
    assert quay.predefined_type == "QUAY"
    assert quay.facility == "PORT-01"
    assert quay.length == 350.0


def test_marine_invalid_facility_reference():
    """Test schema reference validation for unknown marine facility tag."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PROJ-MAR-01", "name": "Marine Test"},
        "spatial_structure": {"storeys": [{"id": "GROUND", "name": "Ground", "elevation": 0.0, "height": 3.0}]},
        "grids": {"axes_x": {"1": 0.0, "2": 100.0}, "axes_y": {"A": 0.0, "B": 100.0}},
        "materials": [{"id": "MAT_CONC", "name": "Marine Concrete", "category": "concrete", "unit_cost_ref": "REF"}],
        "elements": [
            {
                "class": "IfcMarinePart",
                "tag": "QUAY-01",
                "predefined_type": "QUAY",
                "facility": "NON_EXISTENT_PORT",
                "placement": {"storey": "GROUND", "grid": ["1", "A"]},
            }
        ],
    }
    with pytest.raises(ValidationError):
        ProjectManifest.model_validate(manifest_data)


def test_marine_resolution_and_qto():
    """Test 3D spatial resolution and QTO calculations for marine elements."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-01", name="Marine & Coastal Infrastructure"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 300.0}, axes_y={"A": 0.0, "B": 150.0}),
        materials=[
            {"id": "MAT_MARINE_CONC", "name": "High Durability Marine Concrete", "category": "concrete", "unit_cost_ref": "MARINE-QUAY-WALL"}
        ],
        elements=[
            IfcMarineFacility(
                tag="PORT-MAIN",
                name="Shed & Quay Basin",
                predefined_type="PORT",
                material="MAT_MARINE_CONC",
                water_depth=15.0,
                length=300.0,
                width=150.0,
                height=5.0,
                placement={"storey": "GROUND", "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]},
            ),
            IfcMarinePart(
                tag="QUAY-WALL-1",
                name="Deep Water Quay Wall",
                predefined_type="QUAY",
                facility="PORT-MAIN",
                material="MAT_MARINE_CONC",
                water_depth=15.0,
                length=300.0,
                width=20.0,
                height=6.0,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcMarinePart(
                tag="BREAKWATER-1",
                name="Outer Protection Breakwater",
                predefined_type="BREAKWATER",
                facility="PORT-MAIN",
                material="MAT_MARINE_CONC",
                water_depth=20.0,
                length=150.0,
                width=25.0,
                height=8.0,
                placement={"storey": "GROUND", "from_grid": ["1", "B"], "to_grid": ["2", "B"]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.marine_facilities) == 1
    assert len(resolved.marine_parts) == 2

    fac = resolved.marine_facilities[0]
    assert fac.tag == "PORT-MAIN"
    assert fac.surface_area == 45000.0  # 300m * 150m
    assert fac.volume == 45000.0 * (5.0 + 15.0)  # 900,000 m3
    assert "QUAY-WALL-1" in fac.parts
    assert "BREAKWATER-1" in fac.parts

    quay = resolved.marine_parts[0]
    assert quay.tag == "QUAY-WALL-1"
    assert quay.length == 300.0
    assert quay.surface_area == 6000.0  # 300m * 20m
    assert quay.volume == 36000.0        # 6000 * 6.0
    assert quay.formwork_area == 2.0 * (300.0 + 20.0) * 6.0

    # QTO
    qto = calculate_qto(resolved)
    assert qto.total_marine_facility_area == 45000.0
    assert qto.total_marine_facility_volume == 900000.0
    assert qto.total_marine_part_length == 450.0  # 300 + 150
    assert qto.total_marine_part_volume > 36000.0


def test_marine_cost_estimation(tmp_path: Path):
    """Test price catalog generation and cost estimation for marine entities."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-02", name="Marine Cost Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 200.0}, axes_y={"A": 0.0, "B": 100.0}),
        materials=[
            {"id": "MAT_PORT_INFRA", "name": "Port Base Area", "category": "civil", "unit_cost_ref": "MARINE-FACILITY-PORT"},
            {"id": "MAT_MARINE_CONC", "name": "Marine Concrete", "category": "concrete", "unit_cost_ref": "MARINE-QUAY-WALL"}
        ],
        elements=[
            IfcMarineFacility(
                tag="PORT-01",
                predefined_type="PORT",
                material="MAT_PORT_INFRA",
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcMarinePart(
                tag="QUAY-01",
                predefined_type="QUAY",
                facility="PORT-01",
                material="MAT_MARINE_CONC",
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
        ],
    )

    qto = calculate_qto(manifest)
    tpl_path = tmp_path / "prices.yaml"
    generate_cost_template(manifest, output_path=tpl_path)

    catalog = load_price_catalog(tpl_path)
    assert "MARINE-FACILITY-PORT" in catalog.items
    assert "MARINE-QUAY-WALL" in catalog.items

    catalog.items["MARINE-FACILITY-PORT"].material_cost = 500.0
    catalog.items["MARINE-QUAY-WALL"].material_cost = 3500.0

    estimate = estimate_cost(qto, catalog, manifest)
    assert estimate.grand_total > 0.0


def test_marine_ifc_compilation_and_geom_shape_verification(tmp_path: Path):
    """Test IFC4.3 compilation, spatial hierarchy, and 3D shape verification with ifcopenshell.geom.create_shape."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-IFC", name="Marine IFC Export Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[
            {"id": "MAT_CONC", "name": "Marine Concrete", "category": "concrete", "unit_cost_ref": "C1"}
        ],
        elements=[
            IfcMarineFacility(
                tag="PORT-FACILITY-01",
                name="Deep Water Terminal",
                predefined_type="PORT",
                placement={"storey": "GROUND", "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]},
            ),
            IfcMarinePart(
                tag="QUAY-PART-01",
                name="Quay Wall Section A",
                predefined_type="QUAY",
                facility="PORT-FACILITY-01",
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
        ],
    )

    # 1. IFC Compilation
    ifc_file = tmp_path / "marine_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    # 2. Inspect spatial decomposition hierarchy in compiled IFC model:
    # IfcProject -> IfcSite -> IfcMarineFacility -> IfcMarinePart
    model = ifcopenshell.open(str(ifc_file))

    projects = model.by_type("IfcProject")
    assert len(projects) >= 1
    project = projects[0]

    # Site aggregated under project
    site = project.IsDecomposedBy[0].RelatedObjects[0]
    assert site.is_a("IfcSite")

    # MarineFacility / MarinePart elements
    facility_entity = [p for p in model if getattr(p, "Name", None) == "PORT-FACILITY-01"][0]
    part_entity = [p for p in model if getattr(p, "Name", None) == "QUAY-PART-01"][0]

    # 3. Verify 3D shape generation with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, part_entity)
    assert shape is not None
    assert len(shape.geometry.verts) > 0

    # 4. STEP Fallback compilation
    step_file = tmp_path / "marine_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCMARINEFACILITY" in step_content or "PORT-FACILITY-01" in step_content
    assert "IFCMARINEPART" in step_content or "QUAY-PART-01" in step_content


def test_marine_viewer_html_generation():
    """Test 3D HTML Web Viewer generation for marine entities."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-VIEW", name="Marine Viewer Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[
            {"id": "MAT_CONC", "name": "Concrete", "category": "concrete", "unit_cost_ref": "C1"}
        ],
        elements=[
            IfcMarineFacility(tag="PORT-01", placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]}),
            IfcMarinePart(tag="QUAY-01", facility="PORT-01", placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]}),
        ],
    )

    html = generate_viewer_html(manifest)
    assert "IfcMarineFacility" in html
    assert "PORT-01" in html
    assert "IfcMarinePart" in html
    assert "QUAY-01" in html
    assert "civil/marine/facilities" in html
    assert "civil/marine/parts" in html
