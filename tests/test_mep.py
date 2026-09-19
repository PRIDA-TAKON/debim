"""
Unit tests for debim MEP (Mechanical, Electrical & Plumbing) Systems.
Validates schema parsing, spatial resolution, QTO calculation, cost engine,
IFC compilation, and 3D web viewer integration for pipes, fixtures, and electrical components.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.schema import (
    Grids,
    IfcAirTerminal,
    IfcCableCarrierSegment,
    IfcDistributionBoard,
    IfcDuctSegment,
    IfcLightFixture,
    IfcOutlet,
    IfcPipeSegment,
    IfcSanitaryTerminal,
    IfcSwitchingDevice,
    IfcUnitaryEquipment,
    Material,
    PipePlacement,
    PipePoint,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    TerminalDimensions,
    TerminalPlacement,
    IfcWall,
    WallPlacement,
    load_manifest,
)
from debim.resolver import (
    ResolvedAirTerminal,
    ResolvedCableCarrierSegment,
    ResolvedDistributionBoard,
    ResolvedDuctSegment,
    ResolvedLightFixture,
    ResolvedOutlet,
    ResolvedPipeSegment,
    ResolvedSanitaryTerminal,
    ResolvedSwitchingDevice,
    ResolvedUnitaryEquipment,
    resolve_manifest,
)
from debim.qto import calculate_qto
from debim.cost import PriceCatalog, PriceItem, estimate_cost
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html


@pytest.fixture
def sample_mep_manifest() -> ProjectManifest:
    """Fixture providing a project manifest with complete MEP elements."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-MEP-TEST", name="MEP Test Suite"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1_GROUND", name="Level 1 Ground", elevation=0.0, height=3.5),
                Storey(id="L2_SECOND", name="Level 2 Second", elevation=3.5, height=3.0),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0, "3": 8.0},
            axes_y={"A": 0.0, "B": 4.0, "C": 8.0},
        ),
        materials=[
            Material(
                id="PIPE_PPR",
                name="PPR Pipe",
                category="plumbing",
                unit_cost_ref="MAT-PIPE-PPR",
            ),
            Material(
                id="PIPE_PVC",
                name="PVC Pipe",
                category="drainage",
                unit_cost_ref="MAT-PIPE-PVC",
            ),
            Material(
                id="CONDUIT_EMT",
                name="EMT Conduit",
                category="electrical",
                unit_cost_ref="MAT-CONDUIT-EMT",
            ),
            Material(
                id="SAN_WARE",
                name="Sanitary Ware",
                category="sanitary",
                unit_cost_ref="MAT-WC",
            ),
            Material(
                id="ELEC_EQ",
                name="Electrical Equipment",
                category="electrical",
                unit_cost_ref="MAT-CU",
            ),
            Material(
                id="HVAC_EQ",
                name="HVAC Equipment",
                category="hvac",
                unit_cost_ref="MAT-AC-WALL",
            ),
            Material(
                id="DUCT_STEEL",
                name="Galvanized Duct",
                category="hvac",
                unit_cost_ref="MAT-DUCT-GALV",
            ),
        ],
        elements=[
            # 1. Cold water pipe (multi-point path)
            IfcPipeSegment(
                tag="PIPE-CW-01",
                system_type="COLD_WATER",
                material="PIPE_PPR",
                nominal_diameter=0.025,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    path=[
                        PipePoint(grid=("1", "A"), offset_x=0.5, offset_y=0.5, offset_z=0.1),
                        PipePoint(grid=("2", "A"), offset_x=0.0, offset_y=0.5, offset_z=0.1),
                        PipePoint(grid=("2", "B"), offset_x=0.0, offset_y=0.0, offset_z=0.1),
                    ],
                ),
            ),
            # 2. Soil pipe (sloped from WC to external septic)
            IfcPipeSegment(
                tag="PIPE-SOIL-01",
                system_type="SOIL",
                material="PIPE_PVC",
                nominal_diameter=0.100,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    from_grid=("2", "B"),
                    to_grid=("3", "B"),
                    from_offset=(0.5, 0.5, -0.2),
                    to_offset=(1.0, 0.5, -0.2),
                    slope=0.02,
                ),
            ),
            # 3. Vent pipe (vertical)
            IfcPipeSegment(
                tag="PIPE-VENT-01",
                system_type="VENT",
                material="PIPE_PVC",
                nominal_diameter=0.050,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    from_grid=("2", "B"),
                    to_grid=("2", "B"),
                    from_offset=(0.5, 0.5, 0.0),
                    to_offset=(0.5, 0.5, 3.0),
                ),
            ),
            # 4. Electrical Conduit (Lighting Circuit)
            IfcCableCarrierSegment(
                tag="CONDUIT-L1-01",
                system_type="LIGHTING",
                material="CONDUIT_EMT",
                nominal_diameter=0.020,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    from_grid=("1", "A"),
                    to_grid=("2", "B"),
                    from_offset=(0.2, 0.2, 3.2),
                    to_offset=(0.0, 0.0, 3.2),
                ),
            ),
            # Electrical Conduit (Power Circuit)
            IfcCableCarrierSegment(
                tag="CONDUIT-P1-01",
                system_type="POWER",
                material="CONDUIT_EMT",
                nominal_diameter=0.020,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    from_grid=("1", "A"),
                    to_grid=("2", "A"),
                    from_offset=(0.2, 0.2, 0.3),
                    to_offset=(0.0, 0.0, 0.3),
                ),
            ),
            # 5. Sanitary Terminals
            IfcSanitaryTerminal(
                tag="WC-01",
                terminal_type="WATER_CLOSET",
                material="SAN_WARE",
                placement=TerminalPlacement(
                    grid=("2", "B"), storey="L1_GROUND", offset_x=0.5, offset_y=0.8, offset_z=0.0
                ),
                dimensions=TerminalDimensions(width=0.40, depth=0.70, height=0.75),
            ),
            IfcSanitaryTerminal(
                tag="SEPTIC-01",
                terminal_type="SEPTIC_TANK",
                material="SAN_WARE",
                placement=TerminalPlacement(
                    grid=("3", "B"), storey="L1_GROUND", offset_x=1.0, offset_y=0.0, offset_z=-1.0
                ),
                dimensions=TerminalDimensions(width=1.40, depth=1.40, height=1.60),
            ),
            # 6. Distribution Board
            IfcDistributionBoard(
                tag="CU-01",
                board_type="CONSUMER_UNIT",
                material="ELEC_EQ",
                placement=TerminalPlacement(
                    grid=("1", "A"), storey="L1_GROUND", offset_x=0.2, offset_y=0.1, offset_z=1.5
                ),
                dimensions=TerminalDimensions(width=0.40, depth=0.12, height=0.50),
                circuits_count=12,
            ),
            # 7. Light Fixture
            IfcLightFixture(
                tag="LIGHT-01",
                fixture_type="DOWNLIGHT",
                material="ELEC_EQ",
                placement=TerminalPlacement(
                    grid=("2", "B"), storey="L1_GROUND", offset_x=1.0, offset_y=1.0, offset_z=3.0
                ),
                dimensions=TerminalDimensions(width=0.18, depth=0.18, height=0.06),
                wattage=12.0,
            ),
            # 8. Switch & Outlet
            IfcSwitchingDevice(
                tag="SW-01",
                switch_type="ONE_WAY",
                material="ELEC_EQ",
                placement=TerminalPlacement(
                    grid=("1", "A"), storey="L1_GROUND", offset_x=0.5, offset_y=0.1, offset_z=1.2
                ),
                gangs=2,
            ),
            IfcOutlet(
                tag="REC-01",
                outlet_type="DUPLEX_GROUNDED",
                material="ELEC_EQ",
                placement=TerminalPlacement(
                    grid=("2", "B"), storey="L1_GROUND", offset_x=0.1, offset_y=0.1, offset_z=0.3
                ),
            ),
            # 9. HVAC - Refrigerant Pipe
            IfcPipeSegment(
                tag="PIPE-REF-01",
                system_type="REFRIGERANT",
                material="PIPE_PPR",
                nominal_diameter=0.012,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    from_grid=("2", "B"),
                    to_grid=("3", "B"),
                    from_offset=(1.0, 1.0, 2.5),
                    to_offset=(1.0, 1.0, 0.5),
                ),
            ),
            # 10. HVAC - Exhaust Duct
            IfcDuctSegment(
                tag="DUCT-EXH-01",
                system_type="EXHAUST_AIR",
                material="DUCT_STEEL",
                width=0.25,
                height=0.20,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    from_grid=("1", "A"),
                    to_grid=("1", "B"),
                    from_offset=(1.5, 0.5, 2.8),
                    to_offset=(1.5, 0.5, 2.8),
                ),
            ),
            # 11. HVAC - Exhaust Fan
            IfcAirTerminal(
                tag="EXH-FAN-01",
                terminal_type="EXHAUST_FAN_CEILING",
                material="HVAC_EQ",
                placement=TerminalPlacement(
                    grid=("2", "B"), storey="L1_GROUND", offset_x=0.8, offset_y=0.8, offset_z=2.8
                ),
                flow_rate_cfm=120.0,
            ),
            # 12. HVAC - Kitchen Hood
            IfcAirTerminal(
                tag="HOOD-01",
                terminal_type="KITCHEN_HOOD",
                material="HVAC_EQ",
                placement=TerminalPlacement(
                    grid=("1", "A"), storey="L1_GROUND", offset_x=1.5, offset_y=0.5, offset_z=1.8
                ),
                dimensions=TerminalDimensions(width=0.90, depth=0.55, height=0.50),
                flow_rate_cfm=600.0,
            ),
            # 13. HVAC - Air Conditioners (Indoor FCU & Outdoor CDU)
            IfcUnitaryEquipment(
                tag="AC-FCU-01",
                equipment_type="AC_INDOOR_WALL",
                material="HVAC_EQ",
                placement=TerminalPlacement(
                    grid=("2", "B"), storey="L1_GROUND", offset_x=1.0, offset_y=0.2, offset_z=2.5
                ),
                cooling_capacity_btu=18000.0,
            ),
            IfcUnitaryEquipment(
                tag="AC-CDU-01",
                equipment_type="AC_OUTDOOR_CONDENSER",
                material="HVAC_EQ",
                placement=TerminalPlacement(
                    grid=("3", "B"), storey="L1_GROUND", offset_x=1.0, offset_y=0.2, offset_z=0.3
                ),
                cooling_capacity_btu=18000.0,
            ),
        ],
    )


