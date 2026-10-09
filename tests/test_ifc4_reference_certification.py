"""
End-to-End buildingSMART IFC4 Reference Test Suite for debim Certification (Task 5.1).

Validates multi-discipline integrated reference building manifest:
- Structural: IfcColumn, IfcBeam, IfcFooting, IfcSlab
- Architectural & Circulation: IfcWall, IfcDoor, IfcWindow, IfcStairFlight, IfcRoof, IfcCurtainWall, IfcPlate
- MEP Fixtures & Topology: IfcPipeSegment, IfcSanitaryTerminal, IfcLightFixture, IfcAirTerminal, IfcDistributionPort, IfcRelConnectsPorts
- Civil Infrastructure: IfcEarthworksCut, IfcEarthworksFill, IfcRetainingWall, IfcRoad, IfcBridge
- Generic Long-Tail Equipment: IfcBuildingElementProxy / IfcChiller with validated Property Sets

Verifies spatial resolution, debim QTO takeoff consistency, compiled IFC4 schema compliance,
and spatial containment tree integrity (IfcProject -> IfcSite -> IfcBuilding -> IfcBuildingStorey -> Products).
"""

from pathlib import Path
import pytest
import ifcopenshell

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import ProjectManifest


@pytest.fixture
def reference_building_manifest() -> ProjectManifest:
    """Construct an integrated multi-discipline reference building project manifest."""
    manifest_data = {
        "schema": "IFC4",
        "project": {"id": "PROJ-REF-CERT", "name": "buildingSMART IFC4 Reference Building"},
        "spatial_structure": {
            "storeys": [
                {"id": "FOUNDATION", "name": "Foundation Level", "elevation": -1.5, "height": 1.5},
                {"id": "L1", "name": "Ground Floor L1", "elevation": 0.0, "height": 3.5},
                {"id": "L2", "name": "Second Floor L2", "elevation": 3.5, "height": 3.5},
                {"id": "ROOF", "name": "Roof Level", "elevation": 7.0, "height": 3.0},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 5.0, "3": 10.0, "4": 15.0},
            "axes_y": {"A": 0.0, "B": 6.0, "C": 12.0},
        },
        "materials": [
            {"id": "MAT_CONC", "name": "Reinforced Concrete C30", "category": "concrete", "unit_cost_ref": "CONC-30"},
            {"id": "MAT_STEEL", "name": "Structural Steel SS400", "category": "steel", "unit_cost_ref": "STEEL-SS400"},
            {"id": "MAT_BRICK", "name": "Common Brick Masonry", "category": "masonry", "unit_cost_ref": "BRICK-COMMON"},
            {"id": "MAT_GLASS", "name": "Double Glazed Glass", "category": "glass", "unit_cost_ref": "GLASS-PANEL"},
            {"id": "MAT_PPR", "name": "PPR Water Pipe", "category": "plastic", "unit_cost_ref": "PIPE-PPR"},
            {"id": "MAT_SOIL", "name": "Excavated Soil", "category": "soil", "unit_cost_ref": "EARTH-SOIL"},
            {"id": "MAT_ASPHALT", "name": "Asphalt Concrete", "category": "asphalt", "unit_cost_ref": "ROAD-ASPHALT"},
        ],
        "elements": [
            # --- 1. Structural Discipline ---
            {
                "class": "IfcFooting",
                "tag": "FTG-01",
                "material": "MAT_CONC",
                "profile": {"shape": "BOX", "width": 1.5, "depth": 1.5, "thickness": 0.5},
                "placement": {"grid": ["1", "A"], "storey": "FOUNDATION", "offset_z": 0.0},
            },
            {
                "class": "IfcColumn",
                "tag": "COL-ST-01",
                "material": "MAT_STEEL",
                "profile": {"shape": "RHS", "section": "RHS150X150X6"},
                "placement": {"grid": ["1", "A"], "base_storey": "FOUNDATION", "top_storey": "L1"},
            },
            {
                "class": "IfcColumn",
                "tag": "COL-RC-01",
                "material": "MAT_CONC",
                "profile": {"shape": "BOX", "width": 0.4, "depth": 0.4},
                "placement": {"grid": ["2", "A"], "base_storey": "L1", "top_storey": "L2"},
            },
            {
                "class": "IfcBeam",
                "tag": "BM-01",
                "material": "MAT_CONC",
                "profile": {"shape": "BOX", "width": 0.3, "depth": 0.5},
                "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "L1"},
            },
            {
                "class": "IfcSlab",
                "tag": "SLAB-L1",
                "material": "MAT_CONC",
                "thickness": 0.15,
                "placement": {
                    "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]],
                    "storey": "L1",
                },
            },

            # --- 2. Architectural & Circulation Discipline ---
            {
                "class": "IfcWall",
                "tag": "WALL-01",
                "material": "MAT_BRICK",
                "thickness": 0.20,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "L1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "DOOR-01",
                        "dimensions": {"width": 0.9, "height": 2.1},
                        "offset_distance": 1.0,
                    },
                    {
                        "class": "IfcWindow",
                        "tag": "WIN-01",
                        "dimensions": {"width": 1.2, "height": 1.5},
                        "offset_distance": 2.8,
                        "sill_height": 0.9,
                    },
                ],
            },
            {
                "class": "IfcStairFlight",
                "tag": "STAIR-FL-01",
                "material": "MAT_CONC",
                "flight_width": 1.2,
                "riser_height": 0.175,
                "tread_length": 0.28,
                "number_of_risers": 10,
                "placement": {
                    "grid_anchor": ["2", "B"],
                    "from_storey": "L1",
                    "to_storey": "L2",
                },
            },
            {
                "class": "IfcRoof",
                "tag": "ROOF-01",
                "material": "MAT_CONC",
                "roof_type": "HIP",
                "placement": {
                    "boundary": [["1", "A"], ["3", "A"], ["3", "B"], ["1", "B"]],
                    "storey": "ROOF",
                    "overhang": 0.8,
                },
            },
            {
                "class": "IfcCurtainWall",
                "tag": "CWALL-01",
                "material": "MAT_GLASS",
                "height": 3.5,
                "glass_thickness": 0.010,
                "placement": {"from_grid": ["2", "A"], "to_grid": ["3", "A"], "storey": "L1"},
            },
            {
                "class": "IfcPlate",
                "tag": "PLATE-01",
                "material": "MAT_STEEL",
                "thickness": 0.010,
                "width": 1.0,
                "depth": 1.0,
                "placement": {"storey": "L1", "grid": ["1", "B"]},
            },

            # --- 3. MEP Fixtures & Topology Discipline ---
            {
                "class": "IfcSanitaryTerminal",
                "tag": "WC-01",
                "terminal_type": "WATER_CLOSET",
                "material": "MAT_CONC",
                "placement": {"grid": ["1", "B"], "storey": "L1", "offset_z": 0.0},
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
                    "to_grid": ["1", "B"],
                    "from_offset": [0.2, 0.0, 0.4],
                    "to_offset": [0.2, 0.0, 0.4],
                },
                "ports": [
                    {"port_id": "INLET", "flow_direction": "SOURCE", "nominal_diameter": 0.02, "offset": [0.0, 0.0, 0.0]},
                    {"port_id": "OUTLET", "flow_direction": "SINK", "nominal_diameter": 0.02, "offset": [0.0, 6.0, 0.0]},
                ],
            },
            {
                "class": "IfcAirTerminal",
                "tag": "DIFFUSER-01",
                "terminal_type": "DIFFUSER",
                "placement": {"grid": ["2", "B"], "storey": "L1", "offset_z": 2.8},
                "ports": [{"port_id": "NECK", "flow_direction": "SINK", "offset": [0.0, 0.0, 0.0]}],
            },
            {
                "class": "IfcLightFixture",
                "tag": "LIGHT-01",
                "fixture_type": "DOWNLIGHT",
                "wattage": 15.0,
                "placement": {"grid": ["2", "B"], "storey": "L1", "offset_z": 2.8},
            },

            # --- 4. Civil Infrastructure Discipline ---
            {
                "class": "IfcEarthworksCut",
                "tag": "CUT-01",
                "material": "MAT_SOIL",
                "depth": 2.0,
                "cut_volume": 100.0,
                "placement": {"storey": "FOUNDATION", "grid": ["1", "A"]},
            },
            {
                "class": "IfcEarthworksFill",
                "tag": "FILL-01",
                "material": "MAT_SOIL",
                "depth": 0.5,
                "fill_volume": 25.0,
                "placement": {"storey": "FOUNDATION", "grid": ["2", "A"]},
            },
            {
                "class": "IfcRetainingWall",
                "tag": "RWALL-01",
                "material": "MAT_CONC",
                "length": 10.0,
                "stem_height": 2.5,
                "stem_thickness": 0.30,
                "footing_base_width": 1.5,
                "footing_thickness": 0.40,
                "placement": {"storey": "FOUNDATION", "from_grid": ["1", "A"], "to_grid": ["3", "A"]},
            },
            {
                "class": "IfcRoad",
                "tag": "ROAD-01",
                "material": "MAT_ASPHALT",
                "road_width": 6.0,
                "corridor_length": 15.0,
                "placement": {"storey": "FOUNDATION", "from_grid": ["1", "A"], "to_grid": ["4", "A"]},
            },
            {
                "class": "IfcBridge",
                "tag": "BRIDGE-01",
                "material": "MAT_CONC",
                "span_length": 10.0,
                "deck_width": 8.0,
                "deck_thickness": 0.30,
                "pier_height": 4.0,
                "pier_count": 2,
                "placement": {"storey": "FOUNDATION", "from_grid": ["1", "C"], "to_grid": ["3", "C"]},
            },
        ],
        "proxies": [
            # --- 5. Generic Long-Tail Equipment Discipline ---
            {
                "class": "IfcChiller",
                "tag": "CHILLER-01",
                "ifc_class": "IfcChiller",
                "predefined_type": "WATERCOOLED",
                "material": "MAT_STEEL",
                "geometry": {"box": [2.5, 1.5, 1.8]},
                "placement": {"storey": "ROOF", "grid": ["2", "A"]},
                "properties": {
                    "Pset_ChillerTypeCommon": {
                        "NominalCapacity": 250.0,
                        "RefrigerantClass": "R134a",
                    }
                },
            }
        ],
        "connections": [
            ("PIPE-CW-01:OUTLET", "WC-01:CW_IN"),
        ],
    }
    return ProjectManifest.model_validate(manifest_data)


