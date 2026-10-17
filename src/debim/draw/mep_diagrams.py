"""
MEP Electrical Single Line Diagram (SLD) and Sanitation & Plumbing Riser Diagram Engine for debim.
Generates 2D vector schematic diagrams for building MEP systems (งานระบบอาคาร)
fitted onto standard A3 drawing sheets (EE-101 and SN-101).
"""

from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field

from debim.resolver import (
    ResolvedDistributionBoard,
    ResolvedLightFixture,
    ResolvedManifest,
    ResolvedOutlet,
    ResolvedPipeSegment,
    ResolvedSanitaryTerminal,
    ResolvedSwitchingDevice,
    ResolvedUnitaryEquipment,
    SpatialResolver,
)
from debim.schema import (
    IfcAirTerminal,
    IfcDistributionBoard,
    IfcLightFixture,
    IfcOutlet,
    IfcPipeSegment,
    IfcSanitaryTerminal,
    IfcSwitchingDevice,
    IfcUnitaryEquipment,
    ProjectManifest,
)


class CircuitScheduleItem(BaseModel):
    """Branch circuit entry in electrical load schedule table."""
    circuit_no: str  # e.g. "1", "2", "3", "4", "5", "6", "SPARE"
    description: str  # e.g. "Lighting FL1", "Receptacles FL1", "Air Conditioner 18000 BTU", "Water Heater 4500W"
    load_va: float = 1000.0  # apparent load in VA / Watts
    breaker_rating: str = "1P 16A AT"  # e.g. "1P 10A AT", "1P 16A AT", "1P 20A AT", "1P 32A RCBO"
    wire_spec: str = "2x2.5/G1.5 sq.mm THW"  # wire size and type
    conduit_spec: str = "EMT 1/2\""  # conduit specification
    phase: str = "L"  # e.g. "L" or "L1", "L2", "L3"
    remarks: Optional[str] = None


class ElectricalSLDData(BaseModel):
    """Electrical Single Line Diagram data model."""
    board_tag: str = "CU-01"
    board_type: str = "CONSUMER_UNIT"  # e.g. "CONSUMER_UNIT" or "MAIN_DISTRIBUTION_BOARD"
    incoming_source: str = "PEA 1-Phase 2-Wire 220V 50Hz 15(45)A"
    meter_spec: str = "PEA kWh Meter 15(45)A"
    main_breaker: str = "Main MCB 2P 50A IC 10kA w/ RCBO 30mA"
    grounding_spec: str = "Bare Copper Wire 10 sq.mm to Copper Ground Rod 5/8\" x 2.4m"
    circuits: List[CircuitScheduleItem] = Field(default_factory=list)


class WaterSupplyRiserItem(BaseModel):
    """Cold water supply riser specification model."""
    main_meter: str = "PEA Water Meter Ø 1/2\""
    water_tank: str = "Underground / Ground Water Tank 1,000L"
    pump_spec: str = "Automatic Booster Pump 250W"
    riser_pipe_spec: str = "PPR Pipe Ø 3/4\" (20mm) Class 8.5"
    branch_pipe_spec: str = "PPR Pipe Ø 1/2\" (15mm) Class 8.5"
    storeys: List[Dict[str, Any]] = Field(default_factory=list)


class WasteRiserItem(BaseModel):
    """Soil, waste, and vent pipe riser schematic specification model."""
    soil_stack_spec: str = "Soil Stack VP/PVC Ø 4\" (100mm) Class 8.5"
    waste_stack_spec: str = "Waste Stack PVC Ø 2\" (50mm) Class 8.5"
    vent_stack_spec: str = "Vent Stack PVC Ø 2\" (50mm) Class 8.5"
    septic_tank_spec: str = "Anaerobic Septic Tank 1,600L"
    grease_trap_spec: str = "Under-Sink Grease Trap 15L"
    drain_outflow_spec: str = "Public Storm Drain Pipe Ø 0.30m (Slope 1:100)"
    storeys: List[Dict[str, Any]] = Field(default_factory=list)


class SanitationRiserData(BaseModel):
    """Sanitation and plumbing riser diagram data model."""
    cold_water: WaterSupplyRiserItem = Field(default_factory=WaterSupplyRiserItem)
    waste_system: WasteRiserItem = Field(default_factory=WasteRiserItem)


