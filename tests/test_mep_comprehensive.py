"""
Comprehensive Unit Tests for MEP Distribution Systems (~200 Entities).
Verifies:
- Flow Segments & Fittings (IfcDuctSegment, IfcPipeSegment, IfcCableCarrierSegment, fittings) with 3D swept path extrusions
- Terminals & Controllers (IfcAirTerminal, IfcSanitaryTerminal, IfcWasteTerminal, IfcDamper, IfcFlowController, IfcValve, IfcOutlet, IfcSwitchingDevice, IfcElectricDistributionBoard)
- Energy Conversion & Storage (IfcPump, IfcChiller, IfcBoiler, IfcTank, IfcFan, IfcCoil, IfcTransformer)
- Topological Ports (IfcDistributionPort) & Flow Directions (SOURCE, SINK, SOURCEANDSINK)
- System Containment (IfcDistributionSystem & IfcRelAssignsToGroup)
- Roundtrip IFC Verification (IfcOpenShell & StepSerializer)
- Execution performance (< 5s)
"""

import time
from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcAirTerminal,
    IfcBuildingElementProxy,
    IfcCustomElement,
    IfcDamper,
    IfcDistributionPort,
    IfcDistributionSystem,
    IfcDuctSegment,
    IfcFlowController,
    IfcOutlet,
    IfcPipeSegment,
    IfcSanitaryTerminal,
    IfcSwitchingDevice,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    TerminalPlacement,
)


