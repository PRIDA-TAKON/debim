"""
Unit tests for point offsets (offset_x, offset_y) and arithmetic grid coordinate expressions.
Verifies displaced columns, footings with piles, walls, and arithmetic grid expressions
such as grid: ['3 + 1.00', 'ข - 0.50'] and from_grid: ['1 - 0.20', 'A'].
"""

import pytest
from debim.schema import (
    BoxProfile,
    ColumnPlacement,
    FootingPiles,
    FootingPlacement,
    FootingProfile,
    Grids,
    IfcColumn,
    IfcFooting,
    IfcWall,
    PileProfile,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    WallPlacement,
)
from debim.resolver import SpatialResolver, resolve_manifest


def create_base_manifest() -> ProjectManifest:
    """Helper to create a ProjectManifest with numeric and Thai grid axes."""
    return ProjectManifest(
        project=ProjectInfo(id="TEST-OFFSETS", name="Offset Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Ground Floor", elevation=0.0, height=3.5),
                Storey(id="L2", name="Second Floor", elevation=3.5, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0, "3": 8.0},
            axes_y={"A": 0.0, "B": 5.0, "ข": 10.0},
        ),
        materials=[
            {"id": "CONCRETE", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "MAT-CONC"},
            {"id": "BRICK", "name": "Brick", "category": "MASONRY", "unit_cost_ref": "MAT-BRICK"},
        ],
        elements=[],
    )


def test_displaced_column_carport_offsets():
    """Test displaced column (carport offset) with offset_x and offset_y."""
    manifest = create_base_manifest()
    col = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "C-CARPORT",
            "material": "CONCRETE",
            "profile": BoxProfile(width=0.20, depth=0.20),
            "placement": ColumnPlacement(
                grid=("1", "A"),
                base_storey="L1",
                top_storey="L2",
                offset_x=1.50,
                offset_y=-0.80,
            ),
        }
    )
    manifest.elements.append(col)
    resolver = SpatialResolver(manifest)
    res_col = resolver.resolve_column(col)

    # Grid 1=0.0 + offset_x 1.50 = 1.50
    # Grid A=0.0 + offset_y -0.80 = -0.80
    assert res_col.start_point == (1.50, -0.80, 0.0)
    assert res_col.end_point == (1.50, -0.80, 3.5)
    assert res_col.height == 3.5


def test_displaced_footing_and_piles():
    """Test displaced footing and footing piles shift together with offset_x and offset_y."""
    manifest = create_base_manifest()
    footing = IfcFooting(
        **{
            "class": "IfcFooting",
            "tag": "F1-DISPLACED",
            "material": "CONCRETE",
            "profile": FootingProfile(width=1.00, depth=1.00, thickness=0.40),
            "placement": FootingPlacement(
                grid=("2", "B"),
                storey="L1",
                offset_x=-0.50,
                offset_y=1.20,
                offset_z=-1.00,
            ),
            "piles": FootingPiles(
                count=4,
                profile=PileProfile(shape="HEXAGONAL", dimension=0.15),
                length=6.00,
                spacing=0.60,
            ),
        }
    )
    manifest.elements.append(footing)
    resolver = SpatialResolver(manifest)
    res_footing = resolver.resolve_footing(footing)

    # Grid 2=4.0 + offset_x -0.50 = 3.50
    # Grid B=5.0 + offset_y 1.20 = 6.20
    assert res_footing.position == (3.50, 6.20, -1.00)
    assert len(res_footing.piles) == 4

    # Pile positions should be centered at (3.50, 6.20, -1.00)
    pile_positions = [p.position for p in res_footing.piles]
    assert (3.20, 5.90, -1.00) in pile_positions
    assert (3.80, 5.90, -1.00) in pile_positions
    assert (3.20, 6.50, -1.00) in pile_positions
    assert (3.80, 6.50, -1.00) in pile_positions


def test_displaced_wall_cantilever_alignment():
    """Test displaced wall (cantilever wall alignment) with offset_x and offset_y."""
    manifest = create_base_manifest()
    wall = IfcWall(
        **{
            "class": "IfcWall",
            "tag": "W-CANTILEVER",
            "material": "BRICK",
            "thickness": 0.10,
            "height": 2.80,
            "placement": WallPlacement(
                from_grid=("1", "A"),
                to_grid=("2", "A"),
                storey="L1",
                offset_x=0.0,
                offset_y=-0.60,
            ),
        }
    )
    manifest.elements.append(wall)
    resolver = SpatialResolver(manifest)
    r_wall, _, _ = resolver.resolve_wall(wall)

    # from_grid (1, A) = (0.0, 0.0) + (0.0, -0.60) = (0.0, -0.60, 0.0)
    # to_grid (2, A) = (4.0, 0.0) + (0.0, -0.60) = (4.0, -0.60, 0.0)
    assert r_wall.start_point == (0.0, -0.60, 0.0)
    assert r_wall.end_point == (4.0, -0.60, 0.0)
    assert r_wall.length == 4.0


def test_arithmetic_grid_expressions_single_point_and_linear():
    """
    Test arithmetic grid coordinates such as grid: ['3 + 1.00', 'ข - 0.50']
    and from_grid: ['1 - 0.20', 'A'].
    """
    manifest = create_base_manifest()

    # 1. Single-point Column with grid: ['3 + 1.00', 'ข - 0.50']
    col = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "C-ARITH",
            "material": "CONCRETE",
            "profile": BoxProfile(width=0.25, depth=0.25),
            "placement": ColumnPlacement(
                grid=("3 + 1.00", "ข - 0.50"),
                base_storey="L1",
                top_storey="L2",
                offset_x=0.10,
                offset_y=0.20,
            ),
        }
    )

    # 2. Linear Wall with from_grid: ['1 - 0.20', 'A'] and to_grid: ['2 + 0.50', 'B - 1.00']
    wall = IfcWall(
        **{
            "class": "IfcWall",
            "tag": "W-ARITH",
            "material": "BRICK",
            "thickness": 0.15,
            "height": 3.0,
            "placement": WallPlacement(
                from_grid=("1 - 0.20", "A"),
                to_grid=("2 + 0.50", "B - 1.00"),
                storey="L1",
                offset_x=0.05,
                offset_y=0.05,
            ),
        }
    )

    manifest.elements.extend([col, wall])

    # Validate references and resolve
    manifest.model_validate(manifest)
    resolved = resolve_manifest(manifest)

    # Verify column C-ARITH
    # Grid '3' = 8.0 -> 8.0 + 1.00 = 9.00 + offset_x 0.10 = 9.10
    # Grid 'ข' = 10.0 -> 10.0 - 0.50 = 9.50 + offset_y 0.20 = 9.70
    res_col = resolved.get_element_by_tag("C-ARITH")
    assert res_col is not None
    assert res_col.start_point == pytest.approx((9.10, 9.70, 0.0))
    assert res_col.end_point == pytest.approx((9.10, 9.70, 3.5))

    # Verify wall W-ARITH
    # from_grid: '1 - 0.20' = -0.20 + 0.05 = -0.15; 'A' = 0.0 + 0.05 = 0.05
    # to_grid: '2 + 0.50' = 4.50 + 0.05 = 4.55; 'B - 1.00' = 4.00 + 0.05 = 4.05
    res_wall = resolved.get_element_by_tag("W-ARITH")
    assert res_wall is not None
    assert res_wall.start_point == pytest.approx((-0.15, 0.05, 0.0))
    assert res_wall.end_point == pytest.approx((4.55, 4.05, 0.0))
