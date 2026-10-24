"""
Unit tests for Gravity Drainage Slope Solver and Invert Elevation Calculation Engine in src/debim/solver.py.
"""

import math
import pytest
from debim.schema import (
    ProjectManifest,
    MepNetworkSystem,
    CollectorPipeDefinition,
    GatherFixtureDefinition,
    IfcSanitaryTerminal,
    TerminalPlacement,
    IfcBeam,
    BeamPlacement,
    BoxProfile,
    IfcPipeSegment,
    PipePlacement,
)
from debim.solver import (
    solve_gravity_drainage_slopes,
    GravityDrainageSolverResult,
    InvertElevationResult,
    DrainageSlopeWarning,
)


def create_base_drainage_manifest():
    """Helper to build a minimal ProjectManifest with sanitary terminals, beam, and drainage network."""
    return ProjectManifest.model_validate({
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ_SLOPE_TEST", "name": "Drainage Slope Test Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "STOREY-1", "name": "Floor 1", "elevation": 0.0, "height": 3.5}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 4.0, "C": 8.0},
        },
        "materials": [
            {"id": "CONCRETE", "name": "Concrete C25/30", "category": "Concrete", "unit_cost_ref": "MAT-CONC"},
            {"id": "PVC", "name": "PVC Class 8.5", "category": "Plastic", "unit_cost_ref": "MAT-PVC"},
        ],
        "elements": [
            # Sanitary Terminals (WC and Basin)
            IfcSanitaryTerminal(
                tag="SAN_WC_01",
                terminal_type="WATER_CLOSET",
                placement=TerminalPlacement(grid=("1", "B"), storey="STOREY-1", offset_x=0.0, offset_y=0.0, offset_z=0.40),
            ),
            IfcSanitaryTerminal(
                tag="SAN_BASIN_01",
                terminal_type="WASHHANDBASIN",
                placement=TerminalPlacement(grid=("2", "B"), storey="STOREY-1", offset_x=0.0, offset_y=0.0, offset_z=0.80),
            ),
        ],
        "mep_systems": [
            MepNetworkSystem(
                id="SYS_SOIL_WASTE_01",
                system_type="SANITARY_DRAINAGE",
                material="PVC",
                collector_pipe=CollectorPipeDefinition.model_validate({
                    "tag": "PIPE_SOIL_MAIN",
                    "discharge_to": "STACK_01",
                    "slope": 0.01,  # 1:100
                    "diameter": 0.100,
                    "from": {"grid": ["1", "B"], "offset": [0.0, 0.0, 3.0]},
                    "to": {"grid": ["3", "B"], "offset": [0.0, 0.0, 2.94]},
                }),
                gather_fixtures=[
                    GatherFixtureDefinition(
                        fixture="SAN_WC_01",
                        branch_diameter=0.100,
                        slope=0.01,
                    ),
                    GatherFixtureDefinition(
                        fixture="SAN_BASIN_01",
                        branch_diameter=0.050,
                        slope=0.01,
                    ),
                ],
            )
        ],
    })


def test_gravity_drainage_invert_elevation_calculation():
    """Verify upstream fixture inverts are higher than discharge points by distance * slope."""
    manifest = create_base_drainage_manifest()
    res = solve_gravity_drainage_slopes(manifest, min_slope=0.01, discharge_stack_invert=2.00)

    assert isinstance(res, GravityDrainageSolverResult)
    assert res.min_slope == 0.01
    assert len(res.invert_elevations) >= 3  # Collector + 2 Fixtures

    # Find collector result
    coll_res = next(r for r in res.invert_elevations if r.tag == "PIPE_SOIL_MAIN")
    assert coll_res.point_type == "COLLECTOR_PIPE"
    assert coll_res.end_invert_elevation == 2.00
    # Horizontal distance from grid 1 to 3 along Y=4.0 is 8.0m
    expected_dist = 8.0
    assert abs(coll_res.distance_from_discharge - expected_dist) < 1e-3
    # Start invert elevation = end + dist * slope = 2.00 + 8.0 * 0.01 = 2.08
    assert abs(coll_res.start_invert_elevation - 2.08) < 1e-3

    # Find SAN_BASIN_01 result
    basin_res = next(r for r in res.invert_elevations if r.tag == "SAN_BASIN_01")
    assert basin_res.point_type == "FIXTURE_BRANCH"
    assert basin_res.start_invert_elevation > basin_res.end_invert_elevation
    # Upstream invert is higher than junction invert by branch_distance * slope
    branch_diff = basin_res.start_invert_elevation - basin_res.end_invert_elevation
    assert branch_diff > 0.0


