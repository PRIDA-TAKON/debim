"""
Unit tests for debim Electrical & Lighting Fixtures (Task 2.5).
Validates IfcLightFixture, IfcOutlet, and IfcElectricDistributionBoard (IfcDistributionBoard)
schema parsing, spatial resolution, discipline layering, QTO calculations, price catalog matching,
IFC compilation, and 3D Web Viewer integration.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.schema import (
    Grids,
    IfcElectricDistributionBoard,
    IfcDistributionBoard,
    IfcLightFixture,
    IfcOutlet,
    IfcWall,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    TerminalDimensions,
    TerminalPlacement,
    WallPlacement,
)
from debim.resolver import (
    ResolvedDistributionBoard,
    ResolvedLightFixture,
    ResolvedOutlet,
    resolve_manifest,
)
from debim.qto import calculate_qto
from debim.cost import PriceCatalog, PriceItem, estimate_cost
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html


@pytest.fixture
def electrical_manifest() -> ProjectManifest:
    """Fixture providing a project manifest with electrical fixtures and distribution board."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-ELEC-01", name="Electrical Fixtures Test"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1_GROUND", name="Level 1 Ground", elevation=0.0, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0, "3": 10.0},
            axes_y={"A": 0.0, "B": 4.0, "C": 8.0},
        ),
        materials=[
            Material(
                id="MAT_ELEC",
                name="Electrical Equipment",
                category="electrical",
                unit_cost_ref="MAT-ELEC-EQ",
            ),
            Material(
                id="MAT_CONC",
                name="Concrete Wall",
                category="concrete",
                unit_cost_ref="MAT-CONC-01",
            ),
        ],
        elements=[
            # Host Wall
            IfcWall(
                tag="W-ELEC-01",
                material="MAT_CONC",
                thickness=0.20,
                height=3.0,
                placement=WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1_GROUND"),
            ),
            # 1. Light Fixtures
            IfcLightFixture(
                tag="LIGHT-DOWN-01",
                fixture_type="DOWNLIGHT",
                predefined_type="POINTSOURCE",
                material="MAT_ELEC",
                placement=TerminalPlacement(
                    grid=("1", "A"), storey="L1_GROUND", offset_x=2.5, offset_y=2.0, offset_z=2.8
                ),
                power_watts=18.0,
                luminous_flux_lumens=1600.0,
                color_temperature_kelvin=3000.0,
            ),
            IfcLightFixture(
                tag="LIGHT-SPOT-01",
                fixture_type="FLOODLIGHT",
                predefined_type="DIRECTIONSOURCE",
                material="MAT_ELEC",
                placement=TerminalPlacement(
                    grid=("2", "B"), storey="L1_GROUND", offset_x=0.0, offset_y=0.0, offset_z=3.0
                ),
                power_watts=50.0,
                luminous_flux_lumens=4500.0,
                color_temperature_kelvin=4000.0,
            ),
            IfcLightFixture(
                tag="LIGHT-EXIT-01",
                fixture_type="SECURITYLIGHTING",
                predefined_type="SECURITYLIGHTING",
                material="MAT_ELEC",
                placement=TerminalPlacement(
                    wall="W-ELEC-01", distance=4.5, side="INTERIOR", offset_z=2.4
                ),
                power_watts=5.0,
                luminous_flux_lumens=300.0,
                color_temperature_kelvin=6500.0,
            ),
            # 2. Outlets / Receptacles
            IfcOutlet(
                tag="OUT-DUPLEX-01",
                outlet_type="DUPLEX_GROUNDED",
                predefined_type="POWEROUTLET",
                material="MAT_ELEC",
                placement=TerminalPlacement(
                    wall="W-ELEC-01", distance=1.5, side="INTERIOR", standoff=0.01, offset_z=0.30
                ),
            ),
            IfcOutlet(
                tag="OUT-DATA-01",
                outlet_type="DATAOUTLET",
                predefined_type="DATAOUTLET",
                material="MAT_ELEC",
                placement=TerminalPlacement(
                    wall="W-ELEC-01", distance=3.0, side="INTERIOR", standoff=0.01, offset_z=0.30
                ),
            ),
            # 3. Electric Distribution Board
            IfcElectricDistributionBoard(
                tag="MDB-01",
                board_type="MDB",
                predefined_type="DISTRIBUTIONBOARD",
                material="MAT_ELEC",
                placement=TerminalPlacement(
                    grid=("1", "A"), storey="L1_GROUND", offset_x=0.5, offset_y=0.2, offset_z=1.50
                ),
                voltage=380.0,
                phases=3,
                main_breaker_rating_amperes=100.0,
                poles_count=36,
                dimensions=TerminalDimensions(width=0.60, depth=0.25, height=0.90),
            ),
            # 4. Consumer Unit (legacy class alias IfcDistributionBoard)
            IfcDistributionBoard(
                tag="CU-01",
                board_type="CONSUMER_UNIT",
                predefined_type="CONSUMERUNIT",
                material="MAT_ELEC",
                placement=TerminalPlacement(
                    wall="W-ELEC-01", distance=0.8, side="INTERIOR", offset_z=1.60
                ),
                voltage=220.0,
                phases=1,
                main_breaker_rating_amperes=50.0,
                poles_count=12,
            ),
        ],
    )


