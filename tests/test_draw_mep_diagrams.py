"""
Unit tests for MEP Electrical Single Line Diagram and Sanitation Riser Diagram drawing engine in debim.
Tests data extraction, 2D vector schematic SVG generation, and standard A3 sheet layout rendering (EE-101 & SN-101).
"""

from pathlib import Path
import pytest

from debim.draw import (
    CircuitScheduleItem,
    ElectricalSLDData,
    SanitationRiserData,
    SheetConfig,
    SheetRenderer,
    WasteRiserItem,
    WaterSupplyRiserItem,
    extract_electrical_diagram_data,
    extract_sanitation_diagram_data,
    render_electrical_sheet_svg,
    render_electrical_sld_svg,
    render_sanitation_riser_svg,
    render_sanitation_sheet_svg,
    render_sheet,
)
from debim.schema import (
    Grids,
    IfcDistributionBoard,
    IfcLightFixture,
    IfcOutlet,
    IfcPipeSegment,
    IfcSanitaryTerminal,
    IfcUnitaryEquipment,
    Material,
    PipePlacement,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    TerminalDimensions,
    TerminalPlacement,
)


@pytest.fixture
def mep_manifest() -> ProjectManifest:
    """Fixture providing a project manifest with MEP elements."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-MEP-DRAW", name="MEP Drawing Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1_GROUND", name="Level 1 Ground", elevation=0.0, height=3.5),
                Storey(id="L2_SECOND", name="Level 2 Second", elevation=3.5, height=3.2),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[
            Material(id="ELEC_MAT", name="Electrical Material", category="electrical", unit_cost_ref="MAT-ELEC"),
            Material(id="PLUMB_MAT", name="Plumbing Material", category="plumbing", unit_cost_ref="MAT-PLUMB"),
        ],
        elements=[
            IfcDistributionBoard(
                tag="CU-MAIN",
                board_type="CONSUMER_UNIT",
                material="ELEC_MAT",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1_GROUND", offset_z=1.5),
            ),
            IfcLightFixture(
                tag="LIGHT-L1-01",
                fixture_type="DOWNLIGHT",
                material="ELEC_MAT",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1_GROUND", offset_z=3.0),
            ),
            IfcOutlet(
                tag="REC-L1-01",
                outlet_type="DUPLEX_GROUNDED",
                material="ELEC_MAT",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1_GROUND", offset_z=0.3),
            ),
            IfcUnitaryEquipment(
                tag="AC-01",
                equipment_type="AC_INDOOR_WALL",
                cooling_capacity_btu=18000.0,
                material="ELEC_MAT",
                placement=TerminalPlacement(grid=("2", "B"), storey="L1_GROUND", offset_z=2.5),
            ),
            IfcSanitaryTerminal(
                tag="WC-01",
                terminal_type="WATER_CLOSET",
                material="PLUMB_MAT",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1_GROUND", offset_z=0.0),
                dimensions=TerminalDimensions(width=0.4, depth=0.7, height=0.75),
            ),
            IfcSanitaryTerminal(
                tag="SEPTIC-01",
                terminal_type="SEPTIC_TANK",
                material="PLUMB_MAT",
                placement=TerminalPlacement(grid=("2", "B"), storey="L1_GROUND", offset_z=-1.0),
                dimensions=TerminalDimensions(width=1.4, depth=1.4, height=1.6),
            ),
            IfcPipeSegment(
                tag="PIPE-CW-01",
                system_type="COLD_WATER",
                material="PLUMB_MAT",
                nominal_diameter=0.02,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    from_grid=("1", "A"),
                    to_grid=("2", "A"),
                ),
            ),
            IfcPipeSegment(
                tag="PIPE-SOIL-01",
                system_type="SOIL",
                material="PLUMB_MAT",
                nominal_diameter=0.10,
                placement=PipePlacement(
                    storey="L1_GROUND",
                    from_grid=("1", "A"),
                    to_grid=("2", "B"),
                ),
            ),
        ],
    )


def test_extract_electrical_diagram_data(mep_manifest: ProjectManifest):
    """Test extracting electrical SLD parameters and branch load schedule."""
    sld_data = extract_electrical_diagram_data(mep_manifest)

    assert isinstance(sld_data, ElectricalSLDData)
    assert sld_data.board_tag == "CU-MAIN"
    assert "PEA" in sld_data.incoming_source
    assert "Main MCB" in sld_data.main_breaker
    assert "Ground" in sld_data.grounding_spec

    # Check circuits
    assert len(sld_data.circuits) >= 5
    descriptions = [c.description for c in sld_data.circuits]
    assert any("Lighting" in d for d in descriptions)
    assert any("Receptacle" in d or "Outlet" in d for d in descriptions)
    assert any("Air Conditioner" in d for d in descriptions)
    assert any("Water Heater" in d for d in descriptions)
    assert any("SPARE" in d for d in descriptions)


def test_extract_sanitation_diagram_data(mep_manifest: ProjectManifest):
    """Test extracting cold water supply and soil/waste/vent riser data."""
    riser_data = extract_sanitation_diagram_data(mep_manifest)

    assert isinstance(riser_data, SanitationRiserData)
    assert "PEA Water Meter" in riser_data.cold_water.main_meter
    assert "Water Tank" in riser_data.cold_water.water_tank
    assert "Booster Pump" in riser_data.cold_water.pump_spec
    assert "PPR" in riser_data.cold_water.riser_pipe_spec

    assert "Soil Stack" in riser_data.waste_system.soil_stack_spec
    assert "Waste Stack" in riser_data.waste_system.waste_stack_spec
    assert "Vent Stack" in riser_data.waste_system.vent_stack_spec
    assert "Septic Tank" in riser_data.waste_system.septic_tank_spec
    assert "Grease Trap" in riser_data.waste_system.grease_trap_spec
    assert "Storm Drain" in riser_data.waste_system.drain_outflow_spec


def test_render_electrical_sld_svg(mep_manifest: ProjectManifest):
    """Test rendering 2D vector Electrical Single Line Diagram SVG element."""
    sld_data = extract_electrical_diagram_data(mep_manifest)
    svg_content = render_electrical_sld_svg(sld_data, box_width_mm=330.0, box_height_mm=190.0)

    assert '<g id="electrical-sld-diagram"' in svg_content
    assert "INCOMING SUPPLY" in svg_content
    assert "kWh" in svg_content
    assert "MAIN" in svg_content
    assert "BUS BAR" in svg_content
    assert "PANEL BOARD LOAD SCHEDULE" in svg_content
    assert "TOTAL CONNECTED LOAD" in svg_content


def test_render_sanitation_riser_svg(mep_manifest: ProjectManifest):
    """Test rendering 2D vector Sanitation Riser Diagram SVG element."""
    riser_data = extract_sanitation_diagram_data(mep_manifest)
    svg_content = render_sanitation_riser_svg(riser_data, box_width_mm=330.0, box_height_mm=190.0)

    assert '<g id="sanitation-riser-diagram"' in svg_content
    assert "1. COLD WATER SUPPLY RISER DIAGRAM" in svg_content
    assert "WM" in svg_content
    assert "1,000 Liters" in svg_content
    assert "2. SOIL, WASTE &amp; VENT SCHEMATIC DIAGRAM" in svg_content
    assert "VENT CAP" in svg_content
    assert "GREASE TRAP" in svg_content
    assert "SEPTIC TANK" in svg_content
    assert "DRAIN" in svg_content


def test_render_electrical_sheet_svg(mep_manifest: ProjectManifest):
    """Test rendering complete A3 EE-101 Electrical Drawing Sheet."""
    cfg = SheetConfig(id="EE-101", title="Electrical Single Line Diagram", view_type="ELECTRICAL_DIAGRAM")
    svg_sheet = render_electrical_sheet_svg(mep_manifest, cfg)

    assert '<?xml version="1.0" encoding="UTF-8"?>' in svg_sheet
    assert '<g id="mep-electrical-viewport"' in svg_sheet
    assert "EE-101" in svg_sheet
    assert "GENERATED BY debim ARCHITECTURAL ENGINE" in svg_sheet


def test_render_sanitation_sheet_svg(mep_manifest: ProjectManifest):
    """Test rendering complete A3 SN-101 Sanitation Drawing Sheet."""
    cfg = SheetConfig(id="SN-101", title="Sanitation Riser Diagram", view_type="SANITATION_DIAGRAM")
    svg_sheet = render_sanitation_sheet_svg(mep_manifest, cfg)

    assert '<?xml version="1.0" encoding="UTF-8"?>' in svg_sheet
    assert '<g id="mep-sanitation-viewport"' in svg_sheet
    assert "SN-101" in svg_sheet
    assert "GENERATED BY debim ARCHITECTURAL ENGINE" in svg_sheet


def test_sheet_renderer_routing_mep(mep_manifest: ProjectManifest):
    """Test SheetRenderer routing for EE-101 and SN-101 sheets via render_sheet."""
    # EE-101 Sheet
    svg_ee = render_sheet(mep_manifest, SheetConfig(id="EE-101", view_type="SINGLE_LINE_DIAGRAM"))
    assert '<g id="mep-electrical-viewport"' in svg_ee

    # SN-101 Sheet
    svg_sn = render_sheet(mep_manifest, SheetConfig(id="SN-101", view_type="RISER_DIAGRAM"))
    assert '<g id="mep-sanitation-viewport"' in svg_sn


def test_sheet_renderer_auto_id_routing(mep_manifest: ProjectManifest):
    """Test SheetRenderer auto routing based on sheet ID prefix EE- or SN-."""
    renderer_ee = SheetRenderer(mep_manifest, SheetConfig(id="EE-101"))
    svg_ee = renderer_ee.render_svg()
    assert '<g id="mep-electrical-viewport"' in svg_ee

    renderer_sn = SheetRenderer(mep_manifest, SheetConfig(id="SN-101"))
    svg_sn = renderer_sn.render_svg()
    assert '<g id="mep-sanitation-viewport"' in svg_sn
