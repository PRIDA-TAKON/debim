"""
Unit tests for 3D inclined columns, spatial beams, diagonal bracing, and segmented arches.
"""

import math
from pathlib import Path
import pytest

from debim.schema import (
    BoxProfile,
    ColumnPlacement,
    IfcColumn,
    BeamPlacement,
    IfcBeam,
    BeamWaypoint,
    load_manifest,
)
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    SpatialResolver,
    resolve_manifest,
)
from debim.qto import calculate_element_qto, calculate_qto


def test_inclined_column_resolution_and_qto(sample_project_path):
    manifest = load_manifest(sample_project_path)

    # Create inclined column from A1 (0,0,0) to B2 (4,5,3.5)
    inc_col = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "COL-INCLINED",
            "material": "MAT_CONC",
            "profile": BoxProfile(shape="BOX", width=0.4, depth=0.4),
            "placement": ColumnPlacement(
                grid=("A", "1"),
                top_grid=("B", "2"),
                base_storey="L1",
                top_storey="L2",
                offset_base=(0.0, 0.0, 0.0),
                offset_top=(0.0, 0.0, 0.0),
            ),
        }
    )
    manifest.elements.append(inc_col)

    resolver = SpatialResolver(manifest)
    res_col = resolver.resolve_column(inc_col)

    assert res_col.tag == "COL-INCLINED"
    assert res_col.start_point == (0.0, 0.0, 0.0)
    assert res_col.end_point == (4.0, 5.0, 3.5)

    # 3D length = sqrt(4^2 + 5^2 + 3.5^2) = sqrt(16 + 25 + 12.25) = sqrt(53.25) ~ 7.29726 m
    expected_len = math.sqrt(4.0**2 + 5.0**2 + 3.5**2)
    assert res_col.height == pytest.approx(expected_len, rel=1e-4)

    # Direction vector check
    dx, dy, dz = res_col.direction_vector_3d
    assert dx == pytest.approx(4.0 / expected_len, rel=1e-4)
    assert dy == pytest.approx(5.0 / expected_len, rel=1e-4)
    assert dz == pytest.approx(3.5 / expected_len, rel=1e-4)

    # QTO check based on true 3D spatial length
    qto = calculate_element_qto(res_col, manifest)
    expected_vol = 0.4 * 0.4 * expected_len
    expected_formwork = 2.0 * (0.4 + 0.4) * expected_len
    assert qto.concrete_volume == pytest.approx(expected_vol, rel=1e-4)
    assert qto.formwork_area == pytest.approx(expected_formwork, rel=1e-4)


def test_3d_spatial_beam_and_segmented_arch_resolution(sample_project_path):
    manifest = load_manifest(sample_project_path)

    # 1. Diagonal 3D Beam spanning storeys L1 to L2 across grids
    diag_beam = IfcBeam(
        **{
            "class": "IfcBeam",
            "tag": "BEAM-3D-DIAG",
            "material": "MAT_STEEL",
            "profile": BoxProfile(shape="BOX", width=0.3, depth=0.5),
            "placement": BeamPlacement(
                from_grid=("A", "1"),
                to_grid=("B", "2"),
                storey="L1",
                offset_z=0.0,
                to_storey="L2",
                to_offset_z=1.5,
            ),
        }
    )

    # 2. Segmented parabolic arch beam
    arch_beam = IfcBeam(
        **{
            "class": "IfcBeam",
            "tag": "BEAM-PARABOLIC-ARCH",
            "material": "MAT_STEEL",
            "profile": BoxProfile(shape="BOX", width=0.3, depth=0.5),
            "placement": BeamPlacement(
                from_grid=("A", "1"),
                to_grid=("B", "1"),
                storey="L1",
                offset_z=0.0,
                curve={"arch_height": 10.0, "segments": 10},
            ),
        }
    )

    manifest.elements.extend([diag_beam, arch_beam])
    resolver = SpatialResolver(manifest)

    # Verify Diagonal Beam
    res_diag = resolver.resolve_beam(diag_beam)
    assert res_diag.start_point == (0.0, 0.0, 0.0)
    assert res_diag.end_point == (4.0, 5.0, 5.0)  # L2 elevation 3.5 + to_offset_z 1.5 = 5.0
    expected_span = math.sqrt(4.0**2 + 5.0**2 + 5.0**2)  # sqrt(16 + 25 + 25) = sqrt(66) ~ 8.124
    assert res_diag.span_length == pytest.approx(expected_span, rel=1e-4)

    # Verify Parabolic Arch
    res_arch = resolver.resolve_beam(arch_beam)
    assert len(res_arch.waypoints) == 11  # 10 segments -> 11 points
    assert res_arch.waypoints[0] == (0.0, 0.0, 0.0)
    assert res_arch.waypoints[-1] == (4.0, 0.0, 0.0)
    # Apex at midpoint t=0.5: z = 4.0 * 10.0 * 0.5 * 0.5 = 10.0
    mid_wpt = res_arch.waypoints[5]
    assert mid_wpt[0] == pytest.approx(2.0, rel=1e-4)
    assert mid_wpt[2] == pytest.approx(10.0, rel=1e-4)
    assert res_arch.span_length > 4.0  # Curve length greater than straight span


def test_eiffel_tower_project_yaml_resolution():
    eiffel_path = Path("examples/eiffel_tower/project.yaml")
    assert eiffel_path.exists()

    manifest = load_manifest(eiffel_path)
    resolved = resolve_manifest(manifest)

    # Check that Eiffel tower inclined legs and parabolic arches resolve cleanly
    leg_sw_outer = resolved.get_element_by_tag("LEG-SW-OUTER")
    assert isinstance(leg_sw_outer, ResolvedColumn)
    assert leg_sw_outer.start_point == (-52.0, -52.0, 0.0)
    assert leg_sw_outer.end_point == (-10.0, -10.0, 57.63)
    assert leg_sw_outer.height > 57.63  # Inclined leg spatial length > vertical storey height

    arch_south = resolved.get_element_by_tag("ARCH-SOUTH")
    assert isinstance(arch_south, ResolvedBeam)
    assert len(arch_south.waypoints) == 21  # 20 segments -> 21 waypoints
    assert arch_south.waypoints[10][2] == pytest.approx(39.0, rel=1e-3)  # Peak height 39m

    # Test QTO calculation for Eiffel Tower model
    project_qto = calculate_qto(resolved)
    assert project_qto.total_structural_steel_weight > 0.0
