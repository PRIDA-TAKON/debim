"""
Unit tests for Port-based System Topology (IfcDistributionPort & Connection Graphs)
"""

from pathlib import Path
import pytest
from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    IfcAirTerminal,
    IfcDistributionPort,
    IfcDuctSegment,
    IfcPipeSegment,
    IfcSanitaryTerminal,
    ProjectManifest,
)
from debim.viewer import generate_viewer_html


@pytest.fixture
def mep_topology_manifest() -> ProjectManifest:
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-TOPOLOGY", "name": "MEP Topology Test Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.5}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 4.0},
        },
        "materials": [
            {"id": "MAT_PPR", "name": "PPR Pipe", "category": "plastic", "unit_cost_ref": "MAT-PPR"},
            {"id": "MAT_CERAMIC", "name": "Ceramic", "category": "ceramic", "unit_cost_ref": "MAT-SAN"},
            {"id": "MAT_GALV", "name": "Galvanized Steel", "category": "steel", "unit_cost_ref": "MAT-GALV"},
        ],
        "elements": [
            {
                "class": "IfcSanitaryTerminal",
                "tag": "WC-01",
                "terminal_type": "WATER_CLOSET",
                "material": "MAT_CERAMIC",
                "placement": {"grid": ["1", "A"], "storey": "L1", "offset_z": 0.0},
                "ports": [
                    {"port_id": "CW_IN", "flow_direction": "SINK", "nominal_diameter": 0.02, "offset": [0.2, 0.0, 0.4]},
                    {"port_id": "WASTE_OUT", "flow_direction": "SOURCE", "nominal_diameter": 0.10, "offset": [0.0, 0.0, 0.1]},
                ],
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-CW-01",
                "system_type": "COLD_WATER",
                "material": "MAT_PPR",
                "nominal_diameter": 0.02,
                "placement": {
                    "storey": "L1",
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                    "from_offset": [0.2, 0.0, 0.4],
                    "to_offset": [0.0, 0.0, 0.4],
                },
                "ports": [
                    {"port_id": "INLET", "flow_direction": "SOURCE", "nominal_diameter": 0.02, "offset": [0.0, 0.0, 0.0]},
                    {"port_id": "OUTLET", "flow_direction": "SINK", "nominal_diameter": 0.02, "offset": [3.8, 0.0, 0.0]},
                ],
            },
            {
                "class": "IfcDuctSegment",
                "tag": "DUCT-01",
                "system_type": "SUPPLY_AIR",
                "material": "MAT_GALV",
                "width": 0.30,
                "height": 0.20,
                "placement": {
                    "storey": "L1",
                    "from_grid": ["1", "B"],
                    "to_grid": ["2", "B"],
                    "from_offset": [0.0, 0.0, 2.8],
                    "to_offset": [0.0, 0.0, 2.8],
                },
                "ports": [
                    {"port_id": "PORT_A", "flow_direction": "SOURCE", "offset": [0.0, 0.0, 0.0]},
                    {"port_id": "PORT_B", "flow_direction": "SINK", "offset": [4.0, 0.0, 0.0]},
                ],
            },
            {
                "class": "IfcAirTerminal",
                "tag": "DIFFUSER-01",
                "terminal_type": "DIFFUSER",
                "material": "MAT_GALV",
                "placement": {"grid": ["2", "B"], "storey": "L1", "offset_z": 2.8},
                "ports": [
                    {"port_id": "NECK", "flow_direction": "SINK", "offset": [0.0, 0.0, 0.0]},
                ],
            },
        ],
        "connections": [
            ["PIPE-CW-01:INLET", "WC-01:CW_IN"],
            ["DUCT-01:PORT_B", "DIFFUSER-01:NECK"],
        ],
    }
    return ProjectManifest.model_validate(manifest_data)


