"""
Unit tests for automated floating viewports, standard architectural scales (1:50, 1:75, 1:100),
3-tier perimeter dimensioning, grid bubbles, and room centroid level tags (debim.draw).
"""

from pathlib import Path
import pytest
import xml.etree.ElementTree as ET

from debim.draw.renderer import (
    CoordinateTransformer,
    SheetConfig,
    SheetRenderer,
    ViewportTransform,
    calculate_viewport_transform,
    render_sheet,
    select_architectural_scale,
)
from debim.schema import load_manifest


@pytest.fixture
def project_manifest_path():
    return Path("tests/fixtures/contemporary_thai_house/project.yaml")


def test_select_architectural_scale():
    # Small model (5m x 4m) in A3 viewport (300mm x 200mm) -> fits at 1:50
    scale_50 = select_architectural_scale(5.0, 4.0, 300.0, 200.0)
    assert scale_50 == 50

    # Medium model (12m x 10m) in A3 viewport (300mm x 200mm) -> fits at 1:75 or 1:100
    scale_75_or_100 = select_architectural_scale(12.0, 10.0, 300.0, 200.0)
    assert scale_75_or_100 in (75, 100)

    # Large model (20m x 18m) in A3 viewport (300mm x 200mm) -> fits at 1:100
    scale_100 = select_architectural_scale(20.0, 18.0, 300.0, 200.0)
    assert scale_100 == 100


def test_calculate_viewport_transform():
    bounds = (0.0, 0.0, 10.0, 8.0)  # 10m x 8m model
    drawing_center = (200.0, 150.0)
    drawing_size = (300.0, 200.0)

    # Explicit 1:50 scale
    vt_50 = calculate_viewport_transform(bounds, drawing_center, drawing_size, scale=50)
    assert vt_50.scale == 50
    assert vt_50.model_center == (5.0, 4.0)
    assert vt_50.viewport_center == (200.0, 150.0)

    # Centering check: model center (5.0, 4.0) maps exactly to viewport center (200.0, 150.0)
    paper_center = vt_50.transformer.to_paper(5.0, 4.0)
    assert paper_center == (200.0, 150.0)

    # Corner check at 1:50 (k = 20mm/m): model (10.0, 8.0) -> paper (200 + 5*20, 150 - 4*20) = (300.0, 70.0)
    paper_top_right = vt_50.transformer.to_paper(10.0, 8.0)
    assert paper_top_right == (300.0, 70.0)


def test_auto_3_tier_dimensioning(project_manifest_path):
    cfg = SheetConfig(
        id="A-101",
        title="Ground Floor Plan",
        paper_size="A3",
        scale=100,
        visibility={
            "show_grid": True,
            "show_dimensions": True,
        },
    )

    renderer = SheetRenderer(project_manifest_path, cfg)
    svg_str = renderer.render_svg()

    # Tier 1 (Inner): Openings & wall offsets
    assert 'data-tier="1"' in svg_str

    # Tier 2 (Middle): Grid-to-Grid bay distances
    assert 'data-tier="2"' in svg_str

    # Tier 3 (Outer): Overall building dimensions
    assert 'data-tier="3"' in svg_str

    # Dimension lines, ticks, and text primitives
    assert 'class="dimension-line"' in svg_str
    assert 'class="dimension-tick"' in svg_str
    assert 'class="dimension-text"' in svg_str


def test_grid_bubbles_and_room_centroid_level_tags(project_manifest_path):
    cfg = SheetConfig(
        id="A-101",
        title="Ground Floor Plan",
        paper_size="A3",
        scale=100,
        visibility={
            "show_grid": True,
            "show_room_tags": True,
        },
    )

    renderer = SheetRenderer(project_manifest_path, cfg)
    svg_str = renderer.render_svg()

    # Grid Bubbles & Labels
    assert 'class="grid-bubble"' in svg_str
    assert 'class="grid-text"' in svg_str

    # Room Centroid Level Tag (e.g. FL.1 +0.00)
    assert "FL.1 +" in svg_str or "FL.1 0" in svg_str or "FL." in svg_str
    assert 'class="room-tag"' in svg_str


def test_architectural_scales_rendering(project_manifest_path):
    for target_scale in [50, 75, 100]:
        cfg = SheetConfig(
            id=f"A-101-{target_scale}",
            title=f"Floor Plan 1:{target_scale}",
            paper_size="A3",
            scale=target_scale,
        )
        renderer = SheetRenderer(project_manifest_path, cfg)
        svg_content = renderer.render_svg()

        assert f"1:{target_scale}" in svg_content
        assert 'id="drawing-viewport"' in svg_content
