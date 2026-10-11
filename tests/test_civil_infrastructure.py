import math
import pytest

from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    SpatialStructure,
    Storey,
    Grids,
    Material,
    CivilPlacement,
    AlignmentPoint,
    IfcAlignment,
    IfcRoad,
    IfcBridge,
)
from debim.resolver import SpatialResolver
from debim.qto import calculate_qto
from debim.cost import estimate_cost, PriceCatalog, PriceItem
from debim.compiler import StepSerializer, compile_to_ifc
from debim.viewer import generate_viewer_html


@pytest.fixture
def sample_civil_manifest():
    return ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="CIVIL-PROJ-01", name="Civil Infrastructure Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.5)]
        ),
        grids=Grids(
            axes_x={"A": 0.0, "B": 100.0, "C": 200.0},
            axes_y={"1": 0.0, "2": 50.0},
        ),
        materials=[
            Material(id="ASPHALT", name="Asphalt Concrete", density=2400.0, category="asphalt", unit_cost_ref="ROAD-ASPHALT-PAVEMENT"),
            Material(id="CONCRETE_C30", name="Concrete C30/37", density=2500.0, category="concrete", unit_cost_ref="BRIDGE-RC-DECK"),
        ],
        elements=[
            IfcAlignment(
                tag="ALIGN-01",
                predefined_type="HORIZONTAL",
                start_chainage=100.0,
                design_speed=80.0,
                path=[
                    AlignmentPoint(x=0.0, y=0.0, z=0.0, station=100.0),
                    AlignmentPoint(x=100.0, y=0.0, z=0.0, station=200.0),
                    AlignmentPoint(x=100.0, y=100.0, z=10.0, station=300.0),
                ],
                placement=CivilPlacement(storey="GROUND", offset_x=0.0, offset_y=0.0, offset_z=0.0),
            ),
            IfcRoad(
                tag="ROAD-01",
                predefined_type="HIGHWAY",
                material="ASPHALT",
                corridor_length=150.0,
                road_width=10.0,
                surface_thickness=0.05,
                base_thickness=0.20,
                subbase_thickness=0.25,
                lanes_count=4,
                alignment_ref="ALIGN-01",
                placement=CivilPlacement(
                    storey="GROUND",
                    from_grid=("A", "1"),
                    to_grid=("B", "1"),
                ),
            ),
            IfcBridge(
                tag="BRIDGE-01",
                predefined_type="GIRDER",
                material="CONCRETE_C30",
                span_length=40.0,
                deck_width=12.0,
                deck_thickness=0.40,
                pier_height=8.0,
                pier_count=3,
                pier_shape="CYLINDRICAL",
                pier_diameter=1.2,
                placement=CivilPlacement(
                    storey="GROUND",
                    from_grid=("B", "1"),
                    to_grid=("C", "1"),
                ),
            ),
            IfcBridge(
                tag="BRIDGE-02",
                predefined_type="SLAB",
                material="CONCRETE_C30",
                span_length=20.0,
                deck_width=8.0,
                deck_thickness=0.30,
                pier_height=5.0,
                pier_count=2,
                pier_shape="RECTANGULAR",
                pier_diameter=1.0,
                placement=CivilPlacement(
                    storey="GROUND",
                    offset_x=0.0,
                    offset_y=50.0,
                    offset_z=0.0,
                ),
            ),
        ],
    )


def test_civil_alignment_resolution(sample_civil_manifest):
    resolver = SpatialResolver(sample_civil_manifest)
    resolved = resolver.resolve()

    assert len(resolved.alignments) == 1
    r_align = resolved.alignments[0]
    assert r_align.tag == "ALIGN-01"
    assert r_align.predefined_type == "HORIZONTAL"
    assert len(r_align.points) == 3
    assert r_align.start_chainage == 100.0
    assert pytest.approx(r_align.total_length, rel=1e-3) == 200.4988
    assert pytest.approx(r_align.end_chainage, rel=1e-3) == 300.4988
    assert r_align.design_speed == 80.0
    assert r_align.layer == "civil/infrastructure/alignment"


