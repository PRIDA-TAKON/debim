"""
Unit tests for MEP declarative wall-hosted placement and terminal elements.
"""

import math
import pytest
from pydantic import ValidationError

from debim.resolver import SpatialResolver, resolve_manifest
from debim.schema import (
    Grids,
    IfcAirTerminal,
    IfcDistributionBoard,
    IfcOutlet,
    IfcSanitaryTerminal,
    IfcSwitchingDevice,
    IfcUnitaryEquipment,
    IfcWall,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    TerminalPlacement,
    WallPlacement,
)


@pytest.fixture
def base_mep_manifest():
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-MEP-01", name="MEP Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Level 1", elevation=0.0, height=3.5),
                Storey(id="L2", name="Level 2", elevation=3.5, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0},
            axes_y={"A": 0.0, "B": 4.0},
        ),
        materials=[
            Material(
                id="MAT_CONC",
                name="Concrete",
                category="Concrete",
                unit_cost_ref="REF_CONC",
            ),
            Material(
                id="MAT_CERAMIC",
                name="Ceramic",
                category="Sanitary",
                unit_cost_ref="REF_SAN",
            ),
        ],
        elements=[
            # Wall W-HORIZ along Y=0 from X=0 to X=6 (length = 6.0m, thickness = 0.20m)
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W-HORIZ",
                    "material": "MAT_CONC",
                    "thickness": 0.20,
                    "height": 3.0,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                }
            ),
            # Wall W-VERT along X=0 from Y=0 to Y=4 (length = 4.0m, thickness = 0.15m)
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W-VERT",
                    "material": "MAT_CONC",
                    "thickness": 0.15,
                    "height": 3.0,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("1", "B"), storey="L1"),
                }
            ),
        ],
    )


def test_terminal_placement_schema_validation():
    # Neither grid nor wall provided -> raise ValueError
    with pytest.raises(ValidationError) as exc:
        TerminalPlacement()
    assert "Either grid or wall must be provided" in str(exc.value)

    # Valid grid placement
    p_grid = TerminalPlacement(grid=("1", "A"), storey="L1", offset_z=0.5)
    assert p_grid.grid == ("1", "A")

    # Valid wall placement
    p_wall = TerminalPlacement(wall="W-HORIZ", distance=2.0, side="INTERIOR", standoff=0.02)
    assert p_wall.wall == "W-HORIZ"
    assert p_wall.distance == 2.0
    assert p_wall.side == "INTERIOR"
    assert p_wall.standoff == 0.02


def test_wc_flush_against_horizontal_wall(base_mep_manifest):
    """
    Wall W-HORIZ: P1=(0,0,0), P2=(6,0,0), thickness T=0.20m.
    Tangent u = (1, 0), Normal n = (-0, 1) = (0, 1).
    WC fixture: width=0.40, depth=0.70, height=0.40.
    Placement: wall="W-HORIZ", distance=2.0m, side="INTERIOR", standoff=0.0, offset_z=0.0.
    Expected base point: P_base = (2.0, 0.0, 0.0).
    Expected offset = T/2 + standoff + depth/2 = 0.10 + 0.0 + 0.35 = 0.45.
    Expected position P = P_base + offset * n = (2.0, 0.45, 0.0).
    Auto rotation: n = (0, 1) -> angle = 90.0 degrees.
    Storey: inherited from wall -> "L1" (elevation 0.0).
    """
    wc = IfcSanitaryTerminal(
        **{
            "class": "IfcSanitaryTerminal",
            "tag": "WC-01",
            "material": "MAT_CERAMIC",
            "width": 0.40,
            "depth": 0.70,
            "height": 0.40,
            "placement": TerminalPlacement(
                wall="W-HORIZ",
                distance=2.0,
                side="INTERIOR",
                standoff=0.0,
                offset_z=0.0,
            ),
        }
    )
    base_mep_manifest.elements.append(wc)
    resolved = resolve_manifest(base_mep_manifest)

    r_wc = resolved.get_element_by_tag("WC-01")
    assert r_wc is not None
    assert r_wc.position[0] == pytest.approx(2.0)
    assert r_wc.position[1] == pytest.approx(0.45)
    assert r_wc.position[2] == pytest.approx(0.0)
    assert r_wc.rotation_angle == pytest.approx(90.0)