def test_insufficient_slope_warning():
    """Test warning generation when specified slope is less than min_slope (e.g. 1:200 = 0.005 < 0.01)."""
    manifest = create_base_drainage_manifest()
    # Modify collector pipe slope to 0.005 (0.5%)
    manifest.mep_systems[0].collector_pipe.slope = 0.005

    res = solve_gravity_drainage_slopes(manifest, min_slope=0.01)
    assert not res.passed
    assert len(res.warnings) >= 1

    slope_warn = next(w for w in res.warnings if w.warning_type == "INSUFFICIENT_SLOPE")
    assert slope_warn.pipe_tag == "PIPE_SOIL_MAIN"
    assert "below minimum required gradient" in slope_warn.message


def test_beam_clash_detection():
    """Test warning generation when sloped drainage pipe clashes with a structural beam."""
    manifest = create_base_drainage_manifest()

    # Add a beam directly across the path of the sloped collector pipe at Y=B (4.0m)
    beam = IfcBeam(
        tag="BEAM_CROSS_01",
        material="CONCRETE",
        profile=BoxProfile(width=0.30, depth=0.50),
        placement=BeamPlacement(
            from_grid=("1", "B"),
            to_grid=("3", "B"),
            storey="STOREY-1",
            offset_z=3.0,  # Positioned right where the sloped pipe passes at (1..3, B) Z~3.0
        ),
    )
    manifest.elements.append(beam)

    res = solve_gravity_drainage_slopes(manifest, min_slope=0.01, discharge_stack_invert=3.0)
    clash_warns = [w for w in res.warnings if w.warning_type == "BEAM_CLASH"]

    assert len(clash_warns) > 0
    clash_pipe_tags = {w.pipe_tag for w in clash_warns}
    assert "PIPE_SOIL_MAIN" in clash_pipe_tags or any("BRANCH" in t for t in clash_pipe_tags)


def test_standalone_drainage_pipe_segment():
    """Test gravity slope solver with standalone IfcPipeSegment elements."""
    manifest = ProjectManifest.model_validate({
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ_PIPE_TEST", "name": "Pipe Test"},
        "spatial_structure": {"storeys": [{"id": "STOREY-1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]},
        "grids": {"axes_x": {"1": 0.0, "2": 5.0}, "axes_y": {"A": 0.0, "B": 5.0}},
        "materials": [{"id": "PVC", "name": "PVC", "category": "Plastic", "unit_cost_ref": "MAT-PVC"}],
        "elements": [
            IfcPipeSegment(
                tag="PIPE_DRAIN_01",
                system_type="DRAINAGE",
                material="PVC",
                nominal_diameter=0.100,
                placement=PipePlacement(
                    from_grid=("1", "A"),
                    to_grid=("2", "A"),
                    storey="STOREY-1",
                    slope=0.02,  # 2% slope
                ),
            )
        ],
    })

    res = solve_gravity_drainage_slopes(manifest, min_slope=0.01, discharge_stack_invert=1.0)
    assert len(res.invert_elevations) == 1
    pipe_res = res.invert_elevations[0]
    assert pipe_res.tag == "PIPE_DRAIN_01"
    assert pipe_res.calculated_slope == 0.02
    assert abs(pipe_res.distance_from_discharge - 5.0) < 1e-3
    # Start invert = 1.0 + 5.0 * 0.02 = 1.10
    assert abs(pipe_res.start_invert_elevation - 1.10) < 1e-3