def test_mep_schema_validation(sample_mep_manifest: ProjectManifest):
    """Test that MEP models parse and validate correctly."""
    assert len(sample_mep_manifest.elements) == 17
    pipe = sample_mep_manifest.elements[0]
    assert isinstance(pipe, IfcPipeSegment)
    assert pipe.nominal_diameter == 0.025
    assert pipe.system_type == "COLD_WATER"

    # HVAC elements in schema
    elem_map = {e.tag: e for e in sample_mep_manifest.elements}
    ref_pipe = elem_map.get("PIPE-REF-01")
    assert isinstance(ref_pipe, IfcPipeSegment)
    assert ref_pipe.system_type == "REFRIGERANT"

    duct = elem_map.get("DUCT-EXH-01")
    assert isinstance(duct, IfcDuctSegment)
    assert duct.system_type == "EXHAUST_AIR"
    assert duct.width == 0.25

    air_term = elem_map.get("EXH-FAN-01")
    assert isinstance(air_term, IfcAirTerminal)
    assert air_term.terminal_type == "EXHAUST_FAN_CEILING"

    fcu = elem_map.get("AC-FCU-01")
    assert isinstance(fcu, IfcUnitaryEquipment)
    assert fcu.equipment_type == "AC_INDOOR_WALL"
    assert fcu.cooling_capacity_btu == 18000.0