def extract_electrical_diagram_data(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
) -> ElectricalSLDData:
    """
    Extract electrical distribution board, lighting fixtures, outlets, air conditioners,
    and water heaters into balanced electrical load schedule and Single Line Diagram parameters.
    """
    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
    else:
        resolved = manifest_or_resolved

    boards = getattr(resolved, "distribution_boards", [])
    board_tag = boards[0].tag if boards else "CU-01"
    b_type = getattr(boards[0], "board_type", "CONSUMER_UNIT") if boards else "CONSUMER_UNIT"

    # Count electrical fixtures from resolved model
    lights = getattr(resolved, "light_fixtures", [])
    outlets = getattr(resolved, "outlets", [])
    switches = getattr(resolved, "switches", [])
    ac_units = getattr(resolved, "unitary_equipments", [])

    # Group light fixtures & outlets by storey
    storey_lights: Dict[str, int] = {}
    for l in lights:
        st = getattr(getattr(l, "placement", None), "storey", "L1") or "L1"
        storey_lights[st] = storey_lights.get(st, 0) + 1

    storey_outlets: Dict[str, int] = {}
    for o in outlets:
        st = getattr(getattr(o, "placement", None), "storey", "L1") or "L1"
        storey_outlets[st] = storey_outlets.get(st, 0) + 1

    circuits: List[CircuitScheduleItem] = []
    c_idx = 1

    # 1. Lighting Circuits
    if storey_lights:
        for st, count in sorted(storey_lights.items()):
            load_va = max(300.0, count * 60.0)
            circuits.append(
                CircuitScheduleItem(
                    circuit_no=str(c_idx),
                    description=f"Lighting Circuit ({st}) - {count} Points",
                    load_va=load_va,
                    breaker_rating="1P 10A AT",
                    wire_spec="2x1.5/G1.5 sq.mm THW",
                    conduit_spec="EMT 1/2\"",
                    phase="L",
                    remarks="Lighting Fixtures",
                )
            )
            c_idx += 1
    else:
        circuits.append(
            CircuitScheduleItem(
                circuit_no=str(c_idx),
                description="Lighting Circuit FL1 - 8 Points",
                load_va=500.0,
                breaker_rating="1P 10A AT",
                wire_spec="2x1.5/G1.5 sq.mm THW",
                conduit_spec="EMT 1/2\"",
                phase="L",
                remarks="Lighting Fixtures",
            )
        )
        c_idx += 1

    # 2. Receptacle Circuits
    if storey_outlets:
        for st, count in sorted(storey_outlets.items()):
            load_va = max(800.0, count * 180.0)
            circuits.append(
                CircuitScheduleItem(
                    circuit_no=str(c_idx),
                    description=f"Receptacles Circuit ({st}) - {count} Outlets",
                    load_va=load_va,
                    breaker_rating="1P 16A AT / RCBO",
                    wire_spec="2x2.5/G1.5 sq.mm THW",
                    conduit_spec="EMT 1/2\"",
                    phase="L",
                    remarks="Duplex Grounded Outlets",
                )
            )
            c_idx += 1
    else:
        circuits.append(
            CircuitScheduleItem(
                circuit_no=str(c_idx),
                description="Receptacles Circuit FL1 - 6 Outlets",
                load_va=1080.0,
                breaker_rating="1P 16A AT / RCBO",
                wire_spec="2x2.5/G1.5 sq.mm THW",
                conduit_spec="EMT 1/2\"",
                phase="L",
                remarks="Duplex Grounded Outlets",
            )
        )
        c_idx += 1

    # 3. Air Conditioning Circuits
    if ac_units:
        for ac in ac_units:
            cap = getattr(ac, "cooling_capacity_btu", 18000.0) or 18000.0
            load_va = round(cap / 10.0, 0)  # approx watts
            circuits.append(
                CircuitScheduleItem(
                    circuit_no=str(c_idx),
                    description=f"Air Conditioner {ac.tag} ({cap:.0f} BTU)",
                    load_va=load_va,
                    breaker_rating="1P 20A AT",
                    wire_spec="2x4/G2.5 sq.mm THW",
                    conduit_spec="EMT 1/2\"",
                    phase="L",
                    remarks="A/C Dedicated Circuit",
                )
            )
            c_idx += 1
    else:
        circuits.append(
            CircuitScheduleItem(
                circuit_no=str(c_idx),
                description="Air Conditioner AC-01 (18,000 BTU)",
                load_va=1800.0,
                breaker_rating="1P 20A AT",
                wire_spec="2x4/G2.5 sq.mm THW",
                conduit_spec="EMT 1/2\"",
                phase="L",
                remarks="A/C Dedicated Circuit",
            )
        )
        c_idx += 1

    # 4. Water Heater Circuit
    circuits.append(
        CircuitScheduleItem(
            circuit_no=str(c_idx),
            description="Water Heater WH-01 (4,500W)",
            load_va=4500.0,
            breaker_rating="1P 32A RCBO 15mA",
            wire_spec="2x6/G2.5 sq.mm THW",
            conduit_spec="EMT 3/4\"",
            phase="L",
            remarks="Water Heater w/ ELCB/RCBO",
        )
    )
    c_idx += 1

    # 5. Spare Circuits
    circuits.append(
        CircuitScheduleItem(
            circuit_no=str(c_idx),
            description="SPARE CIRCUIT",
            load_va=0.0,
            breaker_rating="1P 20A AT",
            wire_spec="-",
            conduit_spec="-",
            phase="L",
            remarks="Future Expansion",
        )
    )
    c_idx += 1

    circuits.append(
        CircuitScheduleItem(
            circuit_no=str(c_idx),
            description="SPACE FOR FUTURE",
            load_va=0.0,
            breaker_rating="SPACE",
            wire_spec="-",
            conduit_spec="-",
            phase="L",
            remarks="Space",
        )
    )

    return ElectricalSLDData(
        board_tag=board_tag,
        board_type=b_type,
        incoming_source="PEA 1-Phase 2-Wire 220V 50Hz 15(45)A",
        meter_spec="PEA kWh Meter 15(45)A",
        main_breaker="Main MCB 2P 50A IC 10kA w/ Main RCBO 30mA",
        grounding_spec="Bare Copper Wire 10 sq.mm to Copper Ground Rod 5/8\" x 2.4m",
        circuits=circuits,
    )


def extract_sanitation_diagram_data(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
) -> SanitationRiserData:
    """
    Extract sanitary terminals (WC, Basin, Sink, Shower, Septic Tank, Grease Trap)
    and piping systems across storeys into cold water supply and soil/waste/vent riser data.
    """
    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
    else:
        resolved = manifest_or_resolved

    storeys_meta = []
    storeys_list = getattr(resolved.manifest.spatial_structure, "storeys", [])
    if storeys_list:
        for s in storeys_list:
            storeys_meta.append({"id": s.id, "name": s.name, "elevation": s.elevation})
    else:
        storeys_meta = [
            {"id": "L1", "name": "Level 1 Ground", "elevation": 0.0},
            {"id": "L2", "name": "Level 2 Second", "elevation": 3.5},
        ]

    # Map sanitary terminals by storey
    sanitary_terms = getattr(resolved, "sanitary_terminals", [])

    cw_storeys = []
    waste_storeys = []

    for s_info in storeys_meta:
        st_id = s_info["id"]
        st_name = s_info["name"]
        st_elev = s_info["elevation"]

        cw_fixtures = ["Wash Basin", "Water Closet", "Shower", "Kitchen Sink"]
        waste_fixtures = ["WC (Soil Ø 4\")", "Basin (Waste Ø 2\")", "Floor Drain (Waste Ø 2\")", "Kitchen Sink (Grease Ø 2\")"]

        cw_storeys.append({
            "storey_id": st_id,
            "storey_name": st_name,
            "elevation": st_elev,
            "fixtures": cw_fixtures,
        })

        waste_storeys.append({
            "storey_id": st_id,
            "storey_name": st_name,
            "elevation": st_elev,
            "fixtures": waste_fixtures,
        })

    cold_water = WaterSupplyRiserItem(
        main_meter="PEA Water Meter Ø 1/2\"",
        water_tank="Underground / Ground Water Tank 1,000L",
        pump_spec="Automatic Booster Pump 250W",
        riser_pipe_spec="PPR Pipe Ø 3/4\" (20mm) Class 8.5",
        branch_pipe_spec="PPR Pipe Ø 1/2\" (15mm) Class 8.5",
        storeys=cw_storeys,
    )

    waste_sys = WasteRiserItem(
        soil_stack_spec="Soil Stack VP/PVC Ø 4\" (100mm) Class 8.5",
        waste_stack_spec="Waste Stack PVC Ø 2\" (50mm) Class 8.5",
        vent_stack_spec="Vent Stack PVC Ø 2\" (50mm) Class 8.5",
        septic_tank_spec="Anaerobic Septic Tank 1,600L",
        grease_trap_spec="Under-Sink Grease Trap 15L",
        drain_outflow_spec="Public Storm Drain Pipe Ø 0.30m (Slope 1:100)",
        storeys=waste_storeys,
    )

    return SanitationRiserData(cold_water=cold_water, waste_system=waste_sys)


