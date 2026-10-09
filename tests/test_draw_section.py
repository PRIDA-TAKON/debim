"""
Unit tests for 2D Architectural Section Engine (debim.draw.section and debim.draw.renderer).
Tests vertical section cut-plane slicing (Section A-A, Section B-B), cross-section geometry,
background projections, CAD hatching, storey level markers, section callouts on plans,
and multi-sheet 2D viewer integration.
"""

from pathlib import Path
import pytest
import yaml

from debim.draw import (
    SectionCutElement,
    SectionCutPlaneResult,
    SectionProjectionElement,
    SheetConfig,
    SheetRenderer,
    StoreyLevelMarker,
    generate_2d_viewer_html,
    project_2d_section,
    render_sheet,
    slice_section,
)
from debim.schema import ProjectManifest, load_manifest

FARNSWORTH_PATH = Path("examples/farnsworth_house/project.yaml")
THAI_HOUSE_PATH = Path("tests/fixtures/contemporary_thai_house/project.yaml")


def test_section_a_a_and_b_b_cut_geometry():
    """Test vertical section slicing on Farnsworth House model for Section A-A and B-B."""
    assert FARNSWORTH_PATH.exists()
    manifest = load_manifest(FARNSWORTH_PATH)

    # Section A-A (Cut plane parallel to X, equation Y = 0.0)
    sec_a = slice_section(manifest, section_id="A-A", plane_axis="Y", position=0.0)

    assert isinstance(sec_a, SectionCutPlaneResult)
    assert sec_a.section_id == "A-A"
    assert sec_a.plane_axis == "Y"
    assert sec_a.position == 0.0
    assert len(sec_a.cut_elements) > 0
    assert len(sec_a.projection_elements) > 0
    assert len(sec_a.level_markers) > 0

    cut_tags = {e.tag for e in sec_a.cut_elements}
    # Columns along Y=0 line cut by plane
    assert "COL-A1" in cut_tags or "COL-A2" in cut_tags
    # Glass south wall along Y=0
    assert "GLASS-SOUTH" in cut_tags or "FASCIA-FLOOR-SOUTH" in cut_tags

    proj_tags = {e.tag for e in sec_a.projection_elements}
    # Core walls behind Y=0 in background
    assert "CORE-SOUTH" in proj_tags or "CORE-NORTH" in proj_tags or "COL-B1" in proj_tags

    # Section B-B (Cut plane parallel to Y, equation X = 6.7)
    sec_b = project_2d_section(manifest, section_id="B-B", plane_axis="X", position=6.7)

    assert sec_b.section_id == "B-B"
    assert sec_b.plane_axis == "X"
    assert sec_b.position == 6.7
    assert len(sec_b.cut_elements) > 0
    assert len(sec_b.projection_elements) > 0

    # Bounds check
    min_u, min_z, max_u, max_z = sec_a.bounds
    assert min_u < max_u
    assert min_z < max_z


def test_section_hatching_and_svg_renderer():
    """Test SVG sheet rendering for Section views with CAD hatching and level markers."""
    manifest = load_manifest(FARNSWORTH_PATH)

    cfg_a301 = SheetConfig(
        id="A-301",
        title="รูปตัด A-A (Section A-A)",
        view_type="section",
        section_id="A-A",
        section_axis="Y",
        section_position=0.0,
        scale=100,
    )

    renderer = SheetRenderer(manifest, cfg_a301)
    svg_content = renderer.render_svg()

    # Verify CAD Hatch Patterns in <defs>
    assert '<pattern id="hatch-concrete"' in svg_content
    assert '<pattern id="hatch-wall"' in svg_content

    # Verify cut elements receive hatching classes
    assert 'class="cut-concrete"' in svg_content or 'class="cut-wall"' in svg_content or 'class="cut-heavy"' in svg_content
    assert 'data-hatch="concrete"' in svg_content or 'data-hatch="wall"' in svg_content

    # Verify Storey Level Markers (Elevations)
    assert 'class="level-line"' in svg_content
    assert 'class="level-symbol"' in svg_content
    assert 'class="level-marker-text"' in svg_content
    assert "Living Level" in svg_content or "+1.60" in svg_content or "±0.00" in svg_content

    # Verify Title Block
    assert 'id="title-block"' in svg_content
    assert "A-301" in svg_content
    assert "Section A-A" in svg_content or "รูปตัด A-A" in svg_content


def test_section_callouts_on_floor_plan():
    """Test that Floor Plan sheet (A-101) includes Section Callout symbols (A-A / B-B arrow bubbles)."""
    manifest = load_manifest(FARNSWORTH_PATH)

    cfg_plan = SheetConfig(
        id="A-101",
        title="Ground Floor Plan",
        view_type="plan",
    )

    renderer = SheetRenderer(manifest, cfg_plan)
    svg_content = renderer.render_svg()

    # Section Callout DOM Primitives
    assert 'class="section-callout-line"' in svg_content
    assert 'class="section-callout-bubble"' in svg_content
    assert 'class="section-callout-arrow"' in svg_content
    assert 'class="section-callout-text"' in svg_content
    assert "A-301" in svg_content
    assert "A-302" in svg_content


def test_multi_sheet_2d_viewer_integration():
    """Test that standalone 2D viewer embeds default Section sheets A-301 and A-302."""
    assert THAI_HOUSE_PATH.exists()
    html_content = generate_2d_viewer_html(THAI_HOUSE_PATH)

    assert "<!DOCTYPE html>" in html_content
    assert "A-101" in html_content
    assert "A-301" in html_content
    assert "A-302" in html_content
    assert "Section A-A" in html_content or "รูปตัด A-A" in html_content
    assert "Section B-B" in html_content or "รูปตัด B-B" in html_content