def test_mep_validation_unknown_storey():
    """Test that referencing an unknown storey raises ValueError."""
    with pytest.raises(ValidationError):
        ProjectManifest(
            project=ProjectInfo(id="FAIL", name="Fail"),
            spatial_structure=SpatialStructure(
                storeys=[Storey(id="L1", name="L1", elevation=0.0, height=3.0)]
            ),
            grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
            materials=[Material(id="M1", name="M1", category="plumbing", unit_cost_ref="REF1")],
            elements=[
                IfcPipeSegment(
                    tag="P-01",
                    system_type="COLD_WATER",
                    material="M1",
                    placement=PipePlacement(storey="UNKNOWN_STOREY", from_grid=("1", "A"), to_grid=("1", "A")),
                )
            ],
        )


def test_mep_spatial_resolution(sample_mep_manifest: ProjectManifest):
    """Test that SpatialResolver correctly computes 3D coordinates and lengths for MEP elements."""
    resolved = resolve_manifest(sample_mep_manifest)

    # Pipes
    assert len(resolved.pipes) == 4
    p_cw = resolved.get_element_by_tag("PIPE-CW-01")
    assert isinstance(p_cw, ResolvedPipeSegment)
    # Path: (0.5, 0.5, 0.1) -> (4.0, 0.5, 0.1) [len 3.5] -> (4.0, 4.0, 0.1) [len 3.5] => total 7.0m
    assert pytest.approx(p_cw.length, abs=0.01) == 7.0
    assert p_cw.fittings_count == 2
    assert p_cw.color == "#0284C7"

    # Soil pipe with slope
    p_soil = resolved.get_element_by_tag("PIPE-SOIL-01")
    assert isinstance(p_soil, ResolvedPipeSegment)
    assert p_soil.nominal_diameter == 0.100
    assert p_soil.slope == 0.02
    assert p_soil.length > 3.0
    # End point Z should be lower than start point due to slope
    assert p_soil.end_point[2] < p_soil.start_point[2]

    # Refrigerant pipe
    p_ref = resolved.get_element_by_tag("PIPE-REF-01")
    assert isinstance(p_ref, ResolvedPipeSegment)
    assert p_ref.system_type == "REFRIGERANT"
    assert p_ref.color == "#06B6D4"

    # Duct segment
    assert len(resolved.ducts) == 1
    duct = resolved.get_element_by_tag("DUCT-EXH-01")
    assert isinstance(duct, ResolvedDuctSegment)
    assert duct.system_type == "EXHAUST_AIR"
    assert duct.width == 0.25
    assert duct.length == pytest.approx(4.0, abs=0.01)

    # Air Terminals (Exhaust fan & Kitchen hood)
    assert len(resolved.air_terminals) == 2
    hood = resolved.get_element_by_tag("HOOD-01")
    assert isinstance(hood, ResolvedAirTerminal)
    assert hood.terminal_type == "KITCHEN_HOOD"
    assert hood.dimensions == (0.90, 0.55, 0.50)

    # Unitary Equipments (AC FCU & CDU)
    assert len(resolved.unitary_equipments) == 2
    fcu = resolved.get_element_by_tag("AC-FCU-01")
    assert isinstance(fcu, ResolvedUnitaryEquipment)
    assert fcu.equipment_type == "AC_INDOOR_WALL"
    assert fcu.cooling_capacity_btu == 18000.0

    # Sanitary Terminals
    assert len(resolved.sanitary_terminals) == 2
    wc = resolved.get_element_by_tag("WC-01")
    assert isinstance(wc, ResolvedSanitaryTerminal)
    assert wc.position == (4.5, 4.8, 0.0)
    assert wc.dimensions == (0.40, 0.70, 0.75)

    # Distribution Board
    cu = resolved.get_element_by_tag("CU-01")
    assert isinstance(cu, ResolvedDistributionBoard)
    assert cu.circuits_count == 12

    # Lights, Switches, Outlets
    assert len(resolved.light_fixtures) == 1
    assert len(resolved.switches) == 1
    assert len(resolved.outlets) == 1