def test_electrical_schema_validation(electrical_manifest: ProjectManifest):
    """Test schema parsing and attribute validation for electrical models."""
    elem_map = {e.tag: e for e in electrical_manifest.elements}

    # Light Fixture
    light = elem_map["LIGHT-DOWN-01"]
    assert isinstance(light, IfcLightFixture)
    assert light.power_watts == 18.0
    assert light.wattage == 18.0
    assert light.luminous_flux_lumens == 1600.0
    assert light.color_temperature_kelvin == 3000.0
    assert light.predefined_type == "POINTSOURCE"

    # Outlet
    outlet = elem_map["OUT-DUPLEX-01"]
    assert isinstance(outlet, IfcOutlet)
    assert outlet.outlet_type == "DUPLEX_GROUNDED"
    assert outlet.predefined_type == "POWEROUTLET"

    data_out = elem_map["OUT-DATA-01"]
    assert isinstance(data_out, IfcOutlet)
    assert data_out.predefined_type == "DATAOUTLET"

    # Distribution Board
    mdb = elem_map["MDB-01"]
    assert isinstance(mdb, IfcElectricDistributionBoard)
    assert mdb.voltage == 380.0
    assert mdb.phases == 3
    assert mdb.main_breaker_rating_amperes == 100.0
    assert mdb.poles_count == 36
    assert mdb.circuits_count == 36
    assert mdb.predefined_type == "DISTRIBUTIONBOARD"

    cu = elem_map["CU-01"]
    assert isinstance(cu, IfcDistributionBoard)
    assert cu.voltage == 220.0
    assert cu.phases == 1
    assert cu.predefined_type == "CONSUMERUNIT"


def test_electrical_spatial_resolution_and_layering(electrical_manifest: ProjectManifest):
    """Test 3D spatial resolution, coordinates, and discipline layer assignments."""
    resolved = resolve_manifest(electrical_manifest)

    # Light Fixtures
    r_light = resolved.get_element_by_tag("LIGHT-DOWN-01")
    assert isinstance(r_light, ResolvedLightFixture)
    assert r_light.position == (2.5, 2.0, 2.8)
    assert r_light.layer == "mep/electrical/lighting"
    assert r_light.power_watts == 18.0
    assert r_light.predefined_type == "POINTSOURCE"

    # Outlets
    r_out = resolved.get_element_by_tag("OUT-DUPLEX-01")
    assert isinstance(r_out, ResolvedOutlet)
    assert r_out.layer == "mep/electrical/power"
    assert r_out.predefined_type == "POWEROUTLET"
    assert r_out.position[0] == pytest.approx(1.5)
    assert r_out.position[2] == pytest.approx(0.30)

    # Panels / Distribution Boards
    r_mdb = resolved.get_element_by_tag("MDB-01")
    assert isinstance(r_mdb, ResolvedDistributionBoard)
    assert r_mdb.layer == "mep/electrical/panels"
    assert r_mdb.voltage == 380.0
    assert r_mdb.phases == 3
    assert r_mdb.main_breaker_rating_amperes == 100.0
    assert r_mdb.poles_count == 36
    assert r_mdb.predefined_type == "DISTRIBUTIONBOARD"

    r_cu = resolved.get_element_by_tag("CU-01")
    assert isinstance(r_cu, ResolvedDistributionBoard)
    assert r_cu.layer == "mep/electrical/panels"
    assert r_cu.voltage == 220.0


def test_electrical_qto_and_cost_estimation(electrical_manifest: ProjectManifest):
    """Test QTO counting, electrical specs grouping, and price catalog cost estimation."""
    resolved = resolve_manifest(electrical_manifest)
    qto = calculate_qto(resolved)

    assert qto.total_lighting_fixtures_count == 3
    assert qto.total_outlets_count == 2
    assert qto.total_distribution_boards_count == 2

    # Check element QTO details
    eqto_light = qto.get_element("LIGHT-DOWN-01")
    assert eqto_light is not None
    assert eqto_light.mep is not None
    assert eqto_light.mep.power_watts == 18.0
    assert eqto_light.mep.predefined_type == "POINTSOURCE"

    eqto_mdb = qto.get_element("MDB-01")
    assert eqto_mdb is not None
    assert eqto_mdb.mep is not None
    assert eqto_mdb.mep.voltage == 380.0
    assert eqto_mdb.mep.main_breaker_rating_amperes == 100.0

    # Cost Estimation
    catalog = PriceCatalog(
        currency="THB",
        items={
            "MAT-ELEC-EQ": PriceItem(
                name="Electrical Fixture / Panel", unit="set", material_cost=1500.0, labor_cost=300.0
            ),
        },
    )
    estimate = estimate_cost(qto, catalog, electrical_manifest)
    assert estimate.grand_total > 0.0


def test_electrical_ifc_compilation(electrical_manifest: ProjectManifest, tmp_path: Path):
    """Test compiling electrical fixtures to standard IFC4 STEP physical file."""
    ifc_file = tmp_path / "electrical_test.ifc"
    out_path = compile_to_ifc(electrical_manifest, ifc_file, force_fallback=True)

    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")

    assert "IFCLIGHTFIXTURE" in content
    assert "IFCOUTLET" in content
    assert "IFCELECTRICDISTRIBUTIONBOARD" in content or "IFCDISTRIBUTIONBOARD" in content
    assert ".POINTSOURCE." in content
    assert ".POWEROUTLET." in content
    assert ".DISTRIBUTIONBOARD." in content or ".CONSUMERUNIT." in content


def test_electrical_viewer_html_generation(electrical_manifest: ProjectManifest):
    """Test Three.js web viewer HTML generation with electrical metadata."""
    html = generate_viewer_html(electrical_manifest)

    assert "mep/electrical/lighting" in html
    assert "mep/electrical/power" in html
    assert "mep/electrical/panels" in html
    assert "LIGHT-DOWN-01" in html
    assert "OUT-DUPLEX-01" in html
    assert "MDB-01" in html
    assert "CU-01" in html