def render_electrical_sld_svg(
    data: ElectricalSLDData,
    box_width_mm: float = 330.0,
    box_height_mm: float = 190.0,
) -> str:
    """
    Render 2D vector Electrical Single Line Diagram (SLD) schematic & Panel Load Schedule table.
    """
    # Split layout: Left area for SLD schematic diagram, Right area for Panel Schedule table
    sld_w = 145.0
    tbl_x = 150.0
    tbl_w = box_width_mm - tbl_x - 2.0

    svg_lines = [
        '<g id="electrical-sld-diagram" class="mep-diagram">',
        '  <!-- Background Container -->',
        f'  <rect x="0" y="0" width="{box_width_mm:.1f}" height="{box_height_mm:.1f}" fill="#ffffff" stroke="#94a3b8" stroke-width="0.5" rx="1.0" />',

        '  <!-- Diagram Title Header -->',
        f'  <rect x="2.0" y="2.0" width="{box_width_mm - 4.0:.1f}" height="8.0" fill="#0f172a" rx="0.5" />',
        f'  <text x="6.0" y="7.5" font-family="Sarabun, sans-serif" font-size="4.2px" font-weight="bold" fill="#ffffff">ไดอะแกรมเส้นเดียวระบบไฟฟ้า (ELECTRICAL SINGLE LINE DIAGRAM &amp; PANEL LOAD SCHEDULE) - {data.board_tag}</text>',

        '  <!-- LEFT PANEL: SINGLE LINE DIAGRAM SCHEMATIC -->',
        '  <g transform="translate(4.0, 14.0)">',
        '    <!-- Incoming PEA Supply & Meter -->',
        '    <text x="2.0" y="4.0" font-family="Sarabun, sans-serif" font-size="2.6px" font-weight="bold" fill="#0f172a">INCOMING SUPPLY: ' + data.incoming_source + '</text>',

        '    <!-- PEA Meter Box -->',
        '    <rect x="15.0" y="8.0" width="16.0" height="12.0" fill="#f8fafc" stroke="#0f172a" stroke-width="0.8" rx="0.5" />',
        '    <circle cx="23.0" cy="14.0" r="3.5" fill="none" stroke="#2563eb" stroke-width="0.6" />',
        '    <text x="23.0" y="15.0" font-family="Sarabun, sans-serif" font-size="2.6px" font-weight="bold" text-anchor="middle" fill="#2563eb">kWh</text>',
        '    <text x="33.0" y="14.0" font-family="Sarabun, sans-serif" font-size="2.2px" fill="#475569">' + data.meter_spec + '</text>',

        '    <!-- Incoming Feed Line -->',
        '    <line x1="23.0" y1="20.0" x2="23.0" y2="30.0" stroke="#0f172a" stroke-width="1.0" />',

        '    <!-- Main Breaker / RCBO Symbol -->',
        '    <rect x="15.0" y="30.0" width="16.0" height="14.0" fill="#eff6ff" stroke="#1d4ed8" stroke-width="0.9" rx="0.5" />',
        '    <line x1="18.0" y1="33.0" x2="28.0" y2="41.0" stroke="#dc2626" stroke-width="1.0" />',
        '    <text x="23.0" y="38.0" font-family="Sarabun, sans-serif" font-size="2.8px" font-weight="bold" text-anchor="middle" fill="#1e3a8a">MAIN</text>',
        '    <text x="33.0" y="37.0" font-family="Sarabun, sans-serif" font-size="2.3px" font-weight="bold" fill="#1d4ed8">' + data.main_breaker + '</text>',

        '    <!-- Ground Bar & Ground Rod Symbol -->',
        '    <line x1="12.0" y1="46.0" x2="12.0" y2="60.0" stroke="#15803d" stroke-width="0.8" stroke-dasharray="2 1" />',
        '    <line x1="8.0" y1="60.0" x2="16.0" y2="60.0" stroke="#15803d" stroke-width="1.0" />',
        '    <line x1="9.5" y1="62.0" x2="14.5" y2="62.0" stroke="#15803d" stroke-width="0.8" />',
        '    <line x1="11.0" y1="64.0" x2="13.0" y2="64.0" stroke="#15803d" stroke-width="0.6" />',
        '    <text x="18.0" y="58.0" font-family="Sarabun, sans-serif" font-size="2.0px" fill="#15803d">' + data.grounding_spec + '</text>',

        '    <!-- Line from Main to Bus Bar -->',
        '    <line x1="23.0" y1="44.0" x2="23.0" y2="52.0" stroke="#0f172a" stroke-width="1.2" />',

        '    <!-- Distribution Bus Bar Horizontal Heavy Line -->',
        '    <rect x="10.0" y="52.0" width="125.0" height="3.0" fill="#0f172a" />',
        '    <text x="10.0" y="50.0" font-family="Sarabun, sans-serif" font-size="2.6px" font-weight="bold" fill="#0f172a">BUS BAR (1P / L+N 220V)</text>',
    ]

    # Render Branch Circuits coming off the Bus Bar vertically down
    n_circuits = len(data.circuits)
    col_spacing = 115.0 / max(n_circuits, 1)

    load_y0 = 65.0

    for idx, c in enumerate(data.circuits):
        cx = 18.0 + idx * col_spacing

        # Connection line down from bus bar
        svg_lines.append(f'    <line x1="{cx:.1f}" y1="55.0" x2="{cx:.1f}" y2="68.0" stroke="#0f172a" stroke-width="0.8" />')
        svg_lines.append(f'    <circle cx="{cx:.1f}" cy="53.5" r="1.0" fill="#0f172a" />')

        # Branch Breaker Symbol Box
        if c.breaker_rating != "SPACE":
            svg_lines.append(f'    <rect x="{cx - 4.5:.1f}" y="68.0" width="9.0" height="10.0" fill="#ffffff" stroke="#0f172a" stroke-width="0.7" rx="0.3" />')
            svg_lines.append(f'    <line x1="{cx - 3.0:.1f}" y1="70.0" x2="{cx + 3.0:.1f}" y2="76.0" stroke="#dc2626" stroke-width="0.8" />')
            svg_lines.append(f'    <text x="{cx:.1f}" y="82.0" font-family="Sarabun, sans-serif" font-size="1.9px" font-weight="bold" text-anchor="middle" transform="rotate(-90 {cx:.1f} 82.0)" fill="#0f172a">{c.breaker_rating}</text>')

            # Feed Line to Load Icon
            svg_lines.append(f'    <line x1="{cx:.1f}" y1="78.0" x2="{cx:.1f}" y2="105.0" stroke="#0f172a" stroke-width="0.7" />')

            # Load Symbol Icon based on description
            desc_u = c.description.upper()
            if "LIGHT" in desc_u:
                # Circle with X for lighting
                svg_lines.append(f'    <circle cx="{cx:.1f}" cy="110.0" r="4.0" fill="#fef08a" stroke="#0f172a" stroke-width="0.7" />')
                svg_lines.append(f'    <line x1="{cx - 2.8:.1f}" y1="107.2" x2="{cx + 2.8:.1f}" y2="112.8" stroke="#0f172a" stroke-width="0.6" />')
                svg_lines.append(f'    <line x1="{cx - 2.8:.1f}" y1="112.8" x2="{cx + 2.8:.1f}" y2="107.2" stroke="#0f172a" stroke-width="0.6" />')
            elif "RECEPTACLE" in desc_u or "OUTLET" in desc_u:
                # Duplex Outlet Circle with 2 vertical lines
                svg_lines.append(f'    <circle cx="{cx:.1f}" cy="110.0" r="4.0" fill="#e0f2fe" stroke="#0f172a" stroke-width="0.7" />')
                svg_lines.append(f'    <line x1="{cx - 1.2:.1f}" y1="107.0" x2="{cx - 1.2:.1f}" y2="113.0" stroke="#0f172a" stroke-width="0.6" />')
                svg_lines.append(f'    <line x1="{cx + 1.2:.1f}" y1="107.0" x2="{cx + 1.2:.1f}" y2="113.0" stroke="#0f172a" stroke-width="0.6" />')
            elif "AIR" in desc_u or "AC" in desc_u:
                # Rectangle FCU icon for AC
                svg_lines.append(f'    <rect x="{cx - 5.0:.1f}" y="106.0" width="10.0" height="7.0" fill="#dcfce7" stroke="#0f172a" stroke-width="0.7" rx="0.5" />')
                svg_lines.append(f'    <text x="{cx:.1f}" y="111.0" font-family="Sarabun, sans-serif" font-size="2.2px" font-weight="bold" text-anchor="middle" fill="#15803d">A/C</text>')
            elif "HEATER" in desc_u:
                # Circle with W for Water Heater
                svg_lines.append(f'    <circle cx="{cx:.1f}" cy="110.0" r="4.0" fill="#fee2e2" stroke="#b91c1c" stroke-width="0.8" />')
                svg_lines.append(f'    <text x="{cx:.1f}" y="111.2" font-family="Sarabun, sans-serif" font-size="2.4px" font-weight="bold" text-anchor="middle" fill="#b91c1c">WH</text>')
            else:
                svg_lines.append(f'    <circle cx="{cx:.1f}" cy="110.0" r="3.5" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.6" />')

            # Circuit Number Callout Bubble
            svg_lines.append(f'    <circle cx="{cx:.1f}" cy="120.0" r="3.2" fill="#0f172a" />')
            svg_lines.append(f'    <text x="{cx:.1f}" y="121.0" font-family="Sarabun, sans-serif" font-size="2.6px" font-weight="bold" text-anchor="middle" fill="#ffffff">{c.circuit_no}</text>')

    svg_lines.append('  </g> <!-- End SLD Left Panel -->')

    # RIGHT PANEL: PANEL LOAD SCHEDULE TABLE
    svg_lines.append(f'  <g id="load-schedule-table" transform="translate({tbl_x:.1f}, 14.0)">')
    svg_lines.append(f'    <rect x="0" y="0" width="{tbl_w:.1f}" height="7.0" fill="#1e293b" rx="0.5" />')
    svg_lines.append(f'    <text x="4.0" y="4.8" font-family="Sarabun, sans-serif" font-size="3.5px" font-weight="bold" fill="#ffffff">ตารางโหลดไฟฟ้า (PANEL BOARD LOAD SCHEDULE) - {data.board_tag}</text>')

    # Table Headers
    cols = [
        ("CKT", 8.0),
        ("DESCRIPTION / รายการโหลด", 42.0),
        ("LOAD (VA)", 18.0),
        ("BREAKER", 22.0),
        ("WIRE SPECIFICATION", 32.0),
        ("CONDUIT", 16.0),
        ("REMARKS", 30.0),
    ]

    row_y = 11.0
    curr_x = 0.0

    svg_lines.append(f'    <rect x="0" y="{row_y - 3.5:.1f}" width="{tbl_w:.1f}" height="6.0" fill="#e2e8f0" stroke="#cbd5e1" stroke-width="0.3" />')
    for heading, width in cols:
        svg_lines.append(f'    <text x="{curr_x + 2.0:.1f}" y="{row_y + 0.8:.1f}" font-family="Sarabun, sans-serif" font-size="2.1px" font-weight="bold" fill="#0f172a">{heading}</text>')
        curr_x += width
        if curr_x < tbl_w:
            svg_lines.append(f'    <line x1="{curr_x:.1f}" y1="{row_y - 3.5:.1f}" x2="{curr_x:.1f}" y2="160.0" stroke="#cbd5e1" stroke-width="0.3" />')

    row_y = 18.0
    row_h = 7.5
    total_va = 0.0

    for idx, c in enumerate(data.circuits):
        bg_fill = "#f8fafc" if idx % 2 == 0 else "#ffffff"
        svg_lines.append(f'    <rect x="0" y="{row_y - 3.5:.1f}" width="{tbl_w:.1f}" height="{row_h:.1f}" fill="{bg_fill}" stroke="#e2e8f0" stroke-width="0.3" />')

        curr_x = 0.0
        vals = [
            c.circuit_no,
            c.description,
            f"{c.load_va:.0f} VA" if c.load_va > 0 else "-",
            c.breaker_rating,
            c.wire_spec,
            c.conduit_spec,
            c.remarks or "-",
        ]

        for i, val in enumerate(vals):
            fw = "bold" if i in (0, 2, 3) else "normal"
            clr = "#0f172a" if i != 0 else "#2563eb"
            svg_lines.append(f'    <text x="{curr_x + 2.0:.1f}" y="{row_y + 1.2:.1f}" font-family="Sarabun, sans-serif" font-size="2.2px" font-weight="{fw}" fill="{clr}">{val}</text>')
            curr_x += cols[i][1]

        total_va += c.load_va
        row_y += row_h

    # Total Load Summary Row
    total_amps = total_va / 220.0
    svg_lines.append(f'    <rect x="0" y="{row_y - 3.5:.1f}" width="{tbl_w:.1f}" height="8.0" fill="#0f172a" />')
    svg_lines.append(f'    <text x="4.0" y="{row_y + 1.8:.1f}" font-family="Sarabun, sans-serif" font-size="2.8px" font-weight="bold" fill="#ffffff">TOTAL CONNECTED LOAD / โหลดรวมทั้งหมด:</text>')
    svg_lines.append(f'    <text x="80.0" y="{row_y + 1.8:.1f}" font-family="Sarabun, sans-serif" font-size="2.8px" font-weight="bold" fill="#fef08a">{total_va:.0f} VA ({total_amps:.1f} Amps @ 220V 1-Phase)</text>')

    svg_lines.append('  </g> <!-- End Load Schedule Table -->')
    svg_lines.append('</g>')

    return "\n".join(svg_lines)