def test_mep_qto_calculations(sample_mep_manifest: ProjectManifest):
    """Test Quantitative Take-Off for MEP elements."""
    resolved = resolve_manifest(sample_mep_manifest)
    qto = calculate_qto(resolved)

    assert qto.total_cold_water_pipe_length == pytest.approx(7.0, abs=0.05)
    assert qto.total_soil_pipe_length > 3.0
    assert qto.total_vent_pipe_length == pytest.approx(3.0, abs=0.01)
    assert qto.total_refrigerant_pipe_length > 4.0
    assert qto.total_conduit_length > 4.0
    assert qto.total_duct_length == pytest.approx(4.0, abs=0.01)
    assert qto.total_pipe_fittings_count >= 5
    assert qto.total_sanitary_terminals_count == 2
    assert qto.total_distribution_boards_count == 1
    assert qto.total_lighting_fixtures_count == 1
    assert qto.total_switches_count == 1
    assert qto.total_outlets_count == 1
    assert qto.total_air_terminals_count == 2
    assert qto.total_unitary_equipment_count == 2


def test_mep_cost_estimation(sample_mep_manifest: ProjectManifest):
    """Test matching QTO with price catalog for MEP items."""
    catalog = PriceCatalog(
        currency="THB",
        items={
            "MAT-PIPE-PPR": PriceItem(
                name="PPR Cold Water Pipe", unit="m", material_cost=100.0, labor_cost=50.0
            ),
            "MAT-PIPE-PVC": PriceItem(
                name="PVC Soil/Waste Pipe", unit="m", material_cost=180.0, labor_cost=70.0
            ),
            "MAT-CONDUIT-EMT": PriceItem(
                name="EMT Conduit", unit="m", material_cost=50.0, labor_cost=30.0
            ),
            "MAT-WC": PriceItem(
                name="Water Closet Set", unit="set", material_cost=3500.0, labor_cost=500.0
            ),
            "MAT-CU": PriceItem(
                name="Consumer Unit", unit="set", material_cost=3000.0, labor_cost=1000.0
            ),
            "MAT-AC-WALL": PriceItem(
                name="Wall Mounted AC 18000 BTU", unit="set", material_cost=18000.0, labor_cost=2500.0
            ),
            "MAT-DUCT-GALV": PriceItem(
                name="Galvanized Steel Duct", unit="m", material_cost=450.0, labor_cost=150.0
            ),
        },
    )

    resolved = resolve_manifest(sample_mep_manifest)
    qto = calculate_qto(resolved)
    estimate = estimate_cost(qto, catalog, sample_mep_manifest)

    assert estimate.grand_total > 25000.0
    # Check that line items include PPR pipe, PVC, conduit, WC, CU, AC, and Duct
    codes = {item.code for item in estimate.line_items}
    assert "MAT-PIPE-PPR" in codes
    assert "MAT-PIPE-PVC" in codes
    assert "MAT-CONDUIT-EMT" in codes
    assert "MAT-WC" in codes
    assert "MAT-CU" in codes
    assert "MAT-AC-WALL" in codes
    assert "MAT-DUCT-GALV" in codes