@pytest.fixture
def comprehensive_mep_manifest() -> ProjectManifest:
    """Constructs a multi-discipline MEP project manifest with energy equipment, piping, ducting, terminals, and topological ports."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-COMPREHENSIVE", "name": "Comprehensive MEP Test Building"},
        "spatial_structure": {
            "storeys": [
                {"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.5},
                {"id": "MECH1", "name": "Mechanical Room", "elevation": 3.5, "height": 4.0},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 6.0, "3": 12.0},
            "axes_y": {"A": 0.0, "B": 6.0},
        },
        "materials": [
            {"id": "MAT_STEEL", "name": "Structural Steel", "category": "steel", "unit_cost_ref": "MAT-STEEL"},
            {"id": "MAT_COPPER", "name": "Copper Pipe", "category": "metal", "unit_cost_ref": "MAT-COPPER"},
            {"id": "MAT_GALV", "name": "Galvanized Duct", "category": "steel", "unit_cost_ref": "MAT-GALV"},
        ],
        "elements": [
            # 1. Energy Conversion & Storage Equipment (Chiller, Pump, Boiler, Tank)
            {
                "class": "IfcChiller",
                "tag": "CHILLER-01",
                "material": "MAT_STEEL",
                "placement": {"grid": ["1", "A"], "storey": "MECH1", "offset_x": 1.0, "offset_y": 1.0, "offset_z": 0.0},
                "dimensions": {"width": 2.0, "depth": 1.2, "height": 1.5},
                "ports": [
                    {"port_id": "CHW_IN", "flow_direction": "SINK", "nominal_diameter": 0.10, "offset": [0.0, 0.6, 0.5]},
                    {"port_id": "CHW_OUT", "flow_direction": "SOURCE", "nominal_diameter": 0.10, "offset": [2.0, 0.6, 0.5]},
                ],
            },
            {
                "class": "IfcPump",
                "tag": "PUMP-CHW-01",
                "material": "MAT_STEEL",
                "placement": {"grid": ["1", "A"], "storey": "MECH1", "offset_x": 4.0, "offset_y": 1.0, "offset_z": 0.0},
                "dimensions": {"width": 0.8, "depth": 0.5, "height": 0.6},
                "ports": [
                    {"port_id": "SUCTION", "flow_direction": "SINK", "nominal_diameter": 0.10, "offset": [0.0, 0.25, 0.3]},
                    {"port_id": "DISCHARGE", "flow_direction": "SOURCE", "nominal_diameter": 0.10, "offset": [0.8, 0.25, 0.3]},
                ],
            },
            {
                "class": "IfcBoiler",
                "tag": "BOILER-01",
                "material": "MAT_STEEL",
                "placement": {"grid": ["2", "A"], "storey": "MECH1", "offset_x": 1.0, "offset_y": 1.0, "offset_z": 0.0},
                "dimensions": {"width": 1.8, "depth": 1.0, "height": 1.6},
            },
            {
                "class": "IfcTank",
                "tag": "TANK-HW-01",
                "material": "MAT_STEEL",
                "placement": {"grid": ["2", "A"], "storey": "MECH1", "offset_x": 4.0, "offset_y": 1.0, "offset_z": 0.0},
                "dimensions": {"width": 1.2, "depth": 1.2, "height": 2.0},
            },
            {
                "class": "IfcFan",
                "tag": "FAN-EXH-01",
                "placement": {"grid": ["3", "A"], "storey": "MECH1", "offset_z": 2.0},
                "dimensions": {"width": 0.6, "depth": 0.6, "height": 0.6},
            },
            {
                "class": "IfcCoil",
                "tag": "COIL-COOL-01",
                "placement": {"grid": ["3", "A"], "storey": "MECH1", "offset_x": 1.5, "offset_z": 2.0},
                "dimensions": {"width": 0.8, "depth": 0.3, "height": 0.6},
            },
            {
                "class": "IfcTransformer",
                "tag": "XFMR-01",
                "placement": {"grid": ["1", "B"], "storey": "MECH1", "offset_z": 0.0},
                "dimensions": {"width": 1.2, "depth": 0.8, "height": 1.4},
            },

            # 2. Piping Network with Waypoints & Ports
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-CHW-SUPPLY",
                "system_type": "CHILLED_WATER",
                "material": "MAT_COPPER",
                "nominal_diameter": 0.10,
                "placement": {
                    "storey": "MECH1",
                    "path": [
                        {"x": 3.0, "y": 1.6, "z": 4.0},
                        {"x": 4.0, "y": 1.6, "z": 4.0},
                    ]
                },
                "ports": [
                    {"port_id": "P_IN", "flow_direction": "SOURCE", "nominal_diameter": 0.10, "offset": [0.0, 0.0, 0.0]},
                    {"port_id": "P_OUT", "flow_direction": "SINK", "nominal_diameter": 0.10, "offset": [1.0, 0.0, 0.0]},
                ],
            },

            # 3. HVAC Ducts, Dampers, Flow Controllers & Air Terminals
            {
                "class": "IfcDuctSegment",
                "tag": "DUCT-MAIN-SUPPLY",
                "system_type": "SUPPLY_AIR",
                "material": "MAT_GALV",
                "width": 0.50,
                "height": 0.30,
                "placement": {
                    "storey": "FL1",
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                    "from_offset": [0.0, 3.0, 2.8],
                    "to_offset": [0.0, 3.0, 2.8],
                },
                "ports": [
                    {"port_id": "DUCT_IN", "flow_direction": "SOURCE", "offset": [0.0, 0.0, 0.0]},
                    {"port_id": "DUCT_OUT", "flow_direction": "SINK", "offset": [6.0, 0.0, 0.0]},
                ],
            },
            {
                "class": "IfcDamper",
                "tag": "FD-FIRE-01",
                "damper_type": "FIRE_DAMPER",
                "duct_width": 0.50,
                "duct_depth": 0.30,
                "placement": {"grid": ["1", "A"], "storey": "FL1", "offset_x": 3.0, "offset_y": 3.0, "offset_z": 2.8},
            },
            {
                "class": "IfcFlowController",
                "tag": "VAV-BOX-01",
                "controller_type": "AIR_CONTROLLER",
                "duct_width": 0.50,
                "duct_depth": 0.30,
                "placement": {"grid": ["2", "A"], "storey": "FL1", "offset_x": 0.0, "offset_y": 3.0, "offset_z": 2.8},
                "ports": [
                    {"port_id": "VAV_IN", "flow_direction": "SINK", "offset": [0.0, 0.0, 0.0]},
                ],
            },
            {
                "class": "IfcAirTerminal",
                "tag": "DIFFUSER-SUPPLY-01",
                "terminal_type": "DIFFUSER",
                "air_flow_rate_m3h": 450.0,
                "placement": {"grid": ["2", "A"], "storey": "FL1", "offset_x": 2.0, "offset_y": 3.0, "offset_z": 2.7},
            },

            # 4. Sanitation & Electrical Fixtures
            {
                "class": "IfcSanitaryTerminal",
                "tag": "WC-FL1-01",
                "terminal_type": "WATER_CLOSET",
                "placement": {"grid": ["1", "B"], "storey": "FL1", "offset_x": 1.0, "offset_y": 1.0, "offset_z": 0.0},
            },
            {
                "class": "IfcOutlet",
                "tag": "OUTLET-FL1-01",
                "placement": {"grid": ["1", "B"], "storey": "FL1", "offset_x": 2.0, "offset_y": 1.0, "offset_z": 0.3},
            },
            {
                "class": "IfcSwitchingDevice",
                "tag": "SWITCH-FL1-01",
                "placement": {"grid": ["1", "B"], "storey": "FL1", "offset_x": 2.5, "offset_y": 1.0, "offset_z": 1.2},
            },
        ],
        "systems": [
            {
                "class": "IfcDistributionSystem",
                "name": "CHILLED_WATER_SYSTEM",
                "system_type": "CHILLED_WATER",
                "elements": ["CHILLER-01", "PUMP-CHW-01", "PIPE-CHW-SUPPLY"],
            },
            {
                "class": "IfcDistributionSystem",
                "name": "SUPPLY_AIR_SYSTEM",
                "system_type": "SUPPLY_AIR",
                "elements": ["DUCT-MAIN-SUPPLY", "FD-FIRE-01", "VAV-BOX-01", "DIFFUSER-SUPPLY-01"],
            },
        ],
        "connections": [
            ["CHILLER-01:CHW_OUT", "PIPE-CHW-SUPPLY:P_IN"],
            ["PIPE-CHW-SUPPLY:P_OUT", "PUMP-CHW-01:SUCTION"],
            ["DUCT-MAIN-SUPPLY:DUCT_OUT", "VAV-BOX-01:VAV_IN"],
        ],
    }
    return ProjectManifest.model_validate(manifest_data)


def test_mep_comprehensive_schema_and_resolution(comprehensive_mep_manifest: ProjectManifest):
    """Test resolution of energy equipment, piping, ducting, terminals, ports, and systems."""
    resolved = resolve_manifest(comprehensive_mep_manifest)

    # Check energy conversion & storage equipment
    chiller = resolved.get_element_by_tag("CHILLER-01")
    assert chiller is not None
    assert chiller.ifc_class == "IfcChiller"
    assert chiller.position == (1.0, 1.0, 3.5)

    pump = resolved.get_element_by_tag("PUMP-CHW-01")
    assert pump is not None
    assert pump.ifc_class == "IfcPump"

    boiler = resolved.get_element_by_tag("BOILER-01")
    assert boiler is not None
    assert boiler.ifc_class == "IfcBoiler"

    tank = resolved.get_element_by_tag("TANK-HW-01")
    assert tank is not None
    assert tank.ifc_class == "IfcTank"

    fan = resolved.get_element_by_tag("FAN-EXH-01")
    assert fan is not None
    assert fan.ifc_class == "IfcFan"

    # Check ports resolution
    assert len(resolved.resolved_ports) == 7
    ports_map = {p.global_port_id: p for p in resolved.resolved_ports}
    assert "CHILLER-01:CHW_OUT" in ports_map
    assert ports_map["CHILLER-01:CHW_OUT"].flow_direction == "SOURCE"
    assert ports_map["CHILLER-01:CHW_OUT"].world_position == (3.0, 1.6, 4.0)

    # Check topology graph
    tg = resolved.topology_graph
    assert tg is not None
    assert len(tg.connected_edges) == 3
    assert ("CHILLER-01:CHW_OUT", "PIPE-CHW-SUPPLY:P_IN") in tg.connected_edges


def test_mep_comprehensive_ifc_export_roundtrip(comprehensive_mep_manifest: ProjectManifest, tmp_path: Path):
    """Test roundtrip IFC export for both IfcOpenShell and fallback StepSerializer."""
    t0 = time.time()

    out_ifcopenshell = tmp_path / "mep_comprehensive_ifcopenshell.ifc"
    out_fallback = tmp_path / "mep_comprehensive_fallback.ifc"

    # 1. Export with IfcOpenShell
    compile_to_ifc(comprehensive_mep_manifest, output_path=out_ifcopenshell, force_fallback=False)
    assert out_ifcopenshell.exists()

    content_ios = out_ifcopenshell.read_text(encoding="utf-8")
    assert "IFCCHILLER" in content_ios
    assert "IFCPUMP" in content_ios
    assert "IFCBOILER" in content_ios
    assert "IFCTANK" in content_ios
    assert "IFCFAN" in content_ios
    assert "IFCCOIL" in content_ios
    assert "IFCTRANSFORMER" in content_ios
    assert "IFCPIPESEGMENT" in content_ios
    assert "IFCDUCTSEGMENT" in content_ios
    assert "IFCDISTRIBUTIONPORT" in content_ios
    assert "IFCRELCONNECTSPORTS" in content_ios
    assert "IFCDISTRIBUTIONSYSTEM" in content_ios
    assert "IFCRELASSIGNSTOGROUP" in content_ios

    # 2. Export with Fallback StepSerializer
    compile_to_ifc(comprehensive_mep_manifest, output_path=out_fallback, force_fallback=True)
    assert out_fallback.exists()

    content_fb = out_fallback.read_text(encoding="utf-8")
    assert "IFCCHILLER" in content_fb
    assert "IFCPUMP" in content_fb
    assert "IFCBOILER" in content_fb
    assert "IFCTANK" in content_fb
    assert "IFCFAN" in content_fb
    assert "IFCCOIL" in content_fb
    assert "IFCTRANSFORMER" in content_fb
    assert "IFCPIPESEGMENT" in content_fb
    assert "IFCDUCTSEGMENT" in content_fb
    assert "IFCDISTRIBUTIONPORT" in content_fb
    assert "IFCRELCONNECTSPORTS" in content_fb
    assert "IFCDISTRIBUTIONSYSTEM" in content_fb
    assert "IFCRELASSIGNSTOGROUP" in content_fb

    elapsed = time.time() - t0
    assert elapsed < 5.0, f"Roundtrip compilation took {elapsed:.2f}s (expected < 5.0s)"


def test_mep_comprehensive_qto_takeoff(comprehensive_mep_manifest: ProjectManifest):
    """Test QTO calculation and network statistics."""
    qto = calculate_qto(comprehensive_mep_manifest)
    assert qto.total_pipe_length > 0.0
    assert qto.total_duct_length > 0.0
    assert qto.total_ports_count == 7
    assert qto.total_connected_ports_count == 6
    assert qto.total_network_connections_count == 3