def test_basin_flush_against_vertical_wall(base_mep_manifest):
    """
    Wall W-VERT: P1=(0,0,0), P2=(0,4,0), thickness T=0.15m.
    Tangent u = (0, 1), Normal n = (-1, 0).
    Basin fixture: width=0.50, depth=0.45, height=0.85.
    Placement: wall="W-VERT", distance=1.5m, side="INTERIOR", standoff=0.0, offset_z=0.85.
    Expected base point: P_base = (0.0, 1.5, 0.0).
    Expected offset = T/2 + standoff + depth/2 = 0.075 + 0.0 + 0.225 = 0.30.
    Expected position P = P_base + offset * n = (0.0 - 0.30, 1.5, 0.85) = (-0.30, 1.5, 0.85).
    Auto rotation: n = (-1, 0) -> angle = 180.0 degrees.
    """
    basin = IfcSanitaryTerminal(
        **{
            "class": "IfcSanitaryTerminal",
            "tag": "BASIN-01",
            "material": "MAT_CERAMIC",
            "width": 0.50,
            "depth": 0.45,
            "height": 0.85,
            "placement": TerminalPlacement(
                wall="W-VERT",
                distance=1.5,
                side="INTERIOR",
                standoff=0.0,
                offset_z=0.85,
            ),
        }
    )
    base_mep_manifest.elements.append(basin)
    resolved = resolve_manifest(base_mep_manifest)

    r_basin = resolved.get_element_by_tag("BASIN-01")
    assert r_basin is not None
    assert r_basin.position[0] == pytest.approx(-0.30)
    assert r_basin.position[1] == pytest.approx(1.5)
    assert r_basin.position[2] == pytest.approx(0.85)
    assert r_basin.rotation_angle == pytest.approx(180.0)


def test_embedded_switch_center_side(base_mep_manifest):
    """
    Wall W-HORIZ: P1=(0,0,0), P2=(6,0,0), T=0.20m.
    Switch fixture: side="CENTER", offset_z=1.20m.
    Offset distance = 0.0.
    Expected position = (1.0, 0.0, 1.20).
    """
    switch = IfcSwitchingDevice(
        **{
            "class": "IfcSwitchingDevice",
            "tag": "SW-01",
            "width": 0.08,
            "depth": 0.04,
            "height": 0.08,
            "placement": TerminalPlacement(
                wall="W-HORIZ",
                distance=1.0,
                side="CENTER",
                offset_z=1.20,
            ),
        }
    )
    base_mep_manifest.elements.append(switch)
    resolved = resolve_manifest(base_mep_manifest)

    r_sw = resolved.get_element_by_tag("SW-01")
    assert r_sw is not None
    assert r_sw.position[0] == pytest.approx(1.0)
    assert r_sw.position[1] == pytest.approx(0.0)
    assert r_sw.position[2] == pytest.approx(1.20)
    assert r_sw.rotation_angle == pytest.approx(90.0)


def test_exterior_side_and_manual_rotation(base_mep_manifest):
    """
    Wall W-HORIZ: P1=(0,0,0), P2=(6,0,0), T=0.20m.
    Fixture: side="EXTERIOR", standoff=0.05m, depth=0.40m, distance=3.0m.
    Offset distance = -(T/2 + standoff + depth/2) = -(0.10 + 0.05 + 0.20) = -0.35m.
    Expected position = (3.0, -0.35, 1.50).
    Manual rotation override: 45.0.
    """
    outlet = IfcOutlet(
        **{
            "class": "IfcOutlet",
            "tag": "OUTLET-EXT",
            "width": 0.10,
            "depth": 0.40,
            "height": 0.10,
            "placement": TerminalPlacement(
                wall="W-HORIZ",
                distance=3.0,
                side="EXTERIOR",
                standoff=0.05,
                offset_z=1.50,
                rotation=45.0,
            ),
        }
    )
    base_mep_manifest.elements.append(outlet)
    resolved = resolve_manifest(base_mep_manifest)

    r_out = resolved.get_element_by_tag("OUTLET-EXT")
    assert r_out is not None
    assert r_out.position[0] == pytest.approx(3.0)
    assert r_out.position[1] == pytest.approx(-0.35)
    assert r_out.position[2] == pytest.approx(1.50)
    assert r_out.rotation_angle == pytest.approx(45.0)


def test_unknown_wall_raises_error(base_mep_manifest):
    term = IfcAirTerminal(
        **{
            "class": "IfcAirTerminal",
            "tag": "AIR-01",
            "placement": TerminalPlacement(
                wall="WALL-NONEXISTENT",
                distance=1.0,
            ),
        }
    )
    base_mep_manifest.elements.append(term)
    with pytest.raises(ValueError) as exc:
        resolve_manifest(base_mep_manifest)
    assert "Hosting wall 'WALL-NONEXISTENT' not found" in str(exc.value)


def test_grid_based_backward_compatibility(base_mep_manifest):
    board = IfcDistributionBoard(
        **{
            "class": "IfcDistributionBoard",
            "tag": "DB-01",
            "placement": TerminalPlacement(
                grid=("2", "B"),
                storey="L2",
                offset_x=-0.5,
                offset_y=-0.5,
                offset_z=1.5,
                rotation=180.0,
            ),
        }
    )
    base_mep_manifest.elements.append(board)
    resolved = resolve_manifest(base_mep_manifest)

    r_db = resolved.get_element_by_tag("DB-01")
    assert r_db is not None
    assert r_db.position[0] == pytest.approx(6.0 - 0.5)
    assert r_db.position[1] == pytest.approx(4.0 - 0.5)
    assert r_db.position[2] == pytest.approx(3.5 + 1.5)
    assert r_db.rotation_angle == pytest.approx(180.0)