def test_mep_ifc_compilation(sample_mep_manifest: ProjectManifest, tmp_path: Path):
    """Test compiling MEP elements to standard IFC4 STEP file."""
    ifc_path = tmp_path / "mep_test.ifc"
    out_path = compile_to_ifc(sample_mep_manifest, ifc_path, force_fallback=True)

    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "IFCPIPESEGMENT" in content
    assert "IFCCABLECARRIERSEGMENT" in content
    assert "IFCSANITARYTERMINAL" in content
    assert "IFCDISTRIBUTIONBOARD" in content
    assert "IFCLIGHTFIXTURE" in content
    assert "IFCSWITCHINGDEVICE" in content
    assert "IFCOUTLET" in content
    assert "IFCDUCTSEGMENT" in content
    assert "IFCAIRTERMINAL" in content
    assert "IFCUNITARYEQUIPMENT" in content


def test_mep_viewer_html_generation(sample_mep_manifest: ProjectManifest):
    """Test generating 3D web viewer with MEP layers and inspector metadata."""
    html = generate_viewer_html(sample_mep_manifest)
    assert "mep_cold_water" in html
    assert "mep_drainage" in html
    assert "mep_fixtures" in html
    assert "mep_electrical" in html
    assert "mep_hvac" in html
    assert "PIPE-CW-01" in html
    assert "CU-01" in html
    assert "WC-01" in html
    assert "DUCT-EXH-01" in html
    assert "HOOD-01" in html
    assert "AC-FCU-01" in html
    assert "AC-CDU-01" in html


# --- Wall-Hosted Tests (from Jules) ---
@pytest.fixture
def base_mep_manifest():
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-MEP-01", name="MEP Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Level 1", elevation=0.0, height=3.5),
                Storey(id="L2", name="Level 2", elevation=3.5, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0},
            axes_y={"A": 0.0, "B": 4.0},
        ),
        materials=[
            Material(
                id="MAT_CONC",
                name="Concrete",
                category="Concrete",
                unit_cost_ref="REF_CONC",
            ),
            Material(
                id="MAT_CERAMIC",
                name="Ceramic",
                category="Sanitary",
                unit_cost_ref="REF_SAN",
            ),
        ],
        elements=[
            # Wall W-HORIZ along Y=0 from X=0 to X=6 (length = 6.0m, thickness = 0.20m)
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W-HORIZ",
                    "material": "MAT_CONC",
                    "thickness": 0.20,
                    "height": 3.0,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                }
            ),
            # Wall W-VERT along X=0 from Y=0 to Y=4 (length = 4.0m, thickness = 0.15m)
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W-VERT",
                    "material": "MAT_CONC",
                    "thickness": 0.15,
                    "height": 3.0,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("1", "B"), storey="L1"),
                }
            ),
        ],
    )


