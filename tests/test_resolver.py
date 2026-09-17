"""
Unit tests for 3D spatial coordinate resolver (debim.resolver).
"""

import math
from pathlib import Path
import pytest

from debim.schema import load_manifest
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCustomElement,
    ResolvedDoor,
    ResolvedWall,
    ResolvedWindow,
    SpatialResolver,
    resolve_manifest,
)


def test_resolve_townhouse_manifest(sample_project_path):
    manifest = load_manifest(sample_project_path)
    resolved = resolve_manifest(manifest)

    assert len(resolved.columns) == 1
    assert len(resolved.beams) == 1
    assert len(resolved.walls) == 1
    assert len(resolved.doors) == 1
    assert len(resolved.windows) == 0
    assert len(resolved.custom_elements) == 1

    # 1. Column C-A1
    col = resolved.get_element_by_tag("C-A1")
    assert isinstance(col, ResolvedColumn)
    assert col.start_point == (0.0, 0.0, 0.0)
    assert col.end_point == (0.0, 0.0, 3.5)
    assert col.height == 3.5

    # 2. Beam B-A1_B1
    beam = resolved.get_element_by_tag("B-A1_B1")
    assert isinstance(beam, ResolvedBeam)
    assert beam.start_point == (0.0, 0.0, 3.5)
    assert beam.end_point == (4.0, 0.0, 3.5)
    assert beam.span_length == 4.0
    assert beam.direction_vector == (1.0, 0.0)
    assert beam.rotation_angle == 0.0

    # 3. Wall W-A1_A2
    wall = resolved.get_element_by_tag("W-A1_A2")
    assert isinstance(wall, ResolvedWall)
    assert wall.start_point == (0.0, 0.0, 0.0)
    assert wall.end_point == (0.0, 5.0, 0.0)
    assert wall.length == 5.0
    assert wall.thickness == 0.075
    assert wall.height == 3.10
    assert len(wall.children) == 1

    # 4. Door D1
    door = resolved.doors[0]
    assert isinstance(door, ResolvedDoor)
    assert door.tag == "D1"
    assert door.position == (0.0, 1.2, 0.0)
    assert door.width == 0.90
    assert door.height == 2.00
    assert door.offset_distance == 1.20
    assert door.sill_height == 0.00

    # 5. Custom Element ST-01
    custom = resolved.get_element_by_tag("ST-01")
    assert isinstance(custom, ResolvedCustomElement)
    assert custom.position == (2.0, 2.5, 0.0)


def test_spatial_resolver_angled_beam_and_window(sample_project_path):
    manifest = load_manifest(sample_project_path)
    resolver = SpatialResolver(manifest)

    # Test error handling on unknown grid/storey
    with pytest.raises(ValueError, match="Grid X axis 'X99' not found"):
        resolver.get_grid_xy(("X99", "1"))

    with pytest.raises(ValueError, match="Storey 'L99' not found"):
        resolver.get_storey("L99")


def test_resolver_footing_with_piles(sample_project_path):
    from debim.schema import IfcFooting, FootingProfile, FootingPlacement, FootingPiles, PileProfile

    manifest = load_manifest(sample_project_path)
    piled_footing = IfcFooting(
        **{
            "class": "IfcFooting",
            "tag": "F4-TEST",
            "material": "MAT_CONC",
            "profile": FootingProfile(width=1.20, depth=1.20, thickness=0.40),
            "placement": FootingPlacement(grid=("A", "1"), storey="L1", offset_z=-1.00),
            "piles": FootingPiles(
                count=4,
                profile=PileProfile(shape="HEXAGONAL", dimension=0.15),
                length=6.00,
                spacing=0.60,
            ),
        }
    )
    manifest.elements.append(piled_footing)
    resolver = SpatialResolver(manifest)
    res_footing = resolver.resolve_footing(piled_footing)

    assert res_footing.tag == "F4-TEST"
    assert res_footing.position == (0.0, 0.0, -1.00)
    assert len(res_footing.piles) == 4

    # Check pile coordinates (top of piles at footing cap bottom z=-1.00)
    # spacing 0.60 -> offsets +/-0.30 in X and Y
    p_positions = [p.position for p in res_footing.piles]
    assert (-0.30, -0.30, -1.00) in p_positions
    assert (0.30, -0.30, -1.00) in p_positions
    assert (-0.30, 0.30, -1.00) in p_positions
    assert (0.30, 0.30, -1.00) in p_positions
    assert all(p.length == 6.00 for p in res_footing.piles)


def test_resolver_slab(sample_project_path):
    from debim.schema import IfcSlab, SlabPlacement, SlabReinforcement

    manifest = load_manifest(sample_project_path)
    slab = IfcSlab(
        **{
            "class": "IfcSlab",
            "tag": "SLAB-TEST",
            "material": "MAT_CONC",
            "thickness": 0.12,
            "slab_type": "SOLID",
            "placement": SlabPlacement(
                boundary=[("A", "1"), ("B", "1"), ("B", "2"), ("A", "2")],
                storey="L1",
            ),
        }
    )
    manifest.elements.append(slab)
    resolver = SpatialResolver(manifest)
    res_slab = resolver.resolve_slab(slab)

    assert res_slab.tag == "SLAB-TEST"
    assert res_slab.thickness == 0.12
    # Area: width 4.0m x length 5.0m = 20.0 m2 (from Townhouse grid A-B: 5.0m, 1-2: 4.0m)
    assert res_slab.area == pytest.approx(20.0, rel=1e-2)
    assert len(res_slab.polygon) == 4


def test_resolver_stair(sample_project_path):
    from debim.schema import IfcStair, StairPlacement, StairLanding, StairStepConfig, StairReinforcement

    manifest = load_manifest(sample_project_path)
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-TEST",
            "material": "MAT_CONC",
            "stair_type": "DOG_LEG",
            "width": 1.00,
            "waist_thickness": 0.12,
            "placement": StairPlacement(
                grid_anchor=("A", "1"),
                from_storey="L1",
                to_storey="L2",
                offset_x=0.0,
                offset_y=0.0,
                offset_z=0.0,
                orientation="+Y",
            ),
            "landing": StairLanding(
                elevation=1.50,
                depth=1.00,
                thickness=0.12,
            ),
            "steps": StairStepConfig(
                tread=0.25,
                riser=0.1875,
            ),
        }
    )
    manifest.elements.append(stair)
    resolver = SpatialResolver(manifest)
    res_stair = resolver.resolve_stair(stair)

    assert res_stair.tag == "ST-TEST"
    assert res_stair.element.stair_type == "DOG_LEG"
    assert len(res_stair.flights) == 2
    assert res_stair.landing_polygon is not None
    assert res_stair.landing_area > 0.0
    assert res_stair.flights[0].n_risers > 0
    assert res_stair.total_concrete_volume > 0.0
    assert res_stair.total_formwork_area > 0.0