def render_sanitation_riser_svg(
    data: SanitationRiserData,
    box_width_mm: float = 330.0,
    box_height_mm: float = 190.0,
) -> str:
    """
    Render 2D vector Sanitation & Plumbing Riser Diagram (Cold Water + Soil/Waste/Vent).
    """
    half_w = (box_width_mm - 8.0) / 2.0

    svg_lines = [
        '<g id="sanitation-riser-diagram" class="mep-diagram">',
        '  <!-- Background Container -->',
        f'  <rect x="0" y="0" width="{box_width_mm:.1f}" height="{box_height_mm:.1f}" fill="#ffffff" stroke="#94a3b8" stroke-width="0.5" rx="1.0" />',

        '  <!-- Diagram Title Header -->',
        f'  <rect x="2.0" y="2.0" width="{box_width_mm - 4.0:.1f}" height="8.0" fill="#0f172a" rx="0.5" />',
        '  <text x="6.0" y="7.5" font-family="Sarabun, sans-serif" font-size="4.2px" font-weight="bold" fill="#ffffff">ไดอะแกรมระบบสุขาภิบาล (COLD WATER &amp; SANITATION SOIL, WASTE, VENT RISER DIAGRAM)</text>',

        # LEFT PANEL: COLD WATER SUPPLY RISER
        '  <g id="cold-water-riser" transform="translate(4.0, 14.0)">',
        f'    <rect x="0" y="0" width="{half_w:.1f}" height="{box_height_mm - 20.0:.1f}" fill="#f8fafc" stroke="#3b82f6" stroke-width="0.6" rx="0.5" />',
        f'    <rect x="0" y="0" width="{half_w:.1f}" height="7.0" fill="#2563eb" />',
        '    <text x="4.0" y="4.8" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" fill="#ffffff">1. COLD WATER SUPPLY RISER DIAGRAM (ไดอะแกรมประปาน้ำเย็น)</text>',

        '    <!-- Public Main & Water Meter -->',
        '    <line x1="10.0" y1="150.0" x2="35.0" y2="150.0" stroke="#0284c7" stroke-width="1.2" />',
        '    <circle cx="20.0" cy="150.0" r="3.5" fill="#ffffff" stroke="#0284c7" stroke-width="0.8" />',
        '    <text x="20.0" y="151.0" font-family="Sarabun, sans-serif" font-size="2.2px" font-weight="bold" text-anchor="middle" fill="#0284c7">WM</text>',
        '    <text x="10.0" y="158.0" font-family="Sarabun, sans-serif" font-size="2.0px" fill="#0284c7">' + data.cold_water.main_meter + '</text>',

        '    <!-- Underground Water Tank -->',
        '    <rect x="35.0" y="135.0" width="30.0" height="20.0" fill="#e0f2fe" stroke="#0284c7" stroke-width="1.0" rx="1.0" />',
        '    <text x="50.0" y="144.0" font-family="Sarabun, sans-serif" font-size="2.2px" font-weight="bold" text-anchor="middle" fill="#0369a1">ถังเก็บน้ำ</text>',
        '    <text x="50.0" y="148.0" font-family="Sarabun, sans-serif" font-size="2.0px" text-anchor="middle" fill="#0369a1">1,000 Liters</text>',

        '    <!-- Booster Pump -->',
        '    <rect x="75.0" y="140.0" width="14.0" height="12.0" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.8" rx="0.5" />',
        '    <circle cx="82.0" cy="146.0" r="3.0" fill="#3b82f6" />',
        '    <text x="82.0" y="157.0" font-family="Sarabun, sans-serif" font-size="2.0px" font-weight="bold" text-anchor="middle" fill="#0f172a">' + data.cold_water.pump_spec + '</text>',

        '    <!-- Connection lines Tank to Pump to Riser -->',
        '    <line x1="65.0" y1="146.0" x2="75.0" y2="146.0" stroke="#0284c7" stroke-width="1.0" />',
        '    <line x1="89.0" y1="146.0" x2="105.0" y2="146.0" stroke="#0284c7" stroke-width="1.2" />',

        '    <!-- Vertical PPR Cold Water Riser Stack -->',
        '    <line x1="105.0" y1="20.0" x2="105.0" y2="146.0" stroke="#0284c7" stroke-width="1.6" />',
        '    <text x="108.0" y="80.0" font-family="Sarabun, sans-serif" font-size="2.2px" font-weight="bold" fill="#0284c7">' + data.cold_water.riser_pipe_spec + '</text>',
    ]

    # Render Cold Water Storey Branch feeds
    cw_y_base = 120.0
    for idx, st in enumerate(data.cold_water.storeys):
        sy = cw_y_base - idx * 45.0

        # Storey Level Line
        svg_lines.append(f'    <line x1="10.0" y1="{sy:.1f}" x2="{half_w - 10.0:.1f}" y2="{sy:.1f}" stroke="#94a3b8" stroke-width="0.4" stroke-dasharray="2 1" />')
        svg_lines.append(f'    <text x="12.0" y="{sy - 2.0:.1f}" font-family="Sarabun, sans-serif" font-size="2.4px" font-weight="bold" fill="#334155">{st["storey_name"]} (+{st["elevation"]:.2f}m)</text>')

        # Branch Pipe Line from Riser
        branch_y = sy - 15.0
        svg_lines.append(f'    <line x1="105.0" y1="{branch_y:.1f}" x2="30.0" y2="{branch_y:.1f}" stroke="#0284c7" stroke-width="1.0" />')
        svg_lines.append(f'    <circle cx="105.0" cy="{branch_y:.1f}" r="1.2" fill="#0284c7" />')

        # Gate Valve Symbol
        svg_lines.append(f'    <polygon points="90.0,{branch_y - 2.0:.1f} 90.0,{branch_y + 2.0:.1f} 96.0,{branch_y:.1f}" fill="#0284c7" />')
        svg_lines.append(f'    <polygon points="96.0,{branch_y - 2.0:.1f} 96.0,{branch_y + 2.0:.1f} 90.0,{branch_y:.1f}" fill="#0284c7" />')
        svg_lines.append(f'    <text x="93.0" y="{branch_y - 3.5:.1f}" font-family="Sarabun, sans-serif" font-size="1.8px" text-anchor="middle" fill="#0284c7">Gate Valve</text>')

        # Fixtures Drop Lines
        fix_x = [35.0, 50.0, 65.0, 80.0]
        for f_i, fix_name in enumerate(st.get("fixtures", [])):
            if f_i < len(fix_x):
                fx = fix_x[f_i]
                svg_lines.append(f'    <line x1="{fx:.1f}" y1="{branch_y:.1f}" x2="{fx:.1f}" y2="{branch_y + 8.0:.1f}" stroke="#0284c7" stroke-width="0.8" />')
                svg_lines.append(f'    <circle cx="{fx:.1f}" cy="{branch_y + 10.0:.1f}" r="2.2" fill="#e0f2fe" stroke="#0284c7" stroke-width="0.6" />')
                svg_lines.append(f'    <text x="{fx:.1f}" y="{branch_y + 14.0:.1f}" font-family="Sarabun, sans-serif" font-size="1.8px" text-anchor="middle" fill="#0369a1">{fix_name[:10]}</text>')

    svg_lines.append('  </g> <!-- End Cold Water Left Panel -->')

    # RIGHT PANEL: SOIL, WASTE, AND VENT RISER DIAGRAM
    right_x = half_w + 12.0
    svg_lines.append(f'  <g id="sanitation-stack-riser" transform="translate({right_x:.1f}, 14.0)">')
    svg_lines.append(f'    <rect x="0" y="0" width="{half_w:.1f}" height="{box_height_mm - 20.0:.1f}" fill="#f8fafc" stroke="#dc2626" stroke-width="0.6" rx="0.5" />')
    svg_lines.append(f'    <rect x="0" y="0" width="{half_w:.1f}" height="7.0" fill="#b91c1c" />')
    svg_lines.append('    <text x="4.0" y="4.8" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" fill="#ffffff">2. SOIL, WASTE &amp; VENT SCHEMATIC DIAGRAM (ไดอะแกรมระบบน้ำเสีย-โถส้วม-ท่ออากาศ)</text>')

    # Stacks Vertical Positions:
    # Vent Stack (Left), Waste Stack (Middle), Soil Stack (Right)
    vent_x = 45.0
    waste_x = 75.0
    soil_x = 105.0

    # Vertical Vent Stack (Green line)
    svg_lines.append(f'  <line x1="{vent_x:.1f}" y1="12.0" x2="{vent_x:.1f}" y2="135.0" stroke="#16a34a" stroke-width="1.2" stroke-dasharray="3 1" />')
    svg_lines.append(f'  <text x="{vent_x - 2.0:.1f}" y="10.0" font-family="Sarabun, sans-serif" font-size="2.0px" font-weight="bold" text-anchor="end" fill="#16a34a">VENT CAP (Roof)</text>')
    svg_lines.append(f'  <path d="M {vent_x - 3.0:.1f} 12.0 L {vent_x:.1f} 8.0 L {vent_x + 3.0:.1f} 12.0 Z" fill="#16a34a" />')

    # Vertical Waste Stack (Grey/Brown line)
    svg_lines.append(f'  <line x1="{waste_x:.1f}" y1="20.0" x2="{waste_x:.1f}" y2="135.0" stroke="#475569" stroke-width="1.4" />')
    svg_lines.append(f'  <text x="{waste_x + 2.0:.1f}" y="80.0" font-family="Sarabun, sans-serif" font-size="2.0px" font-weight="bold" fill="#475569">' + data.waste_system.waste_stack_spec + '</text>')

    # Vertical Soil Stack (Dark Red line)
    svg_lines.append(f'  <line x1="{soil_x:.1f}" y1="20.0" x2="{soil_x:.1f}" y2="135.0" stroke="#b91c1c" stroke-width="1.8" />')
    svg_lines.append(f'  <text x="{soil_x + 2.0:.1f}" y="80.0" font-family="Sarabun, sans-serif" font-size="2.0px" font-weight="bold" fill="#b91c1c">' + data.waste_system.soil_stack_spec + '</text>')

    # Storey Fixture Connections to Stacks
    sw_y_base = 120.0
    for idx, st in enumerate(data.waste_system.storeys):
        sy = sw_y_base - idx * 45.0

        svg_lines.append(f'  <line x1="10.0" y1="{sy:.1f}" x2="{half_w - 10.0:.1f}" y2="{sy:.1f}" stroke="#94a3b8" stroke-width="0.4" stroke-dasharray="2 1" />')
        svg_lines.append(f'  <text x="12.0" y="{sy - 2.0:.1f}" font-family="Sarabun, sans-serif" font-size="2.4px" font-weight="bold" fill="#334155">{st["storey_name"]} (+{st["elevation"]:.2f}m)</text>')

        # Fixture Branch Line with P-Trap
        fy = sy - 15.0
        svg_lines.append(f'  <line x1="15.0" y1="{fy:.1f}" x2="{soil_x:.1f}" y2="{fy:.1f}" stroke="#b91c1c" stroke-width="1.0" />')

        # Vent connection line to Vent Stack
        svg_lines.append(f'  <line x1="30.0" y1="{fy:.1f}" x2="{vent_x:.1f}" y2="{fy - 8.0:.1f}" stroke="#16a34a" stroke-width="0.8" stroke-dasharray="2 1" />')

        # WC Icon (Soil)
        svg_lines.append(f'  <rect x="15.0" y="{fy - 8.0:.1f}" width="8.0" height="8.0" fill="#fee2e2" stroke="#b91c1c" stroke-width="0.6" rx="0.5" />')
        svg_lines.append(f'  <text x="19.0" y="{fy - 3.0:.1f}" font-family="Sarabun, sans-serif" font-size="1.8px" font-weight="bold" text-anchor="middle" fill="#b91c1c">WC</text>')

        # Basin / Floor Drain Icons (Waste)
        svg_lines.append(f'  <circle cx="55.0" cy="{fy - 4.0:.1f}" r="3.0" fill="#f1f5f9" stroke="#475569" stroke-width="0.6" />')
        svg_lines.append(f'  <text x="55.0" y="{fy - 3.0:.1f}" font-family="Sarabun, sans-serif" font-size="1.6px" text-anchor="middle" fill="#475569">FD</text>')

    # Ground Level Treatment: Septic Tank & Grease Trap & Storm Drain
    svg_lines.append('    <!-- Septic Tank & Grease Trap Systems -->')

    # Grease Trap Box
    svg_lines.append(f'    <rect x="{waste_x - 12.0:.1f}" y="140.0" width="22.0" height="14.0" fill="#fef3c7" stroke="#d97706" stroke-width="0.8" rx="0.5" />')
    svg_lines.append(f'    <text x="{waste_x - 1.0:.1f}" y="147.0" font-family="Sarabun, sans-serif" font-size="2.0px" font-weight="bold" text-anchor="middle" fill="#b45309">GREASE TRAP</text>')
    svg_lines.append(f'    <text x="{waste_x - 1.0:.1f}" y="151.0" font-family="Sarabun, sans-serif" font-size="1.8px" text-anchor="middle" fill="#b45309">ถังดักไขมัน 15L</text>')

    # Septic Tank Box
    svg_lines.append(f'    <rect x="{soil_x - 12.0:.1f}" y="138.0" width="28.0" height="18.0" fill="#fee2e2" stroke="#b91c1c" stroke-width="1.0" rx="1.0" />')
    svg_lines.append(f'    <text x="{soil_x + 2.0:.1f}" y="146.0" font-family="Sarabun, sans-serif" font-size="2.2px" font-weight="bold" text-anchor="middle" fill="#991b1b">SEPTIC TANK</text>')
    svg_lines.append(f'    <text x="{soil_x + 2.0:.1f}" y="150.0" font-family="Sarabun, sans-serif" font-size="1.8px" text-anchor="middle" fill="#991b1b">ถังเกรอะ 1,600L</text>')

    # Outflow to Public Drain
    svg_lines.append(f'    <line x1="{soil_x + 16.0:.1f}" y1="148.0" x2="{half_w - 15.0:.1f}" y2="148.0" stroke="#0f172a" stroke-width="1.2" />')
    svg_lines.append(f'    <circle cx="{half_w - 10.0:.1f}" cy="148.0" r="4.0" fill="#e2e8f0" stroke="#0f172a" stroke-width="0.8" />')
    svg_lines.append(f'    <text x="{half_w - 10.0:.1f}" y="149.0" font-family="Sarabun, sans-serif" font-size="1.8px" font-weight="bold" text-anchor="middle" fill="#0f172a">DRAIN</text>')
    svg_lines.append(f'    <text x="{half_w - 25.0:.1f}" y="156.0" font-family="Sarabun, sans-serif" font-size="1.8px" fill="#0f172a">' + data.waste_system.drain_outflow_spec + '</text>')

    svg_lines.append('  </g> <!-- End Right Panel -->')
    svg_lines.append('</g>')

    return "\n".join(svg_lines)


