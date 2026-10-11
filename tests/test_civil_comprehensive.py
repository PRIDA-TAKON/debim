"""
Comprehensive test suite for debim Civil Infrastructure & Linear Assets Engine.
Tests multi-kilometre highway alignment, bridge pier/deck QTO, earthworks cut/fill,
railway track elements, TIN terrain meshes, spatial decomposition, and dual IFC compilation.
"""

from pathlib import Path
import tempfile
import pytest

from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    SpatialStructure,
    Storey,
    Grids,
    Units,
    Material,
    IfcAlignment,
    IfcRoad,
    IfcBridge,
    IfcRailway,
    IfcTrackElement,
    IfcMarineFacility,
    IfcGeographicElement,
    IfcTriangulatedFaceSet,
    IfcFacilityPart,
    IfcEarthworksCut,
    IfcEarthworksFill,
    IfcRetainingWall,
    AlignmentHorizontalSegment,
    AlignmentVerticalSegment,
    AlignmentPlacement,
    RoadPlacement,
    BridgePlacement,
    FacilityPlacement,
    EarthworksPlacement,
    RetainingWallPlacement,
    RetainingWallReinforcement,
    ProxyPlacement,
)
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.cost import generate_cost_template, estimate_cost, load_price_catalog
from debim.compiler import compile_to_ifc, StepSerializer
from debim.viewer import generate_viewer_html


