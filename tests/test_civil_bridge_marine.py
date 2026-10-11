"""
Unit test suite for IFC4.3 Civil Bridge Components & Marine Infrastructure Entities:
IfcBridgePart, IfcBearing, IfcMarineFacility, IfcMarinePart.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.bsdd import validate_manifest_psets
from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcBearing,
    IfcBridge,
    IfcBridgePart,
    IfcMarineFacility,
    IfcMarinePart,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.schema_registry import SchemaEntityRegistry
from debim.viewer import generate_viewer_html


def test_civil_bridge_marine_schema_validation():
    """Test Pydantic v2 schema validation for IfcBridgePart, IfcBearing, IfcMarineFacility, IfcMarinePart."""
    # 1. BridgePart
    bp = IfcBridgePart(
        tag="BP-DECK-01",
        bridge="BRIDGE-01",
        predefined_type="DECK",
        length=50.0,
        width=12.0,
        height=0.45,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert bp.class_ == "IfcBridgePart"
    assert bp.tag == "BP-DECK-01"
    assert bp.predefined_type == "DECK"
    assert bp.length == 50.0

    # 2. Bearing
    brg = IfcBearing(
        tag="BRG-01",
        bridge="BRIDGE-01",
        bridge_part="BP-DECK-01",
        predefined_type="ELASTOMERIC",
        width=0.60,
        depth=0.60,
        height=0.18,
        load_capacity_kN=2500.0,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert brg.class_ == "IfcBearing"
    assert brg.predefined_type == "ELASTOMERIC"
    assert brg.load_capacity_kn == 2500.0

    # 3. MarineFacility
    mf = IfcMarineFacility(
        tag="PORT-BANGKOK-01",
        name="Bangkok Commercial Container Port",
        predefined_type="PORT",
        surface_area=120000.0,
        water_depth=16.5,
        quay_length=600.0,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert mf.class_ == "IfcMarineFacility"
    assert mf.predefined_type == "PORT"
    assert mf.surface_area == 120000.0
    assert mf.water_depth == 16.5

    # 4. MarinePart
    mp = IfcMarinePart(
        tag="QUAY-BERTH-01",
        marine_facility="PORT-BANGKOK-01",
        predefined_type="QUAY",
        length=300.0,
        width=25.0,
        depth=15.0,
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )
    assert mp.class_ == "IfcMarinePart"
    assert mp.predefined_type == "QUAY"
    assert mp.length == 300.0


def test_spatial_containment_hierarchy():
    """Verify spatial hierarchy containment: IfcProject -> IfcSite -> IfcBridge / IfcMarineFacility -> IfcBridgePart / IfcMarinePart."""
    reg = SchemaEntityRegistry("IFC4X3")

    # Site inside Project
    assert reg.validate_spatial_containment("IfcSite", "IfcProject")

    # Bridge & MarineFacility inside Site
    assert reg.validate_spatial_containment("IfcBridge", "IfcSite")
    assert reg.validate_spatial_containment("IfcMarineFacility", "IfcSite")

    # BridgePart inside Bridge
    assert reg.validate_spatial_containment("IfcBridgePart", "IfcBridge")

    # Bearing inside BridgePart or Bridge
    assert reg.validate_spatial_containment("IfcBearing", "IfcBridgePart")
    assert reg.validate_spatial_containment("IfcBearing", "IfcBridge")

    # MarinePart inside MarineFacility
    assert reg.validate_spatial_containment("IfcMarinePart", "IfcMarineFacility")


def test_civil_bridge_marine_resolution_and_qto():
    """Test 3D spatial resolution and QTO calculations for advanced bridge and marine elements."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-BRIDGE-MARINE-01", name="Bridge & Port Facility"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[
            {"id": "MAT_CONC", "name": "Reinforced Concrete", "category": "concrete", "unit_cost_ref": "BRIDGE-SUBSTRUCTURE"},
            {"id": "MAT_STEEL", "name": "Structural Steel", "category": "steel", "unit_cost_ref": "BRIDGE-BEARING"},
        ],
        elements=[
            IfcBridge(
                tag="BRIDGE-01",
                material="MAT_CONC",
                span_length=100.0,
                deck_width=15.0,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBridgePart(
                tag="BP-PIER-01",
                bridge="BRIDGE-01",
                material="MAT_CONC",
                predefined_type="PIER",
                length=15.0,
                width=3.0,
                height=8.0,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
            IfcBearing(
                tag="BRG-01",
                bridge="BRIDGE-01",
                bridge_part="BP-PIER-01",
                material="MAT_STEEL",
                predefined_type="ELASTOMERIC",
                width=0.8,
                depth=0.8,
                height=0.2,
                load_capacity_kN=3000.0,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
            IfcMarineFacility(
                tag="PORT-01",
                predefined_type="PORT",
                surface_area=25000.0,
                water_depth=14.0,
                quay_length=200.0,
                placement={"storey": "GROUND", "grid": ["1", "B"]},
            ),
            IfcMarinePart(
                tag="QUAY-01",
                marine_facility="PORT-01",
                material="MAT_CONC",
                predefined_type="QUAY",
                length=200.0,
                width=20.0,
                height=12.0,
                placement={"storey": "GROUND", "from_grid": ["1", "B"], "to_grid": ["2", "B"]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.bridges) == 1
    assert len(resolved.bridge_parts) == 1
    assert len(resolved.bearings) == 1
    assert len(resolved.marine_facilities) == 1
    assert len(resolved.marine_parts) == 1

    rbp = resolved.bridge_parts[0]
    assert rbp.tag == "BP-PIER-01"
    assert rbp.volume == 15.0 * 3.0 * 8.0  # 360 m3

    rbrg = resolved.bearings[0]
    assert rbrg.tag == "BRG-01"
    assert rbrg.load_capacity_kn == 3000.0

    rmf = resolved.marine_facilities[0]
    assert rmf.tag == "PORT-01"
    assert rmf.surface_area == 25000.0

    rmp = resolved.marine_parts[0]
    assert rmp.tag == "QUAY-01"
    assert rmp.volume == 200.0 * 20.0 * 12.0  # 48000 m3

    # QTO
    qto = calculate_qto(resolved)
    assert qto.total_bridge_part_volume == 360.0
    assert qto.total_bearing_count == 1
    assert qto.total_marine_facility_area == 25000.0
    assert qto.total_marine_part_volume == 48000.0


def test_cost_and_bsdd_pset_validation(tmp_path: Path):
    """Test cost estimation and bSDD Property Set validation for bridge and marine entities."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-COST-03", name="Bridge Marine Cost Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 50.0}, axes_y={"A": 0.0, "B": 20.0}),
        materials=[
            {"id": "MAT_CONC", "name": "Concrete", "category": "concrete", "unit_cost_ref": "BRIDGE-SUBSTRUCTURE"}
        ],
        elements=[
            IfcBridgePart(
                tag="BP-01",
                material="MAT_CONC",
                predefined_type="DECK",
                length=50.0,
                width=10.0,
                height=0.5,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBearing(
                tag="BRG-01",
                predefined_type="BRIDGEBEARING",
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
            IfcMarineFacility(
                tag="PORT-01",
                predefined_type="PORT",
                surface_area=5000.0,
                placement={"storey": "GROUND", "grid": ["1", "B"]},
            ),
            IfcMarinePart(
                tag="QUAY-01",
                material="MAT_CONC",
                predefined_type="QUAY",
                length=50.0,
                width=10.0,
                height=5.0,
                placement={"storey": "GROUND", "from_grid": ["1", "B"], "to_grid": ["2", "B"]},
            ),
        ],
    )

    qto = calculate_qto(manifest)
    tpl_path = tmp_path / "prices.yaml"
    generate_cost_template(manifest, output_path=tpl_path)

    catalog = load_price_catalog(tpl_path)
    assert "BRIDGE-SUBSTRUCTURE" in catalog.items
    assert "BRIDGE-BEARING" in catalog.items
    assert "MARINE-FACILITY" in catalog.items
    assert "MARINE-QUAY" in catalog.items

    catalog.items["BRIDGE-SUBSTRUCTURE"].material_cost = 3500.0
    catalog.items["BRIDGE-BEARING"].material_cost = 15000.0
    catalog.items["MARINE-FACILITY"].material_cost = 200.0
    catalog.items["MARINE-QUAY"].material_cost = 4000.0

    estimate = estimate_cost(qto, catalog, manifest)
    codes = [item.code for item in estimate.line_items]
    assert "BRIDGE-SUBSTRUCTURE" in codes
    assert "BRIDGE-BEARING" in codes
    assert "MARINE-FACILITY" in codes
    assert "MARINE-QUAY" in codes
    assert estimate.grand_total > 0.0

    # bSDD pset validation
    pset_results = validate_manifest_psets(manifest)
    assert isinstance(pset_results, list)


def test_ifc_export_and_viewer_generation(tmp_path: Path):
    """Test standard IFC compilation and 3D HTML viewer generation for bridge and marine elements."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-EXPORT-04", name="Bridge Marine Export Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 80.0}, axes_y={"A": 0.0, "B": 30.0}),
        materials=[
            {"id": "MAT_CONC", "name": "Concrete", "category": "concrete", "unit_cost_ref": "C1"}
        ],
        elements=[
            IfcBridge(
                tag="BRIDGE-01",
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBridgePart(
                tag="BP-01",
                bridge="BRIDGE-01",
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcBearing(
                tag="BRG-01",
                bridge="BRIDGE-01",
                bridge_part="BP-01",
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
            IfcMarineFacility(
                tag="PORT-01",
                placement={"storey": "GROUND", "grid": ["1", "B"]},
            ),
            IfcMarinePart(
                tag="QUAY-01",
                marine_facility="PORT-01",
                placement={"storey": "GROUND", "from_grid": ["1", "B"], "to_grid": ["2", "B"]},
            ),
        ],
    )

    # 1. Standard compilation
    ifc_file = tmp_path / "bridge_marine.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    # 2. STEP Fallback compilation
    step_file = tmp_path / "bridge_marine_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    content = step_file.read_text(encoding="utf-8")
    assert "IFCBRIDGEPART" in content
    assert "IFCBEARING" in content
    assert "IFCMARINEFACILITY" in content
    assert "IFCMARINEPART" in content

    # 3. 3D Viewer HTML
    html = generate_viewer_html(manifest)
    assert "IfcBridgePart" in html
    assert "IfcBearing" in html
    assert "IfcMarineFacility" in html
    assert "IfcMarinePart" in html
    assert "BP-01" in html
    assert "BRG-01" in html
    assert "PORT-01" in html
    assert "QUAY-01" in html