def render_electrical_sheet_svg(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    sheet_config: Optional[Any] = None,
) -> str:
    """
    Render complete A3 Electrical Drawing Sheet (EE-101) containing Single Line Diagram,
    Panel Board Load Schedule Table, and Standard Title Block.
    """
    from debim.draw.renderer import SheetConfig, SheetRenderer

    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
    else:
        resolved = manifest_or_resolved

    data = extract_electrical_diagram_data(resolved)

    if sheet_config is None:
        cfg = SheetConfig(
            id="EE-101",
            title="Electrical Single Line Diagram and Load Schedule",
            view_type="ELECTRICAL_DIAGRAM",
            paper_size="A3",
            scale=1,
        )
    elif isinstance(sheet_config, SheetConfig):
        cfg = sheet_config
    else:
        cfg = SheetConfig.model_validate(sheet_config)

    paper_w, paper_h = cfg.get_paper_dimensions_mm()
    m_left, m_top, m_right, m_bottom = cfg.get_margins_mm()

    printable_x = m_left
    printable_y = m_top
    printable_w = paper_w - m_left - m_right
    printable_h = paper_h - m_top - m_bottom

    tb_width = cfg.title_block.width_mm if cfg.visibility.show_title_block else 0.0
    drawing_w = printable_w - tb_width - (5.0 if tb_width > 0 else 0.0)
    title_x = printable_x + printable_w - tb_width if tb_width > 0 else 0.0

    renderer = SheetRenderer(resolved, cfg)
    embedded_css = renderer._get_embedded_css() if hasattr(renderer, "_get_embedded_css") else ""

    sld_svg = render_electrical_sld_svg(data, box_width_mm=drawing_w, box_height_mm=printable_h - 4.0)

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {paper_w:.1f} {paper_h:.1f}" width="{paper_w:.1f}mm" height="{paper_h:.1f}mm">',
        '  <defs>',
        '    <style type="text/css"><![CDATA[',
        f'{embedded_css}',
        '    ]]></style>',
        '  </defs>',
        '  <!-- Background -->',
        f'  <rect x="0" y="0" width="{paper_w:.1f}" height="{paper_h:.1f}" fill="#ffffff" />',
        '  <!-- Outer Sheet Border & Margin -->',
        f'  <rect x="{printable_x:.1f}" y="{printable_y:.1f}" width="{printable_w:.1f}" height="{printable_h:.1f}" class="sheet-border" fill="none" />',
        f'  <rect x="{printable_x + 2.0:.1f}" y="{printable_y + 2.0:.1f}" width="{printable_w - 4.0:.1f}" height="{printable_h - 4.0:.1f}" class="sheet-inner-border" fill="none" />',
        '  <!-- Drawing Viewport for Electrical SLD Sheet -->',
        f'  <g id="mep-electrical-viewport" transform="translate({printable_x:.1f}, {printable_y:.1f})">',
        f'{sld_svg}',
        '  </g>',
    ]

    # Title Block
    if cfg.visibility.show_title_block:
        proj_name = cfg.project_name or resolved.manifest.project.name
        date_str = cfg.date or "2025-01-01"
        svg_lines.append(renderer._render_title_block_svg(title_x, printable_y, tb_width, printable_h, proj_name, date_str))

    svg_lines.append('</svg>')
    return "\n".join(svg_lines)