def build_comprehensive_civil_manifest() -> ProjectManifest:
    """Construct a comprehensive multi-kilometre civil infrastructure manifest."""
    return ProjectManifest(
        schema="IFC4.3-Civil",
        project=ProjectInfo(id="PRJ-CIVIL-COMP", name="Comprehensive Highway & Railway Corridor"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="S0", name="Ground Station", elevation=0.0, height=5.0),
                Storey(id="S1", name="Elevated Corridor", elevation=10.0, height=8.0),
            ]
        ),
        grids=Grids(axes_x={"GX1": 0.0, "GX2": 2500.0}, axes_y={"GY1": 0.0, "GY2": 100.0}),
        materials=[
            Material(id="MAT_CONC", name="Concrete 280 ksc", category="concrete", unit_cost_ref="MAT-CONC-01")
        ],
        elements=[
            # 1. Multi-kilometre Highway Alignment (2.5 km)
            IfcAlignment(
                tag="ALIGN-HWY-01",
                predefined_type="USERDEFINED",
                horizontal_segments=[
                    AlignmentHorizontalSegment(segment_type="LINE", start_point=(0.0, 0.0), length=1000.0, start_direction=0.0),
                    AlignmentHorizontalSegment(segment_type="CLOTHOID", start_point=(1000.0, 0.0), length=500.0, start_direction=0.0, radius_start=0.0, radius_end=800.0),
                    AlignmentHorizontalSegment(segment_type="ARC", start_point=(1500.0, 0.0), length=1000.0, start_direction=0.26, radius_start=800.0, radius_end=800.0),
                ],
                vertical_segments=[
                    AlignmentVerticalSegment(segment_type="LINE", start_station=0.0, length=1000.0, start_elevation=0.0, start_gradient=0.01),
                    AlignmentVerticalSegment(segment_type="PARABOLA", start_station=1000.0, length=500.0, start_elevation=10.0, start_gradient=0.01, end_gradient=-0.01),
                    AlignmentVerticalSegment(segment_type="LINE", start_station=1500.0, length=1000.0, start_elevation=10.0, start_gradient=-0.01),
                ],
                placement=AlignmentPlacement(storey="S0"),
            ),
            # 2. Highway Road Corridor (2.5 km, 4-lane, 14m width)
            IfcRoad(
                tag="ROAD-HWY-4L",
                predefined_type="CARRIAGEWAY",
                corridor_length=2500.0,
                road_width=14.0,
                pavement_surface_thickness=0.10,
                pavement_base_thickness=0.25,
                pavement_subbase_thickness=0.35,
                lanes_count=4,
                placement=RoadPlacement(storey="S0", alignment="ALIGN-HWY-01"),
            ),
            # 3. Multi-span Viaduct / Bridge (500m span, 10 piers)
            IfcBridge(
                tag="BRIDGE-VIADUCT-01",
                predefined_type="GIRDER",
                span_length=500.0,
                deck_width=14.0,
                deck_thickness=0.80,
                pier_count=10,
                pier_shape="CYLINDRICAL",
                pier_diameter=2.0,
                placement=BridgePlacement(storey="S1", offset_z=10.0),
            ),
            # 4. Railway Line & Track Elements
            IfcRailway(
                tag="RAIL-MAIN-LINE",
                predefined_type="RAILWAY",
                track_length=1800.0,
                track_gauge=1.435,
                placement=RoadPlacement(storey="S0"),
            ),
            IfcTrackElement(
                tag="TRACK-RAIL-LEFT-01",
                predefined_type="RAIL",
                length=1800.0,
                placement=ProxyPlacement(storey="S0"),
            ),
            IfcTrackElement(
                tag="TRACK-RAIL-RIGHT-01",
                predefined_type="RAIL",
                length=1800.0,
                placement=ProxyPlacement(storey="S0"),
            ),
            # 5. Marine Berth Quay Facility
            IfcMarineFacility(
                tag="BERTH-QUAY-01",
                predefined_type="QUAY",
                length=200.0,
                width=30.0,
                depth=1.5,
                placement=EarthworksPlacement(storey="S0"),
            ),
            # 6. Earthworks Cut & Fill Excavations
            IfcEarthworksCut(
                tag="CUT-PIT-01",
                predefined_type="CUT",
                width=20.0,
                length=100.0,
                depth=4.0,
                placement=EarthworksPlacement(storey="S0", offset_z=-4.0),
            ),
            IfcEarthworksFill(
                tag="FILL-EMBANKMENT-01",
                predefined_type="EMBANKMENT",
                width=18.0,
                length=150.0,
                depth=3.0,
                compaction_ratio=0.95,
                placement=EarthworksPlacement(storey="S0", offset_z=0.0),
            ),
            # 7. Retaining Wall
            IfcRetainingWall(
                tag="RW-HIGHWAY-01",
                predefined_type="CANTILEVER_WALL",
                material="MAT_CONC",
                length=80.0,
                stem_height=4.5,
                stem_thickness=0.40,
                footing_base_width=2.5,
                footing_thickness=0.50,
                placement=RetainingWallPlacement(from_grid=("GX1", "GY1"), to_grid=("GX1", "GY2"), storey="S0"),
                reinforcement=RetainingWallReinforcement(stem_main="DB20 @ 0.15m", stem_distribution="DB12 @ 0.20m"),
            ),
            # 8. TIN Terrain Mesh (IfcTriangulatedFaceSet / IfcGeographicElement)
            IfcGeographicElement(
                tag="TIN-TERRAIN-01",
                predefined_type="TERRAIN",
                tin_mesh=IfcTriangulatedFaceSet(
                    coordinates=[
                        [0.0, 0.0, 0.0], [100.0, 0.0, 2.0], [100.0, 100.0, 5.0],
                        [0.0, 100.0, 1.0], [50.0, 50.0, 3.5],
                    ],
                    coord_index=[
                        [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4]
                    ],
                ),
                placement=EarthworksPlacement(storey="S0"),
            ),
            # 9. Spatial Facility Part (Tactical Segment)
            IfcFacilityPart(
                tag="PART-KM1-KM2",
                predefined_type="ROADWAY",
                facility="ROAD-HWY-4L",
                placement=FacilityPlacement(storey="S0"),
            ),
        ],
    )


def test_civil_comprehensive_spatial_resolution():
    """Verify spatial resolution of multi-kilometre highway, bridge, railway, and terrain elements."""
    manifest = build_comprehensive_civil_manifest()
    resolved = resolve_manifest(manifest)

    # 1. Alignment 3D space-curve discretization
    assert len(resolved.alignments) == 1
    align = resolved.alignments[0]
    assert align.total_length == pytest.approx(2500.0, abs=1.0)
    assert len(align.points_3d) > 20

    # 2. Road Carriageway
    assert len(resolved.roads) == 1
    road = resolved.roads[0]
    assert road.corridor_length == 2500.0
    assert road.surface_area == pytest.approx(2500.0 * 14.0, rel=1e-3)
    assert road.asphalt_volume == pytest.approx(2500.0 * 14.0 * 0.10, rel=1e-3)

    # 3. Bridge Viaduct
    assert len(resolved.bridges) == 1
    bridge = resolved.bridges[0]
    assert bridge.span_length == 500.0
    assert bridge.pier_count == 10
    assert len(bridge.pier_positions) == 10
    assert bridge.deck_concrete_volume == pytest.approx(500.0 * 14.0 * 0.80, rel=1e-3)
    assert bridge.total_concrete_volume > bridge.deck_concrete_volume

    # 4. Railways & Track Elements
    assert len(resolved.railways) == 1
    rw = resolved.railways[0]
    assert rw.length == 1800.0

    assert len(resolved.track_elements) == 2

    # 5. Marine Facility
    assert len(resolved.marine_facilities) == 1
    mf = resolved.marine_facilities[0]
    assert (mf.length * mf.width * mf.depth) == pytest.approx(200.0 * 30.0 * 1.5, rel=1e-3)

    # 6. Earthworks Cut & Fill
    assert len(resolved.earthworks_cuts) == 1
    cut = resolved.earthworks_cuts[0]
    assert cut.cut_volume > 0.0

    assert len(resolved.earthworks_fills) == 1
    fill = resolved.earthworks_fills[0]
    assert fill.compacted_volume > 0.0

    # 7. Triangulated Face Set
    assert len(resolved.geographic_elements) == 1
    tin = resolved.geographic_elements[0]
    assert len(tin.triangulated_mesh.coord_index) == 4