def test_terminal_placement_schema_validation():
    # Neither grid nor wall provided -> raise ValueError
    with pytest.raises(ValidationError) as exc:
        TerminalPlacement()
    assert "Either grid or wall must be provided" in str(exc.value)

    # Valid grid placement
    p_grid = TerminalPlacement(grid=("1", "A"), storey="L1", offset_z=0.5)
    assert p_grid.grid == ("1", "A")

    # Valid wall placement
    p_wall = TerminalPlacement(wall="W-HORIZ", distance=2.0, side="INTERIOR", standoff=0.02)
    assert p_wall.wall == "W-HORIZ"
    assert p_wall.distance == 2.0
    assert p_wall.side == "INTERIOR"
    assert p_wall.standoff == 0.02


def test_wc_flush_against_horizontal_wall(base_mep_manifest):
    """
    Wall W-HORIZ: P1=(0,0,0), P2=(6,0,0), thickness T=0.20m.
    Tangent u = (1, 0), Normal n = (-0, 1) = (0, 1).
    WC fixture: width=0.40, depth=0.70, height=0.40.
    Placement: wall="W-HORIZ", distance=2.0m, side="INTERIOR", standoff=0.0, offset_z=0.0.
    Expected base point: P_base = (2.0, 0.0, 0.0).
    Expected offset = T/2 + standoff + depth/2 = 0.10 + 0.0 + 0.35 = 0.45.
    Expected position P = P_base + offset * n = (2.0, 0.45, 0.0).
    Auto rotation: n = (0, 1) -> angle = 90.0 degrees.
    Storey: inherited from wall -> "L1" (elevation 0.0).
    """
    wc = IfcSanitaryTerminal(
        **{
            "class": "IfcSanitaryTerminal",
            "tag": "WC-01",
            "material": "MAT_CERAMIC",
            "width": 0.40,
            "depth": 0.70,
            "height": 0.40,
            "placement": TerminalPlacement(
                wall="W-HORIZ",
                distance=2.0,
                side="INTERIOR",
                standoff=0.0,
                offset_z=0.0,
            ),
        }
    )
    base_mep_manifest.elements.append(wc)
    resolved = resolve_manifest(base_mep_manifest)

    r_wc = resolved.get_element_by_tag("WC-01")
    assert r_wc is not None
    assert r_wc.position[0] == pytest.approx(2.0)
    assert r_wc.position[1] == pytest.approx(0.45)
    assert r_wc.position[2] == pytest.approx(0.0)
    assert r_wc.rotation_angle == pytest.approx(90.0)


def test_basin_flush_against_vertical_wall(base_mep_manifest):
    """
    Wall W-VERT: P1=(0,0,0), P2=(0,4,0), thickness T=0.15m.
    Tangent u = (0, 1), Normal n = (-1, 0).
    Basin fixture: width=0.50, depth=0.45, height=0.85.
    Placement: wall="W-VERT", distance=1.5m, side="INTERIOR", standoff=0.0, offset_z=0.85.
    Expected base point: P_base = (0.0, 1.5, 0.0).
    Expected offset = T/2 + standoff + depth/2 = 0.075 + 0.0 + 0.225 = 0.30.
    Expected position P = P_base + offset * n = (0.0 - 0.30, 1.5, 0.85) = (-0.30, 1.5, 0.85).
    Auto rotation: n = (-1, 0) -> angle = 180.0 degrees.
    """
    basin = IfcSanitaryTerminal(
        **{
            "class": "IfcSanitaryTerminal",
            "tag": "BASIN-01",
            "material": "MAT_CERAMIC",
            "width": 0.50,
            "depth": 0.45,
            "height": 0.85,
            "placement": TerminalPlacement(
                wall="W-VERT",
                distance=1.5,
                side="INTERIOR",
                standoff=0.0,
                offset_z=0.85,
            ),
        }
    )
    base_mep_manifest.elements.append(basin)
    resolved = resolve_manifest(base_mep_manifest)

    r_basin = resolved.get_element_by_tag("BASIN-01")
    assert r_basin is not None
    assert r_basin.position[0] == pytest.approx(-0.30)
    assert r_basin.position[1] == pytest.approx(1.5)
    assert r_basin.position[2] == pytest.approx(0.85)
    assert r_basin.rotation_angle == pytest.approx(180.0)