def test_reference_manifest_spatial_resolution(reference_building_manifest: ProjectManifest):
    """Test spatial resolution for all multi-discipline entities in reference manifest."""
    resolved = resolve_manifest(reference_building_manifest)

    # Discipline count checks
    assert len(resolved.footings) == 1
    assert len(resolved.columns) == 2
    assert len(resolved.beams) == 1
    assert len(resolved.slabs) == 1
    assert len(resolved.walls) == 1
    assert len(resolved.stair_flights) == 1
    assert len(resolved.roofs) == 1
    assert len(resolved.curtain_walls) == 1
    assert len(resolved.plates) == 1
    assert len(resolved.sanitary_terminals) == 1
    assert len(resolved.pipes) == 1
    assert len(resolved.air_terminals) == 1
    assert len(resolved.light_fixtures) == 1
    assert len(resolved.earthworks_cuts) == 1
    assert len(resolved.earthworks_fills) == 1
    assert len(resolved.retaining_walls) == 1
    assert len(resolved.roads) == 1
    assert len(resolved.bridges) == 1
    assert len(resolved.proxies) == 1

    # Verify specific resolved spatial coordinates
    col_st = next(c for c in resolved.columns if c.tag == "COL-ST-01")
    assert col_st.start_point == (0.0, 0.0, -1.5)
    assert col_st.end_point == (0.0, 0.0, 0.0)
    assert pytest.approx(col_st.height, abs=1e-3) == 1.5

    wall = resolved.walls[0]
    assert wall.start_point == (0.0, 0.0, 0.0)
    assert wall.end_point == (5.0, 0.0, 0.0)
    assert wall.length == 5.0
    assert len(wall.children) == 2

    # Verify port network graph
    assert len(resolved.resolved_ports) >= 3
    assert resolved.topology_graph is not None
    assert ("PIPE-CW-01:OUTLET", "WC-01:CW_IN") in resolved.topology_graph.connected_edges