def test_schema_port_declaration(mep_topology_manifest: ProjectManifest):
    """Test Pydantic v2 schema validation for IfcDistributionPort and top-level connections."""
    wc = mep_topology_manifest.elements[0]
    assert isinstance(wc, IfcSanitaryTerminal)
    assert len(wc.ports) == 2
    assert wc.ports[0].port_id == "CW_IN"
    assert wc.ports[0].flow_direction == "SINK"
    assert wc.ports[0].nominal_diameter == 0.02

    pipe = mep_topology_manifest.elements[1]
    assert isinstance(pipe, IfcPipeSegment)
    assert len(pipe.ports) == 2

    assert len(mep_topology_manifest.connections) == 2
    assert mep_topology_manifest.connections[0] == ("PIPE-CW-01:INLET", "WC-01:CW_IN")


def test_resolver_port_coordinates_and_graph(mep_topology_manifest: ProjectManifest):
    """Test 3D world position resolution for ports and network connection graph construction."""
    resolved = resolve_manifest(mep_topology_manifest)

    assert len(resolved.resolved_ports) == 7
    ports_by_id = {p.global_port_id: p for p in resolved.resolved_ports}

    assert "WC-01:CW_IN" in ports_by_id
    assert ports_by_id["WC-01:CW_IN"].world_position == (0.2, 0.0, 0.4)

    assert "PIPE-CW-01:INLET" in ports_by_id
    assert ports_by_id["PIPE-CW-01:INLET"].world_position == (0.2, 0.0, 0.4)

    tg = resolved.topology_graph
    assert tg is not None
    assert len(tg.connected_edges) == 2
    assert ("PIPE-CW-01:INLET", "WC-01:CW_IN") in tg.connected_edges
    assert ("DUCT-01:PORT_B", "DIFFUSER-01:NECK") in tg.connected_edges

    # Check adjacency list
    assert "WC-01:CW_IN" in tg.adjacency["PIPE-CW-01:INLET"]
    assert "PIPE-CW-01:INLET" in tg.adjacency["WC-01:CW_IN"]

    # Check dead ends
    assert "WC-01:WASTE_OUT" in tg.dead_ends
    assert "PIPE-CW-01:OUTLET" in tg.dead_ends
    assert "DUCT-01:PORT_A" in tg.dead_ends


def test_qto_network_analytics(mep_topology_manifest: ProjectManifest):
    """Test QTO network continuity analytics and connected component statistics."""
    qto = calculate_qto(mep_topology_manifest)

    assert qto.total_ports_count == 7
    assert qto.total_connected_ports_count == 4
    assert qto.total_dead_end_ports_count == 3
    assert qto.total_network_connections_count == 2
    assert pytest.approx(qto.total_connected_path_length, abs=1e-3) == 0.0


def test_ifc_export_topology_relationships(mep_topology_manifest: ProjectManifest, tmp_path: Path):
    """Test valid IFC4 STEP export containing IfcDistributionPort and IfcRelConnectsPorts."""
    out_ifcopenshell = tmp_path / "model_ifcopenshell.ifc"
    out_fallback = tmp_path / "model_fallback.ifc"

    compile_to_ifc(mep_topology_manifest, output_path=out_ifcopenshell, force_fallback=False)
    compile_to_ifc(mep_topology_manifest, output_path=out_fallback, force_fallback=True)

    for out_p in [out_ifcopenshell, out_fallback]:
        content = out_p.read_text(encoding="utf-8")
        assert "IFCDISTRIBUTIONPORT" in content
        assert "IFCRELCONNECTSPORTTOELEMENT" in content
        assert "IFCRELCONNECTSPORTS" in content


def test_viewer_topology_rendering(mep_topology_manifest: ProjectManifest):
    """Test viewer HTML generation for 3D port markers and dashed flow lines."""
    html = generate_viewer_html(mep_topology_manifest)

    assert "IfcDistributionPort" in html
    assert "IfcRelConnectsPorts" in html
    assert "ports" in html
    assert "topology_connections" in html
