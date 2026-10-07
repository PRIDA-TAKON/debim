"""
Unit test suite for IFC4.3 Civil Infrastructure Entities: IfcAlignment, IfcRoad, IfcBridge.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcAlignment,
    IfcBridge,
    IfcRoad,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_civil_infrastructure_schema_validation():
    """Test Pydantic v2 schema validation and default value handling for civil entities."""
    # 1. Alignment
    align = IfcAlignment(
        tag="ALIGN-HW-01",
        name="Highway Alignment 101",
        start_chainage=100.0,
        design_speed_kmh=120.0,
        placement={"points": [[0, 0, 0], [50, 20, 0], [100, 50, 5]]},
    )
    assert align.class_ == "IfcAlignment"
    assert align.tag == "ALIGN-HW-01"
    assert align.start_chainage == 100.0
    assert len(align.placement.points) == 3
    assert align.placement.points[1].x == 50.0

    # 2. Road
    road = IfcRoad(
        tag="ROAD-HW-01",
        predefined_type="HIGHWAY",
        road_width=12.0,
        corridor_length=250.0,
        lanes_count=4,
        pavement_surface_thickness=0.08,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert road.class_ == "IfcRoad"
    assert road.predefined_type == "HIGHWAY"
    assert road.road_width == 12.0
    assert road.width == 12.0
    assert road.pavement_surface_thickness == 0.08

    # 3. Bridge
    bridge = IfcBridge(
        tag="BRIDGE-01",
        predefined_type="GIRDER",
        span_length=40.0,
        deck_width=15.0,
        deck_thickness=0.40,
        pier_height=8.0,
        pier_count=3,
        pier_shape="RECTANGULAR",
        pier_width=1.5,
        pier_depth=1.5,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert bridge.class_ == "IfcBridge"
    assert bridge.span_length == 40.0
    assert bridge.pier_count == 3
    assert bridge.pier_shape == "RECTANGULAR"


def test_civil_infrastructure_resolution_and_qto():
    """Test 3D spatial resolution and QTO calculations for civil infrastructure elements."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-CIVIL-01", name="Highway & Bridge Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 200.0}, axes_y={"A": 0.0, "B": 100.0}),
        materials=[
            {"id": "MAT_ASPHALT", "name": "Asphalt Concrete", "category": "asphalt", "unit_cost_ref": "ROAD-ASPHALT-PAVEMENT"},
            {"id": "MAT_CONCRETE", "name": "Reinforced Concrete", "category": "concrete", "unit_cost_ref": "BRIDGE-RC-DECK"},
        ],
        elements=[
            IfcAlignment(
                tag="ALIGN-01",
                placement={"storey": "GROUND", "points": [[0, 0, 0], [100, 0, 0], [200, 50, 0]]},
            ),
            IfcRoad(
                tag="ROAD-01",
                material="MAT_ASPHALT",
                predefined_type="CARRIAGEWAY",
                road_width=10.0,
                pavement_surface_thickness=0.05,
                pavement_base_thickness=0.15,
                pavement_subbase_thickness=0.20,
                placement={
                    "storey": "GROUND",
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                },
            ),
            IfcBridge(
                tag="BRIDGE-01",
                material="MAT_CONCRETE",
                predefined_type="GIRDER",
                span_length=50.0,
                deck_width=12.0,
                deck_thickness=0.35,
                pier_height=6.0,
                pier_count=2,
                pier_shape="CYLINDRICAL",
                pier_diameter=1.2,
                placement={
                    "storey": "GROUND",
                    "from_grid": ["1", "B"],
                    "to_grid": ["2", "B"],
                },
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.alignments) == 1
    assert len(resolved.roads) == 1
    assert len(resolved.bridges) == 1

    r_align = resolved.alignments[0]
    assert r_align.tag == "ALIGN-01"
    assert r_align.total_length > 200.0

    r_road = resolved.roads[0]
    assert r_road.tag == "ROAD-01"
    assert r_road.corridor_length == 200.0
    assert r_road.surface_area == 2000.0  # 10m * 200m
    assert r_road.asphalt_volume == 100.0  # 2000 * 0.05
    assert r_road.base_volume == 300.0    # 2000 * 0.15
    assert r_road.subbase_volume == 400.0 # 2000 * 0.20

    r_bridge = resolved.bridges[0]
    assert r_bridge.tag == "BRIDGE-01"
    assert r_bridge.span_length == 200.0  # Computed from grid 1 to 2 span (200m)
    assert r_bridge.deck_concrete_volume == 200.0 * 12.0 * 0.35  # 840 m3
    assert len(r_bridge.pier_positions) == 2

    # QTO
    qto = calculate_qto(resolved)
    assert qto.total_alignment_length == r_align.total_length
    assert qto.total_road_surface_area == 2000.0
    assert qto.total_road_asphalt_volume == 100.0
    assert qto.total_road_base_volume == 300.0
    assert qto.total_road_subbase_volume == 400.0
    assert qto.total_bridge_concrete_volume == r_bridge.total_concrete_volume
    assert qto.total_bridge_formwork_area == r_bridge.formwork_area


def test_civil_cost_estimation(tmp_path: Path):
    """Test price catalog generation and cost estimation for civil entities."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-CIVIL-02", name="Civil Cost Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[
            {"id": "MAT_ASPHALT", "name": "Asphalt Concrete", "category": "asphalt", "unit_cost_ref": "ROAD-ASPHALT-PAVEMENT"},
            {"id": "MAT_CONCRETE", "name": "Reinforced Concrete", "category": "concrete", "unit_cost_ref": "BRIDGE-RC-DECK"},
        ],
        elements=[
            IfcRoad(
                tag="ROAD-01",
                material="MAT_ASPHALT",
                road_width=7.0,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBridge(
                tag="BRIDGE-01",
                material="MAT_CONCRETE",
                span_length=100.0,
                deck_width=10.0,
                placement={"storey": "GROUND", "from_grid": ["1", "B"], "to_grid": ["2", "B"]},
            ),
        ],
    )

    qto = calculate_qto(manifest)
    tpl_path = tmp_path / "prices.yaml"
    generate_cost_template(manifest, output_path=tpl_path)

    catalog = load_price_catalog(tpl_path)
    assert "ROAD-ASPHALT-PAVEMENT" in catalog.items
    assert "ROAD-BASE-CRUSHED-ROCK" in catalog.items
    assert "BRIDGE-RC-DECK" in catalog.items

    # Set mock prices
    catalog.items["ROAD-ASPHALT-PAVEMENT"].material_cost = 250.0
    catalog.items["ROAD-ASPHALT-PAVEMENT"].labor_cost = 50.0
    catalog.items["BRIDGE-RC-DECK"].material_cost = 2500.0
    catalog.items["BRIDGE-RC-DECK"].labor_cost = 500.0

    estimate = estimate_cost(qto, catalog, manifest)
    codes = [item.code for item in estimate.line_items]
    assert "ROAD-ASPHALT-PAVEMENT" in codes
    assert "BRIDGE-RC-DECK" in codes
    assert estimate.grand_total > 0.0


def test_civil_ifc_export_and_viewer(tmp_path: Path):
    """Test IFC file compilation and 3D HTML viewer generation for civil infrastructure."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-CIVIL-03", name="Civil Export Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[
            {"id": "MAT_CONC", "name": "Concrete", "category": "concrete", "unit_cost_ref": "C1"}
        ],
        elements=[
            IfcAlignment(tag="ALIGN-01", placement={"storey": "GROUND", "points": [[0, 0, 0], [100, 0, 0]]}),
            IfcRoad(tag="ROAD-01", placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]}, road_width=8.0),
            IfcBridge(tag="BRIDGE-01", placement={"storey": "GROUND", "from_grid": ["1", "B"], "to_grid": ["2", "B"]}, span_length=100.0, deck_width=10.0),
        ],
    )

    # 1. Standard IFC compilation
    ifc_file = tmp_path / "model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()
    content = ifc_file.read_text(encoding="utf-8")
    assert "ROAD-01" in content or "IfcRoad" in content
    assert "BRIDGE-01" in content or "IfcBridge" in content

    # 2. STEP Fallback compilation
    step_file = tmp_path / "model_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCALIGNMENT" in step_content
    assert "IFCROAD" in step_content
    assert "IFCBRIDGE" in step_content

    # 3. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcAlignment" in html
    assert "IfcRoad" in html
    assert "IfcBridge" in html
    assert "ROAD-01" in html
    assert "BRIDGE-01" in html