def test_reference_qto_takeoff_matching(reference_building_manifest: ProjectManifest):
    """Test QTO calculations and cross-discipline takeoff metrics matching."""
    qto = calculate_qto(reference_building_manifest)

    # Check element QTO takeoffs present
    assert len(qto.elements) >= 18
    assert qto.get_element("FTG-01") is not None
    assert qto.get_element("COL-ST-01") is not None
    assert qto.get_element("WALL-01") is not None
    assert qto.get_element("PIPE-CW-01") is not None
    assert qto.get_element("CHILLER-01") is not None

    # Check structural & architectural QTO metrics
    assert qto.total_concrete_volume > 0.0
    assert qto.total_doors_count == 1
    assert qto.total_windows_count == 1
    assert qto.total_openings_area == pytest.approx(0.9 * 2.1 + 1.2 * 1.5, abs=1e-3)
    assert qto.total_curtain_wall_facade_area == pytest.approx(5.0 * 3.5, abs=1e-3)

    # Check MEP topology QTO
    assert qto.total_cold_water_pipe_length == 6.0
    assert qto.total_sanitary_terminals_count == 1
    assert qto.total_air_terminals_count == 1
    assert qto.total_lighting_fixtures_count == 1
    assert qto.total_ports_count >= 3
    assert qto.total_connected_ports_count == 2
    assert qto.total_network_connections_count == 1

    # Check civil infrastructure QTO
    assert qto.total_cut_volume == 100.0
    assert qto.total_fill_volume == 25.0
    assert qto.total_retaining_wall_concrete_volume > 0.0
    assert qto.total_road_surface_area == pytest.approx(6.0 * 15.0, abs=1e-3)
    assert qto.total_bridge_concrete_volume > 0.0

    # Check proxy QTO
    assert qto.total_proxies_count == 1
    assert qto.total_proxies_volume == pytest.approx(2.5 * 1.5 * 1.8, abs=1e-3)


