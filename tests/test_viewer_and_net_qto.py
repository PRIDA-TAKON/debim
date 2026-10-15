"""
Unit tests for 3D WebGL viewer storey filter controls and QTO host_wall opening deduction.
"""

import pytest
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Dimensions,
    Grids,
    IfcDoor,
    IfcWall,
    IfcWindow,
    Material,
    ProjectManifest,
    SpatialStructure,
    Storey,
    WallFinishesConfig,
    WallPlacement,
)
from debim.viewer import generate_viewer_html


def test_viewer_storey_filter_controls():
    """Verify Three.js HTML viewer generation includes storey isolation buttons and storey metadata."""
    manifest = ProjectManifest(
        project={"id": "PROJ-STOREY-TEST", "name": "Storey Test Project"},
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Floor 1", elevation=0.00, height=3.50),
                Storey(id="FL2", name="Floor 2", elevation=3.50, height=3.20),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[Material(id="MAT_BRICK", name="Brick", category="masonry", unit_cost_ref="MAT-BRICK")],
        elements=[
            IfcWall(
                tag="W-FL1",
                material="MAT_BRICK",
                placement=WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="FL1"),
                thickness=0.15,
                height=3.0,
            ),
            IfcWall(
                tag="W-FL2",
                material="MAT_BRICK",
                placement=WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="FL2"),
                thickness=0.15,
                height=3.0,
            ),
        ],
    )

    html = generate_viewer_html(manifest)

    # 1. Verify storey filter UI controls exist in HTML
    assert 'class="view-btn storey-btn active" data-storey="all"' in html
    assert 'id="storey-toolbar-btns"' in html
    assert "filterStorey" in html

    # 2. Verify storey metadata is attached to elements in scene JSON
    assert '"storey": "FL1"' in html
    assert '"storey": "FL2"' in html


def test_qto_net_wall_opening_deduction_inline_and_host_wall():
    """Verify door and window openings deduct from gross wall surface areas for net plaster and masonry take-off."""
    # Create manifest with inline door/window and standalone host_wall door/window
    manifest = ProjectManifest(
        project={"id": "PROJ-NET-QTO", "name": "Net Wall QTO Test"},
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="L1", name="Level 1", elevation=0.0, height=3.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[Material(id="MAT_BRICK", name="Brick", category="masonry", unit_cost_ref="MAT-BRICK")],
        elements=[
            # Wall 1: Gross area = 5.0m * 3.0m = 15.0 m2, with inline door (1.0m * 2.0m = 2.0 m2)
            IfcWall(
                tag="W-INLINE",
                material="MAT_BRICK",
                placement=WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                thickness=0.15,
                height=3.0,
                finishes=WallFinishesConfig(plaster="BOTH", interior_finish="PAINT", exterior_finish="PAINT"),
                children=[
                    IfcDoor(
                        tag="D-01",
                        dimensions=Dimensions(width=1.0, height=2.0),
                        offset_distance=1.0,
                        sill_height=0.0,
                    )
                ],
            ),
            # Wall 2: Gross area = 5.0m * 3.0m = 15.0 m2, with standalone host_wall window (1.5m * 1.0m = 1.5 m2)
            IfcWall(
                tag="W-HOST",
                material="MAT_BRICK",
                placement=WallPlacement(from_grid=("1", "B"), to_grid=("2", "B"), storey="L1"),
                thickness=0.15,
                height=3.0,
                finishes=WallFinishesConfig(plaster="BOTH", interior_finish="PAINT", exterior_finish="PAINT"),
            ),
            IfcWindow(
                tag="WIN-01",
                dimensions=Dimensions(width=1.5, height=1.0),
                offset_distance=1.5,
                sill_height=1.0,
                host_wall="W-HOST",
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    qto = calculate_qto(resolved)

    # Wall 1 QTO:
    # Gross area = 15.0 m2, cutout = 2.0 m2 -> Net area = 13.0 m2
    w1_qto = qto.get_element("W-INLINE")
    assert w1_qto is not None
    assert w1_qto.concrete_volume == pytest.approx(13.0 * 0.15)
    assert w1_qto.wall_finishes is not None
    assert w1_qto.wall_finishes.net_area_one_side == pytest.approx(13.0)
    assert w1_qto.wall_finishes.plaster_area == pytest.approx(26.0)  # BOTH sides = 2 * 13.0

    # Wall 2 QTO:
    # Gross area = 15.0 m2, cutout = 1.5 m2 -> Net area = 13.5 m2
    w2_qto = qto.get_element("W-HOST")
    assert w2_qto is not None
    assert w2_qto.concrete_volume == pytest.approx(13.5 * 0.15)
    assert w2_qto.wall_finishes is not None
    assert w2_qto.wall_finishes.net_area_one_side == pytest.approx(13.5)
    assert w2_qto.wall_finishes.plaster_area == pytest.approx(27.0)  # BOTH sides = 2 * 13.5

    # Project Totals QTO
    # Total Masonry Area = 13.0 + 13.5 = 26.5 m2
    # Total Plaster Area = 26.0 + 27.0 = 53.0 m2
    assert qto.total_wall_masonry_area == pytest.approx(26.5)
    assert qto.total_wall_plaster_area == pytest.approx(53.0)
    assert qto.total_openings_area == pytest.approx(2.0 + 1.5)