def test_civil_road_resolution_and_qto(sample_civil_manifest):
    resolver = SpatialResolver(sample_civil_manifest)
    resolved = resolver.resolve()

    assert len(resolved.roads) == 1
    r_road = resolved.roads[0]
    assert r_road.tag == "ROAD-01"
    assert r_road.road_width == 10.0
    assert r_road.corridor_length == 150.0
    assert r_road.lanes_count == 4
    assert r_road.surface_area == 1500.0
    assert pytest.approx(r_road.asphalt_volume) == 1500.0 * 0.05
    assert pytest.approx(r_road.base_volume) == 1500.0 * 0.20
    assert pytest.approx(r_road.subbase_volume) == 1500.0 * 0.25
    assert r_road.layer == "civil/infrastructure/roads"

    project_qto = calculate_qto(resolved)
    assert project_qto.total_road_pavement_area == 1500.0
    assert project_qto.total_asphalt_volume == 75.0
    assert project_qto.total_road_base_volume == 300.0
    assert project_qto.total_road_subbase_volume == 375.0


def test_civil_bridge_resolution_and_qto(sample_civil_manifest):
    resolver = SpatialResolver(sample_civil_manifest)
    resolved = resolver.resolve()

    assert len(resolved.bridges) == 2
    b1 = resolved.bridges[0]
    assert b1.tag == "BRIDGE-01"
    assert b1.span_length == 40.0
    assert b1.deck_width == 12.0
    assert b1.deck_area == 480.0
    assert pytest.approx(b1.deck_concrete_volume) == 480.0 * 0.40

    single_pier_vol = math.pi * (0.6 ** 2) * 8.0
    expected_pier_vol = single_pier_vol * 3
    assert pytest.approx(b1.pier_concrete_volume, rel=1e-3) == expected_pier_vol
    assert len(b1.pier_positions) == 3

    b2 = resolved.bridges[1]
    assert b2.tag == "BRIDGE-02"
    assert pytest.approx(b2.pier_concrete_volume) == 10.0

    project_qto = calculate_qto(resolved)
    assert project_qto.total_bridge_deck_concrete > 0
    assert project_qto.total_bridge_pier_concrete > 0


def test_civil_cost_estimation(sample_civil_manifest):
    resolver = SpatialResolver(sample_civil_manifest)
    resolved = resolver.resolve()
    project_qto = calculate_qto(resolved)

    catalog = PriceCatalog(
        currency="THB",
        items={
            "ROAD-ASPHALT-PAVEMENT": PriceItem(
                name="Asphalt Road Pavement",
                unit="m2",
                material_cost=450.0,
                labor_cost=150.0,
            ),
            "ROAD-BASE-CRUSHED-ROCK": PriceItem(
                name="Crushed Rock Base Course",
                unit="m3",
                material_cost=600.0,
                labor_cost=200.0,
            ),
            "BRIDGE-RC-DECK": PriceItem(
                name="Bridge RC Deck Slab",
                unit="m3",
                material_cost=3200.0,
                labor_cost=1200.0,
            ),
            "BRIDGE-RC-PIER": PriceItem(
                name="Bridge RC Pier Column",
                unit="m3",
                material_cost=3500.0,
                labor_cost=1500.0,
            ),
        },
    )

    cost_result = estimate_cost(project_qto, catalog)
    assert cost_result.grand_total > 0
    mapped_codes = {line.code for line in cost_result.line_items}
    assert "ROAD-ASPHALT-PAVEMENT" in mapped_codes
    assert "ROAD-BASE-CRUSHED-ROCK" in mapped_codes
    assert "BRIDGE-RC-DECK" in mapped_codes
    assert "BRIDGE-RC-PIER" in mapped_codes


def test_civil_ifc_export(sample_civil_manifest):
    resolver = SpatialResolver(sample_civil_manifest)
    resolved = resolver.resolve()

    # Step string compiler export
    serializer = StepSerializer()
    ifc_content = serializer.serialize(resolved)
    assert "IFCALIGNMENT" in ifc_content
    assert "IFCROAD" in ifc_content
    assert "IFCBRIDGE" in ifc_content

    # IfcOpenShell API export
    ifc_path = compile_to_ifc(sample_civil_manifest, output_path="dist/test_civil.ifc")
    step_str = ifc_path.read_text(encoding="utf-8")
    assert ("IFCALIGNMENT" in step_str) or ("IFCBUILDINGELEMENTPROXY" in step_str)


def test_civil_viewer_generation(sample_civil_manifest):
    resolver = SpatialResolver(sample_civil_manifest)
    resolved = resolver.resolve()

    html = generate_viewer_html(resolved)
    assert "IfcAlignment" in html
    assert "IfcRoad" in html
    assert "IfcBridge" in html
    assert "ALIGN-01" in html
    assert "ROAD-01" in html
    assert "BRIDGE-01" in html