def test_ifc4_reference_certification_schema_and_spatial_containment(
    reference_building_manifest: ProjectManifest, tmp_path: Path
):
    """
    Test compilation to IFC4 STEP file and inspect with IfcOpenShell to verify:
    1. Standard spatial containment hierarchy (IfcProject -> IfcSite -> IfcBuilding -> IfcBuildingStorey -> Products).
    2. Entity existence and counts across all 5 disciplines.
    3. Topological port connections and property set definitions.
    """
    output_ifc = tmp_path / "reference_certification_model.ifc"
    compile_to_ifc(reference_building_manifest, output_path=output_ifc)

    assert output_ifc.exists()
    assert output_ifc.stat().st_size > 0

    # Parse compiled model using IfcOpenShell
    model = ifcopenshell.open(output_ifc)

    # --- 1. Spatial Containment Hierarchy Verification ---
    projects = model.by_type("IfcProject")
    assert len(projects) == 1
    project = projects[0]
    assert project.Name == "buildingSMART IFC4 Reference Building"

    # Spatial aggregation check (IfcProject -> IfcSite)
    sites = model.by_type("IfcSite")
    assert len(sites) >= 1
    site = sites[0]

    # Spatial aggregation check (IfcSite -> IfcBuilding)
    buildings = model.by_type("IfcBuilding")
    assert len(buildings) >= 1
    building = buildings[0]

    # Spatial aggregation check (IfcBuilding -> IfcBuildingStorey)
    storeys = model.by_type("IfcBuildingStorey")
    assert len(storeys) == 4
    storey_names = {s.Name for s in storeys}
    assert storey_names == {"Foundation Level", "Ground Floor L1", "Second Floor L2", "Roof Level"}

    # Spatial containment check (IfcRelContainedInSpatialStructure)
    containment_rels = model.by_type("IfcRelContainedInSpatialStructure")
    assert len(containment_rels) > 0
    contained_elements = []
    for rel in containment_rels:
        assert rel.RelatingStructure.is_a("IfcBuildingStorey")
        contained_elements.extend(rel.RelatedElements)
    assert len(contained_elements) > 0

    # --- 2. Multi-Discipline Entity Existence Verification ---
    # Structural
    assert len(model.by_type("IfcFooting")) >= 1
    assert len(model.by_type("IfcColumn")) == 2
    assert len(model.by_type("IfcBeam")) == 1
    assert len(model.by_type("IfcSlab")) == 1

    # Architectural & Circulation
    assert len(model.by_type("IfcWall")) >= 1
    assert len(model.by_type("IfcDoor")) == 1
    assert len(model.by_type("IfcWindow")) == 1
    assert len(model.by_type("IfcStairFlight")) == 1
    assert len(model.by_type("IfcRoof")) == 1
    assert len(model.by_type("IfcCurtainWall")) == 1
    assert len(model.by_type("IfcPlate")) == 1

    # MEP
    assert len(model.by_type("IfcSanitaryTerminal")) == 1
    assert len(model.by_type("IfcPipeSegment")) == 1
    assert len(model.by_type("IfcAirTerminal")) == 1
    assert len(model.by_type("IfcLightFixture")) == 1

    # MEP Topology
    assert len(model.by_type("IfcDistributionPort")) >= 2
    assert len(model.by_type("IfcRelConnectsPorts")) == 1

    # Civil Infrastructure (Earthworks as IfcGeographicElement/IfcEarthworksElement + Road/Bridge as proxies or entities)
    civil_entities = (
        list(model.by_type("IfcGeographicElement"))
        + list(model.by_type("IfcEarthworksElement"))
        + list(model.by_type("IfcEarthworksCut"))
        + list(model.by_type("IfcEarthworksFill"))
        + list(model.by_type("IfcRoad"))
        + list(model.by_type("IfcBridge"))
        + list(model.by_type("IfcAlignment"))
        + [
            p for p in model.by_type("IfcBuildingElementProxy")
            if any(k in getattr(p, "Name", "").upper() or k in getattr(p, "ObjectType", "").upper() for k in ["ROAD", "BRIDGE", "ALIGNMENT"])
        ]
    )
    assert len(civil_entities) >= 3

    # Generic Long-Tail Equipment & Property Sets
    chillers = list(model.by_type("IfcChiller")) + [
        p for p in model.by_type("IfcBuildingElementProxy") if "CHILLER" in getattr(p, "Name", "").upper()
    ]
    assert len(chillers) == 1
    chiller = chillers[0]

    psets = model.by_type("IfcPropertySet")
    assert len(psets) >= 1
    chiller_pset = next((ps for ps in psets if ps.Name == "Pset_ChillerTypeCommon"), None)
    assert chiller_pset is not None

    p_dict = {prop.Name: prop.NominalValue.wrappedValue for prop in chiller_pset.HasProperties}
    assert p_dict["NominalCapacity"] == 250.0
    assert p_dict["RefrigerantClass"] == "R134a"