def test_embedded_switch_center_side(base_mep_manifest):
    """
    Wall W-HORIZ: P1=(0,0,0), P2=(6,0,0), T=0.20m.
    Switch fixture: side="CENTER", offset_z=1.20m.
    Offset distance = 0.0.
    Expected position = (1.0, 0.0, 1.20).
    """
    switch = IfcSwitchingDevice(
        **{
            "class": "IfcSwitchingDevice",
            "tag": "SW-01",
            "width": 0.08,
            "depth": 0.04,
            "height": 0.08,
            "placement": TerminalPlacement(
                wall="W-HORIZ",
                distance=1.0,
                side="CENTER",
                offset_z=1.20,
            ),
        }
    )
    base_mep_manifest.elements.append(switch)
    resolved = resolve_manifest(base_mep_manifest)

    r_sw = resolved.get_element_by_tag("SW-01")
    assert r_sw is not None
    assert r_sw.position[0] == pytest.approx(1.0)
    assert r_sw.position[1] == pytest.approx(0.0)
    assert r_sw.position[2] == pytest.approx(1.20)
    assert r_sw.rotation_angle == pytest.approx(90.0)


def test_exterior_side_and_manual_rotation(base_mep_manifest):
    """
    Wall W-HORIZ: P1=(0,0,0), P2=(6,0,0), T=0.20m.
    Fixture: side="EXTERIOR", standoff=0.05m, depth=0.40m, distance=3.0m.
    Offset distance = -(T/2 + standoff + depth/2) = -(0.10 + 0.05 + 0.20) = -0.35m.
    Expected position = (3.0, -0.35, 1.50).
    Manual rotation override: 45.0.
    """
    outlet = IfcOutlet(
        **{
            "class": "IfcOutlet",
            "tag": "OUTLET-EXT",
            "width": 0.10,
            "depth": 0.40,
            "height": 0.10,
            "placement": TerminalPlacement(
                wall="W-HORIZ",
                distance=3.0,
                side="EXTERIOR",
                standoff=0.05,
                offset_z=1.50,
                rotation=45.0,
            ),
        }
    )
    base_mep_manifest.elements.append(outlet)
    resolved = resolve_manifest(base_mep_manifest)

    r_out = resolved.get_element_by_tag("OUTLET-EXT")
    assert r_out is not None
    assert r_out.position[0] == pytest.approx(3.0)
    assert r_out.position[1] == pytest.approx(-0.35)
    assert r_out.position[2] == pytest.approx(1.50)
    assert r_out.rotation_angle == pytest.approx(45.0)


def test_unknown_wall_raises_error(base_mep_manifest):
    term = IfcAirTerminal(
        **{
            "class": "IfcAirTerminal",
            "tag": "AIR-01",
            "placement": TerminalPlacement(
                wall="WALL-NONEXISTENT",
                distance=1.0,
            ),
        }
    )
    base_mep_manifest.elements.append(term)
    with pytest.raises(ValueError) as exc:
        resolve_manifest(base_mep_manifest)
    assert "Hosting wall 'WALL-NONEXISTENT' not found" in str(exc.value)


def test_grid_based_backward_compatibility(base_mep_manifest):
    board = IfcDistributionBoard(
        **{
            "class": "IfcDistributionBoard",
            "tag": "DB-01",
            "placement": TerminalPlacement(
                grid=("2", "B"),
                storey="L2",
                offset_x=-0.5,
                offset_y=-0.5,
                offset_z=1.5,
                rotation=180.0,
            ),
        }
    )
    base_mep_manifest.elements.append(board)
    resolved = resolve_manifest(base_mep_manifest)

    r_db = resolved.get_element_by_tag("DB-01")
    assert r_db is not None
    assert r_db.position[0] == pytest.approx(6.0 - 0.5)
    assert r_db.position[1] == pytest.approx(4.0 - 0.5)
    assert r_db.position[2] == pytest.approx(3.5 + 1.5)
    assert r_db.rotation_angle == pytest.approx(180.0)