def test_civil_comprehensive_qto_and_cost():
    """Verify Quantity Take-off and Cost Estimate generation for civil infrastructure."""
    manifest = build_comprehensive_civil_manifest()
    qto = calculate_qto(manifest)

    # Alignment and road QTO totals
    assert qto.total_alignment_length == pytest.approx(2500.0, abs=1.0)
    assert qto.total_road_surface_area == pytest.approx(35000.0, rel=1e-3)
    assert qto.total_road_asphalt_volume == pytest.approx(3500.0, rel=1e-3)

    # Bridge concrete and formwork QTO
    assert qto.total_bridge_concrete_volume > 5600.0
    assert qto.total_bridge_formwork_area > 0.0

    # Marine & Earthworks QTO
    assert qto.total_cut_volume > 0.0
    assert qto.total_compacted_fill_volume > 0.0

    # Cost Template & Estimate
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmpl_path = Path(tmp_dir) / "civil_prices.yaml"
        generate_cost_template(manifest, output_path=tmpl_path, format="yaml")
        assert tmpl_path.exists()

        catalog = load_price_catalog(tmpl_path)
        assert "ROAD-ASPHALT-PAVEMENT" in catalog.items
        assert "BRIDGE-RC-DECK" in catalog.items

        # Populate non-zero costs and estimate
        for item in catalog.items.values():
            item.material_cost = 100.0
            item.labor_cost = 50.0

        estimate = estimate_cost(qto, catalog, manifest=manifest)
        assert estimate.grand_total > 0.0


def test_civil_comprehensive_dual_compilation_and_retention():
    """Verify 100% element retention across pure Python and IfcOpenShell compilers."""
    manifest = build_comprehensive_civil_manifest()
    resolved = resolve_manifest(manifest)

    expected_element_count = len(manifest.elements)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Fallback Pure Python STEP Serializer
        fallback_ifc = Path(tmp_dir) / "model_fallback.ifc"
        compile_to_ifc(resolved, output_path=fallback_ifc, force_fallback=True)
        assert fallback_ifc.exists()

        fallback_content = fallback_ifc.read_text(encoding="utf-8")
        assert "IFC4" in fallback_content
        assert "IFCALIGNMENT" in fallback_content
        assert "IFCROAD" in fallback_content
        assert "IFCBRIDGE" in fallback_content
        assert "IFCRAILWAY" in fallback_content
        assert "IFCTRACKELEMENT" in fallback_content

        # 2. IfcOpenShell Compiler
        ifcopenshell_ifc = Path(tmp_dir) / "model_ifcopenshell.ifc"
        compile_to_ifc(resolved, output_path=ifcopenshell_ifc, force_fallback=False)
        assert ifcopenshell_ifc.exists()

        # 3. Read back compiled IFC with IfcOpenShell to verify 100% element retention
        import ifcopenshell
        model = ifcopenshell.open(str(ifcopenshell_ifc))

        retained_elements = model.by_type("IfcProduct")

        assert len(retained_elements) >= expected_element_count


def test_civil_comprehensive_viewer_html():
    """Verify 3D Web Viewer HTML generation with civil layer hierarchy."""
    manifest = build_comprehensive_civil_manifest()
    html = generate_viewer_html(manifest)

    assert "IfcAlignment" in html
    assert "IfcRoad" in html
    assert "IfcBridge" in html
    assert "IfcRailway" in html
    assert "IfcTrackElement" in html
    assert "IfcMarineFacility" in html
    assert "IfcGeographicElement" in html
    assert "civil/infrastructure/roads" in html
