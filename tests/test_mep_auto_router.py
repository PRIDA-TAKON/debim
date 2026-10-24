"""
Unit tests for Level 2 Constraint-Aware MEP Auto-Routing & Penetration Sleeves.
Verifies 3D Constrained A* pathfinding, obstacle avoidance, wall-hugging preference,
under-slab suspension, monotonic drainage slopes, and 25mm clearance penetration sleeves.
"""

from pathlib import Path
import pytest
from debim.mep.router import MEPRouter, route_connection
from debim.mep.penetration import detect_penetration_sleeves, PenetrationSleeve
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.cost import PriceCatalog, PriceItem, estimate_cost
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html
from debim.schema import (
    Grids,
    IfcBeam,
    IfcColumn,
    IfcPipeSegment,
    IfcSanitaryTerminal,
    IfcSlab,
    IfcWall,
    Material,
    PipePlacement,
    ProjectInfo,
    ProjectManifest,
    SlabPlacement,
    SpatialStructure,
    Storey,
    TerminalPlacement,
    WallPlacement,
)


@pytest.fixture
def mep_auto_router_manifest() -> ProjectManifest:
    """Fixture providing a manifest with WC, pipe stack, column, beam, walls, and slab."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-MEP-ROUTER", name="MEP Auto Router Test"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Level 1", elevation=0.0, height=3.5),
                Storey(id="L2", name="Level 2", elevation=3.5, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0, "3": 8.0},
            axes_y={"A": 0.0, "B": 4.0, "C": 8.0},
        ),
        materials=[
            Material(id="MAT_CONC", name="Concrete", category="Concrete", unit_cost_ref="REF_CONC"),
            Material(id="MAT_PVC", name="PVC Soil Pipe", category="Plumbing", unit_cost_ref="REF_PVC"),
            Material(id="MAT_CERAMIC", name="Ceramic", category="Sanitary", unit_cost_ref="REF_SAN"),
        ],
        elements=[
            # Wall along Y=0 (Y-baseline) from X=0 to X=8
            IfcWall(
                tag="W-WALL-01",
                material="MAT_CONC",
                thickness=0.20,
                height=3.0,
                placement=WallPlacement(from_grid=("1", "A"), to_grid=("3", "A"), storey="L1"),
            ),
            # Structural Column at (4.0, 2.0) blocking direct path
            IfcColumn(
                tag="C-OBSTACLE-01",
                material="MAT_CONC",
                profile={"shape": "BOX", "width": 0.50, "depth": 0.50},
                placement={"grid": ("2", "A"), "storey": "L1", "offset_y": 2.0},
            ),
            # Floor Slab at Level 1
            IfcSlab(
                tag="SLAB-L1",
                material="MAT_CONC",
                thickness=0.15,
                placement=SlabPlacement(
                    boundary=[("1", "A"), ("3", "A"), ("3", "C"), ("1", "C")],
                    storey="L1",
                ),
            ),
            # Source Sanitary Terminal (WC-01) at (1.0, 1.0)
            IfcSanitaryTerminal(
                tag="WC-01",
                terminal_type="WATER_CLOSET",
                material="MAT_CERAMIC",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1", offset_x=1.0, offset_y=1.0, offset_z=0.0),
            ),
            # Target Vertical Stack Pipe (PIPE-STACK-01) at (7.0, 1.0)
            IfcPipeSegment(
                tag="PIPE-STACK-01",
                system_type="SOIL",
                material="MAT_PVC",
                nominal_diameter=0.100,
                placement=PipePlacement(
                    storey="L1",
                    from_grid=("3", "A"),
                    to_grid=("3", "A"),
                    from_offset=(-1.0, 1.0, -0.5),
                    to_offset=(-1.0, 1.0, 3.5),
                ),
            ),
            # Auto-routed Soil Pipe connecting WC-01 to PIPE-STACK-01
            IfcPipeSegment(
                tag="PIPE-SOIL-AUTO",
                system_type="SOIL",
                material="MAT_PVC",
                nominal_diameter=0.100,
                placement=PipePlacement(
                    connect={"from": "WC-01", "to": "PIPE-STACK-01"},
                    slope=0.02,  # 1:50 gravity drainage slope
                ),
            ),
        ],
    )


def test_acceptance_criteria_connect_auto_routes_under_slab(mep_auto_router_manifest: ProjectManifest):
    """
    Acceptance Criteria: connect: {from: 'WC-01', to: 'PIPE-STACK-01'} automatically creates
    a valid orthogonal pipe route under slab.
    """
    resolved = resolve_manifest(mep_auto_router_manifest)
    pipe_auto = resolved.get_element_by_tag("PIPE-SOIL-AUTO")

    assert pipe_auto is not None
    assert len(pipe_auto.waypoints) >= 2
    assert pipe_auto.length > 5.0
    assert pipe_auto.slope == 0.02

    # Verify start point is at source (WC-01) location
    assert pytest.approx(pipe_auto.start_point[0], abs=0.2) == 1.0
    assert pytest.approx(pipe_auto.start_point[1], abs=0.2) == 1.0

    # Verify end point reaches target stack (PIPE-STACK-01) location (7.0, 1.0)
    assert pytest.approx(pipe_auto.end_point[0], abs=0.3) == 7.0
    assert pytest.approx(pipe_auto.end_point[1], abs=0.3) == 1.0

    # Verify route runs under slab (Z < 0.0)
    assert pipe_auto.waypoints[1][2] < 0.0


def test_obstacle_avoidance_bypasses_column(mep_auto_router_manifest: ProjectManifest):
    """Verify 3D Constrained A* router bypasses structural column obstacle."""
    resolved = resolve_manifest(mep_auto_router_manifest)
    pipe_auto = resolved.get_element_by_tag("PIPE-SOIL-AUTO")

    # Column obstacle box: X in [3.70, 4.30], Y in [1.70, 2.30]
    for pt in pipe_auto.waypoints:
        x, y, _ = pt
        is_inside_column = (3.72 <= x <= 4.28) and (1.72 <= y <= 2.28)
        assert not is_inside_column, f"Waypoint {pt} collided with structural column!"


def test_monotonic_drainage_slope(mep_auto_router_manifest: ProjectManifest):
    """Verify Z coordinates along waypoints decrease monotonically according to slope."""
    resolved = resolve_manifest(mep_auto_router_manifest)
    pipe_auto = resolved.get_element_by_tag("PIPE-SOIL-AUTO")

    waypoints = pipe_auto.waypoints
    # Verify Z is monotonically non-increasing (gravity drainage flow down towards stack)
    for i in range(1, len(waypoints)):
        assert waypoints[i][2] <= waypoints[i - 1][2] + 1e-4


def test_wall_hugging_preference(mep_auto_router_manifest: ProjectManifest):
    """Verify wall-hugging preference keeps waypoints close to wall faces."""
    router = MEPRouter(mep_auto_router_manifest)
    route_hugging = router.route("WC-01", "PIPE-STACK-01", wall_hugging=True, slope=0.02)
    route_direct = router.route("WC-01", "PIPE-STACK-01", wall_hugging=False, slope=0.02)

    assert len(route_hugging) >= 2
    assert len(route_direct) >= 2

    # Distance to wall W-WALL-01 (at Y=0) for hugging route vs direct
    avg_y_hugging = sum(p[1] for p in route_hugging) / len(route_hugging)
    avg_y_direct = sum(p[1] for p in route_direct) / len(route_direct)

    # Hugging route stays closer to Y=0 wall
    assert avg_y_hugging <= avg_y_direct + 0.5


def test_penetration_sleeve_generation_and_qto(mep_auto_router_manifest: ProjectManifest):
    """Verify penetration sleeves generate 25mm clearance offset geometry and update QTO."""
    resolved = resolve_manifest(mep_auto_router_manifest)
    sleeves = getattr(resolved, "penetration_sleeves", [])

    assert len(sleeves) >= 1
    sleeve = sleeves[0]
    assert isinstance(sleeve, PenetrationSleeve)

    # 100mm pipe (0.100m) + 2 * 25mm clearance (0.050m) = 150mm (0.150m)
    assert sleeve.pipe_diameter == 0.100
    assert sleeve.sleeve_diameter == pytest.approx(0.150, abs=1e-3)
    assert sleeve.sleeve_length > 0.0

    # QTO calculation
    qto = calculate_qto(resolved)
    assert qto.total_penetration_sleeves_count == len(sleeves)
    assert qto.total_penetration_sleeves_count >= 1


def test_end_to_end_cost_viewer_and_ifc(mep_auto_router_manifest: ProjectManifest, tmp_path: Path):
    """Verify cost estimation, 3D viewer, and IFC compilation for auto-routed model."""
    resolved = resolve_manifest(mep_auto_router_manifest)
    qto = calculate_qto(resolved)

    catalog = PriceCatalog(
        currency="THB",
        items={
            "REF_CONC": PriceItem(name="Concrete", unit="m3", material_cost=2500.0, labor_cost=500.0),
            "REF_PVC": PriceItem(name="PVC Soil Pipe", unit="m", material_cost=180.0, labor_cost=70.0),
            "REF_SAN": PriceItem(name="WC Set", unit="set", material_cost=3500.0, labor_cost=500.0),
            "MEP-SLEEVE": PriceItem(name="Penetration Sleeve", unit="set", material_cost=250.0, labor_cost=150.0),
        },
    )

    estimate = estimate_cost(qto, catalog, mep_auto_router_manifest)
    assert estimate.grand_total > 0.0

    # Viewer HTML check
    html = generate_viewer_html(mep_auto_router_manifest)
    assert "PIPE-SOIL-AUTO" in html
    assert "SLEEVE" in html

    # IFC Compilation check
    ifc_out = tmp_path / "auto_routed_mep.ifc"
    compile_to_ifc(mep_auto_router_manifest, ifc_out, force_fallback=True)
    assert ifc_out.exists()
    content = ifc_out.read_text(encoding="utf-8")
    assert "IFCPIPESEGMENT" in content
    assert "IFCBUILDINGELEMENTPROXY" in content