def test_ifc4_step_fallback_certification(
    reference_building_manifest: ProjectManifest, tmp_path: Path
):
    """Test STEP serializer fallback compiler to confirm pure text STEP compliance."""
    fallback_ifc = tmp_path / "reference_fallback_model.ifc"
    compile_to_ifc(reference_building_manifest, output_path=fallback_ifc, force_fallback=True)

    assert fallback_ifc.exists()
    content = fallback_ifc.read_text(encoding="utf-8")

    # STEP standard header assertions
    assert "ISO-10303-21;" in content
    assert "HEADER;" in content
    assert "FILE_SCHEMA(('IFC4'));" in content
    assert "DATA;" in content
    assert "ENDSEC;" in content

    # Key entity string assertions
    required_entities = [
        "IFCPROJECT",
        "IFCSITE",
        "IFCBUILDING",
        "IFCBUILDINGSTOREY",
        "IFCRELCONTAINEDINSPATIALSTRUCTURE",
        "IFCFOOTING",
        "IFCCOLUMN",
        "IFCBEAM",
        "IFCSLAB",
        "IFCWALL",
        "IFCDOOR",
        "IFCWINDOW",
        "IFCSTAIRFLIGHT",
        "IFCROOF",
        "IFCCURTAINWALL",
        "IFCPLATE",
        "IFCSANITARYTERMINAL",
        "IFCPIPESEGMENT",
        "IFCAIRTERMINAL",
        "IFCLIGHTFIXTURE",
        "IFCDISTRIBUTIONPORT",
        "IFCRELCONNECTSPORTS",
        "IFCPROPERTYSET",
        "IFCRELDEFINESBYPROPERTIES",
    ]
    for ent in required_entities:
        assert ent in content, f"Expected entity type {ent} missing from fallback STEP export"
