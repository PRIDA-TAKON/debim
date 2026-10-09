"""
Unit tests for 2D Architectural Elevations Projection & Rendering Engine (debim.draw.elevation).
Tests orthographic vertical projection across 4 cardinal directions (Front, Rear, Right, Left),
level markers, grid lines, elevation SVG rendering, and 2D HTML viewer integration.
"""

from pathlib import Path
import pytest

from debim.draw.elevation import (
    ElevationResult,
    LevelMarker2D,
    normalize_direction,
    project_2d_elevation,
)
from debim.draw.renderer import SheetConfig, SheetRenderer, render_sheet
from debim.draw.viewer_2d import generate_2d_viewer_html
from debim.schema import load_manifest


@pytest.fixture
def project_manifest_path():
    return Path("tests/fixtures/contemporary_thai_house/project.yaml")


def test_normalize_direction():
    assert normalize_direction("front") == "FRONT"
    assert normalize_direction("SOUTH") == "FRONT"
    assert normalize_direction("1") == "FRONT"
    assert normalize_direction("rear") == "REAR"
    assert normalize_direction("NORTH") == "REAR"
    assert normalize_direction("2") == "REAR"
    assert normalize_direction("right") == "RIGHT"
    assert normalize_direction("EAST") == "RIGHT"
    assert normalize_direction("3") == "RIGHT"
    assert normalize_direction("left") == "LEFT"
    assert normalize_direction("WEST") == "LEFT"
    assert normalize_direction("4") == "LEFT"


def test_project_2d_elevation_all_four_directions(project_manifest_path):
    manifest = load_manifest(project_manifest_path)

    for direction in ["FRONT", "REAR", "RIGHT", "LEFT"]:
        res: ElevationResult = project_2d_elevation(manifest, direction=direction)

        assert res.direction == direction
        assert len(res.elements) > 0
        assert len(res.level_markers) >= 2
        assert len(res.grid_lines) >= 2
        assert res.bounds[2] > res.bounds[0]  # max_u > min_u
        assert res.bounds[3] > res.bounds[1]  # max_v > min_v

        # Check ground line present
        ground_elems = [e for e in res.elements if e.category == "ground"]
        assert len(ground_elems) > 0

        # Check level markers have ground level ±0.00
        ground_markers = [m for m in res.level_markers if "±0.00" in m.display_text or "±0.00" in m.label]
        assert len(ground_markers) > 0


def test_elevation_svg_dom_generation(project_manifest_path):
    cfg = SheetConfig(
        id="A-201",
        title="รูปด้าน 1 (Front Elevation)",
        view_type="ELEVATION",
        elevation_direction="FRONT",
        paper_size="A3",
        orientation="landscape",
        scale=100,
    )

    renderer = SheetRenderer(project_manifest_path, cfg)
    svg_content = renderer.render_svg()

    assert '<?xml version="1.0" encoding="UTF-8"?>' in svg_content
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in svg_content
    assert 'class="level-line"' in svg_content
    assert 'class="level-symbol"' in svg_content
    assert 'class="level-text"' in svg_content
    assert 'class="grid-line"' in svg_content
    assert 'class="grid-bubble"' in svg_content
    assert 'class="grid-text"' in svg_content
    assert 'class="ground-line"' in svg_content
    assert "รูปด้าน 1" in svg_content


def test_elevation_integration_in_2d_viewer(project_manifest_path):
    html = generate_2d_viewer_html(project_manifest_path)

    assert "A-201" in html
    assert "A-202" in html
    assert "A-203" in html
    assert "A-204" in html
    assert "Front Elevation" in html or "รูปด้าน 1" in html
    assert "Rear Elevation" in html or "รูปด้าน 2" in html
    assert "Right Elevation" in html or "รูปด้าน 3" in html
    assert "Left Elevation" in html or "รูปด้าน 4" in html