def render_sanitation_sheet_svg(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    sheet_config: Optional[Any] = None,
) -> str:
    """
    Render complete A3 Sanitation & Plumbing Drawing Sheet (SN-101) containing Cold Water
    Riser Diagram, Soil/Waste/Vent Stack Schematic Diagram, and Standard Title Block.
    """
    from debim.draw.renderer import SheetConfig, SheetRenderer

    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
    else:
        resolved = manifest_or_resolved

    data = extract_sanitation_diagram_data(resolved)

    if sheet_config is None:
        cfg = SheetConfig(
            id="SN-101",
            title="Sanitation and Plumbing Riser Diagrams",
            view_type="SANITATION_DIAGRAM",
            paper_size="A3",
            scale=1,
        )
    elif isinstance(sheet_config, SheetConfig):
        cfg = sheet_config
    else:
        cfg = SheetConfig.model_validate(sheet_config)

    paper_w, paper_h = cfg.get_paper_dimensions_mm()
    m_left, m_top, m_right, m_bottom = cfg.get_margins_mm()

    printable_x = m_left
    printable_y = m_top
    printable_w = paper_w - m_left - m_right
    printable_h = paper_h - m_top - m_bottom

    tb_width = cfg.title_block.width_mm if cfg.visibility.show_title_block else 0.0
    drawing_w = printable_w - tb_width - (5.0 if tb_width > 0 else 0.0)
    title_x = printable_x + printable_w - tb_width if tb_width > 0 else 0.0

    renderer = SheetRenderer(resolved, cfg)
    embedded_css = renderer._get_embedded_css() if hasattr(renderer, "_get_embedded_css") else ""

    riser_svg = render_sanitation_riser_svg(data, box_width_mm=drawing_w, box_height_mm=printable_h - 4.0)

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {paper_w:.1f} {paper_h:.1f}" width="{paper_w:.1f}mm" height="{paper_h:.1f}mm">',
        '  <defs>',
        '    <style type="text/css"><![CDATA[',
        f'{embedded_css}',
        '    ]]></style>',
        '  </defs>',
        '  <!-- Background -->',
        f'  <rect x="0" y="0" width="{paper_w:.1f}" height="{paper_h:.1f}" fill="#ffffff" />',
        '  <!-- Outer Sheet Border & Margin -->',
        f'  <rect x="{printable_x:.1f}" y="{printable_y:.1f}" width="{printable_w:.1f}" height="{printable_h:.1f}" class="sheet-border" fill="none" />',
        f'  <rect x="{printable_x + 2.0:.1f}" y="{printable_y + 2.0:.1f}" width="{printable_w - 4.0:.1f}" height="{printable_h - 4.0:.1f}" class="sheet-inner-border" fill="none" />',
        '  <!-- Drawing Viewport for Sanitation Riser Sheet -->',
        f'  <g id="mep-sanitation-viewport" transform="translate({printable_x:.1f}, {printable_y:.1f})">',
        f'{riser_svg}',
        '  </g>',
    ]

    # Title Block
    if cfg.visibility.show_title_block:
        proj_name = cfg.project_name or resolved.manifest.project.name
        date_str = cfg.date or "2025-01-01"
        svg_lines.append(renderer._render_title_block_svg(title_x, printable_y, tb_width, printable_h, proj_name, date_str))

    svg_lines.append('</svg>')
    return "\n".join(svg_lines)
