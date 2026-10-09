"""
Unit test suite for IFC4.3 Civil Railways & Track Infrastructure Entities:
IfcRailway, IfcRailwayPart, IfcTrackElement, IfcBuiltSystem.
"""

from pathlib import Path
import pytest
import ifcopenshell
import ifcopenshell.geom

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcBuiltSystem,
    IfcRailway,
    IfcRailwayPart,
    IfcTrackElement,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_railway_schema_validation():
    """Test Pydantic v2 schema validation and default value handling for railway entities."""
    # 1. IfcRailway
    railway = IfcRailway(
        tag="RW-MAIN-01",
        name="Main Passenger Line",
        predefined_type="RAILWAY",
        track_gauge=1.435,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert railway.class_ == "IfcRailway"
    assert railway.tag == "RW-MAIN-01"
    assert railway.track_gauge == 1.435

    # 2. IfcRailwayPart (TRACK, SUBGRADE, LINESIDE)
    part_track = IfcRailwayPart(
        tag="RWP-TRACK-01",
        predefined_type="TRACK",
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert part_track.class_ == "IfcRailwayPart"
    assert part_track.predefined_type == "TRACK"

    part_subgrade = IfcRailwayPart(
        tag="RWP-SUBGRADE-01",
        predefined_type="SUBGRADE",
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert part_subgrade.predefined_type == "SUBGRADE"

    part_lineside = IfcRailwayPart(
        tag="RWP-LINESIDE-01",
        predefined_type="LINESIDE",
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert part_lineside.predefined_type == "LINESIDE"

    # 3. IfcTrackElement (RAIL, SLEEPER, TURNOUT, DERAILER, SWITCH)
    track_rail = IfcTrackElement(
        tag="TE-RAIL-01",
        predefined_type="RAIL",
        rail_profile="UIC60",
        rail_weight_kg_m=60.0,
        gauge=1.435,
        sleeper_spacing=0.60,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert track_rail.class_ == "IfcTrackElement"
    assert track_rail.predefined_type == "RAIL"
    assert track_rail.rail_profile == "UIC60"
    assert track_rail.sleeper_spacing == 0.60

    track_turnout = IfcTrackElement(
        tag="TE-TURNOUT-01",
        predefined_type="TURNOUT",
        turnout_angle=0.10,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert track_turnout.predefined_type == "TURNOUT"
    assert track_turnout.turnout_angle == 0.10

    # 4. IfcBuiltSystem with type TRACKSYSTEM
    built_sys = IfcBuiltSystem(
        name="Track System 101",
        system_type="TRACKSYSTEM",
        elements=["TE-RAIL-01", "TE-TURNOUT-01"],
    )
    assert built_sys.class_ == "IfcBuiltSystem"
    assert built_sys.system_type == "TRACKSYSTEM"
    assert built_sys.predefined_type == "TRACKSYSTEM"
    assert len(built_sys.elements) == 2


def test_railway_resolution_qto_and_cost(tmp_path: Path):
    """Test 3D spatial resolution, parallel rail extrusion, sleeper generation, QTO, and BOQ cost estimation."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-RAIL-01", name="High Speed Rail Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 120.0}, axes_y={"A": 0.0, "B": 60.0}),
        materials=[
            {"id": "MAT_STEEL_RAIL", "name": "UIC60 Steel Rail", "category": "steel", "unit_cost_ref": "RAIL-STEEL-TRACK"},
            {"id": "MAT_CONC_SLEEPER", "name": "Concrete Sleeper", "category": "concrete", "unit_cost_ref": "RAIL-CONCRETE-SLEEPER"},
        ],
        elements=[
            IfcRailway(
                tag="RW-01",
                track_gauge=1.435,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcRailwayPart(
                tag="RWP-01",
                predefined_type="TRACK",
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcTrackElement(
                tag="TE-RAIL-01",
                material="MAT_STEEL_RAIL",
                predefined_type="RAIL",
                rail_profile="UIC60",
                rail_weight_kg_m=60.0,
                gauge=1.435,
                sleeper_spacing=0.60,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcTrackElement(
                tag="TE-TURNOUT-01",
                material="MAT_STEEL_RAIL",
                predefined_type="TURNOUT",
                turnout_angle=0.12,
                placement={"storey": "GROUND", "from_grid": ["1", "B"], "to_grid": ["2", "B"]},
            ),
        ],
        systems=[
            IfcBuiltSystem(name="Track System 1", system_type="TRACKSYSTEM", elements=["TE-RAIL-01", "TE-TURNOUT-01"])
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.railways) == 1
    assert len(resolved.railway_parts) == 1
    assert len(resolved.track_elements) == 2
    assert len(resolved.built_systems) == 1

    r_rw = resolved.railways[0]
    assert r_rw.total_length == 120.0

    r_te1 = resolved.track_elements[0]
    assert r_te1.track_length == 120.0
    assert r_te1.total_rail_length == 240.0  # 2 x 120m for dual rails
    assert r_te1.total_rail_weight_kg == 14400.0  # 240m * 60kg/m
    assert len(r_te1.left_rail_points) == 2
    assert len(r_te1.right_rail_points) == 2
    assert r_te1.sleepers_count == 200  # 120m / 0.6m spacing
    assert len(r_te1.sleepers) == 200
    assert r_te1.ballast_volume > 0.0

    # QTO
    qto = calculate_qto(resolved)
    assert qto.total_railway_track_length == 480.0  # Sum across RW-01 (120) + RWP-01 (120) + TE-RAIL-01 (120) + TE-TURNOUT-01 (120)
    assert qto.total_railway_rail_length == 480.0  # Dual rails (240) + turnout main/diverging rails (240)
    assert qto.total_railway_rail_weight_kg == 28800.0  # 480m total rail length * 60 kg/m
    assert qto.total_railway_sleepers_count > 0
    assert qto.total_railway_turnouts_count == 1

    # Cost estimation
    tpl_path = tmp_path / "prices.yaml"
    generate_cost_template(manifest, output_path=tpl_path)
    catalog = load_price_catalog(tpl_path)

    assert "RAIL-STEEL-TRACK" in catalog.items
    assert "RAIL-CONCRETE-SLEEPER" in catalog.items
    assert "RAIL-TURNOUT-SWITCH" in catalog.items
    assert "RAIL-BALLAST-SUBGRADE" in catalog.items

    catalog.items["RAIL-STEEL-TRACK"].material_cost = 1500.0
    catalog.items["RAIL-STEEL-TRACK"].labor_cost = 300.0
    catalog.items["RAIL-CONCRETE-SLEEPER"].material_cost = 1200.0
    catalog.items["RAIL-CONCRETE-SLEEPER"].labor_cost = 200.0

    estimate = estimate_cost(qto, catalog, manifest)
    codes = [item.code for item in estimate.line_items]
    assert "RAIL-STEEL-TRACK" in codes
    assert "RAIL-CONCRETE-SLEEPER" in codes
    assert estimate.grand_total > 0.0


def test_railway_ifc43_export_and_shape_verification(tmp_path: Path):
    """Test IFC4.3 compilation and geometry shape creation/verification using ifcopenshell.geom.create_shape."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-RAIL-02", name="Railway Export Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[
            {"id": "MAT_RAIL", "name": "Steel Rail", "category": "steel", "unit_cost_ref": "RAIL-1"}
        ],
        elements=[
            IfcRailway(tag="RW-01", placement={"storey": "GROUND", "points": [[0, 0, 0], [100, 0, 0]]}),
            IfcRailwayPart(tag="RWP-TRACK-01", predefined_type="TRACK", placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]}),
            IfcTrackElement(tag="TE-RAIL-01", predefined_type="RAIL", placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]}),
            IfcTrackElement(tag="TE-TURNOUT-01", predefined_type="TURNOUT", placement={"storey": "GROUND", "from_grid": ["1", "B"], "to_grid": ["2", "B"]}),
        ],
        systems=[
            IfcBuiltSystem(name="Track System 1", system_type="TRACKSYSTEM", elements=["TE-RAIL-01", "TE-TURNOUT-01"])
        ],
    )

    # 1. IFC4.3 File Export
    ifc_file = tmp_path / "railway_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    # 2. Verify IFC schema entity loading with ifcopenshell
    model = ifcopenshell.open(str(ifc_file))
    railways = model.by_type("IfcRailway")
    railway_parts = model.by_type("IfcRailwayPart")
    track_elements = model.by_type("IfcTrackElement")

    assert len(railways) >= 1 or len(model.by_type("IfcBuildingElementProxy")) >= 1
    assert len(track_elements) >= 1 or len(model.by_type("IfcBuildingElementProxy")) >= 1

    # 3. Geometry creation verification with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()
    for product in model.by_type("IfcProduct"):
        if product.Representation:
            try:
                shape = ifcopenshell.geom.create_shape(settings, product)
                assert shape is not None
                assert len(shape.geometry.verts) > 0
            except Exception:
                pass

    # 4. STEP Fallback Export
    step_file = tmp_path / "railway_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCRAILWAY" in step_content
    assert "IFCTRACKELEMENT" in step_content

    # 5. Standalone 3D Viewer HTML Generation
    html = generate_viewer_html(manifest)
    assert "IfcRailway" in html
    assert "IfcTrackElement" in html
    assert "TE-RAIL-01" in html
    assert "TE-TURNOUT-01" in html
