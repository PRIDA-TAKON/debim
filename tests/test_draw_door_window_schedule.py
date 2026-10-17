"""
Unit tests for architectural Door & Window schedules, 2D vector elevations,
hardware specifications, and sheet rendering (A-401).
"""

from pathlib import Path
import pytest

from debim.draw import (
    SheetConfig,
    SheetRenderer,
    extract_opening_schedule,
    render_2d_opening_elevation_svg,
    render_opening_schedule_svg,
    render_schedule_card_svg,
)
from debim.resolver import SpatialResolver
from debim.schema import (
    Dimensions,
    IfcDoor,
    IfcWall,
    IfcWindow,
    ProjectManifest,
    load_manifest,
)


@pytest.fixture
def sample_house_manifest() -> ProjectManifest:
    """Load sample townhouse or contemporary house manifest."""
    manifest_path = Path(__file__).parent / "fixtures" / "contemporary_thai_house" / "project.yaml"
    if manifest_path.exists():
        return load_manifest(manifest_path)

    # Synthetic fallback manifest if fixture file not found
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "P1", "name": "Schedule Test House"},
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 4.0, "C": 8.0},
        },
        "materials": [
            {"id": "CONC", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "C1"},
            {"id": "BRICK", "name": "Brick", "category": "MASONRY", "unit_cost_ref": "M1"},
        ],
        "elements": [
            {
                "class": "IfcWall",
                "tag": "WALL-1",
                "material": "BRICK",
                "thickness": 0.10,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "L1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "D-01",
                        "dimensions": {"width": 0.90, "height": 2.00},
                        "offset_distance": 0.50,
                        "sill_height": 0.00,
                        "material": "TEAK_WOOD",
                        "operation_type": "SWING",
                    },
                    {
                        "class": "IfcWindow",
                        "tag": "W-01",
                        "dimensions": {"width": 1.60, "height": 1.20},
                        "offset_distance": 2.00,
                        "sill_height": 0.90,
                        "material": "ALUMINUM",
                        "operation_type": "SLIDING",
                    },
                ],
            },
            {
                "class": "IfcWall",
                "tag": "WALL-2",
                "material": "BRICK",
                "thickness": 0.10,
                "height": 3.0,
                "placement": {"from_grid": ["2", "A"], "to_grid": ["3", "A"], "storey": "L1"},
                "children": [
                    {
                        "class": "IfcDoor",
                        "tag": "D-02",
                        "dimensions": {"width": 0.90, "height": 2.00},
                        "offset_distance": 0.50,
                        "sill_height": 0.00,
                        "material": "TEAK_WOOD",
                        "operation_type": "SWING",
                    },
                    {
                        "class": "IfcWindow",
                        "tag": "W-02",
                        "dimensions": {"width": 1.60, "height": 1.20},
                        "offset_distance": 2.00,
                        "sill_height": 0.90,
                        "material": "ALUMINUM",
                        "operation_type": "SLIDING",
                    },
                    {
                        "class": "IfcDoor",
                        "tag": "D-03-SLIDING",
                        "dimensions": {"width": 1.80, "height": 2.05},
                        "offset_distance": 1.00,
                        "sill_height": 0.00,
                        "material": "ALUMINUM",
                        "operation_type": "SLIDING",
                    },
                ],
            },
        ],
    }
    return ProjectManifest.model_validate(manifest_data)


def test_extract_opening_schedule(sample_house_manifest: ProjectManifest):
    """Test door and window schedule extraction and automated quantity count aggregation."""
    resolved = SpatialResolver(sample_house_manifest).resolve()
    doors, windows = extract_opening_schedule(resolved)

    assert len(doors) >= 1
    assert len(windows) >= 1

    # Total quantity count across doors and windows must match instances in model
    tot_doors_count = sum(d.quantity for d in doors)
    tot_windows_count = sum(w.quantity for w in windows)

    assert tot_doors_count >= 3
    assert tot_windows_count >= 2

    # Verify type tags
    for i, d in enumerate(doors, 1):
        assert d.type_tag == f"D{i}"
        assert d.category == "DOOR"
        assert d.quantity == len(d.instances)
        assert d.frame_material is not None
        assert d.hardware is not None

    for j, w in enumerate(windows, 1):
        assert w.type_tag == f"W{j}"
        assert w.category == "WINDOW"
        assert w.quantity == len(w.instances)
        assert w.frame_material is not None
        assert w.hardware is not None


def test_render_2d_opening_elevation_svg(sample_house_manifest: ProjectManifest):
    """Test 2D vector elevation SVG rendering for doors and windows."""
    resolved = SpatialResolver(sample_house_manifest).resolve()
    doors, windows = extract_opening_schedule(resolved)

    d1 = doors[0]
    d_svg = render_2d_opening_elevation_svg(d1)

    assert "<svg" not in d_svg  # Fragment inside <g>
    assert f'id="elevation-{d1.type_tag}"' in d_svg
    assert 'class="opening-frame"' in d_svg
    assert 'class="opening-panel"' in d_svg
    assert f'{d1.width:.2f}' in d_svg
    assert f'{d1.height:.2f}' in d_svg

    w1 = windows[0]
    w_svg = render_2d_opening_elevation_svg(w1)
    assert f'id="elevation-{w1.type_tag}"' in w_svg
    assert 'class="opening-frame"' in w_svg
    assert f'{w1.width:.2f}' in w_svg
    assert f'{w1.height:.2f}' in w_svg


def test_render_schedule_card_svg(sample_house_manifest: ProjectManifest):
    """Test schedule card SVG rendering with hardware specification table."""
    resolved = SpatialResolver(sample_house_manifest).resolve()
    doors, _ = extract_opening_schedule(resolved)

    d1 = doors[0]
    card_svg = render_schedule_card_svg(d1)

    assert f'id="card-{d1.type_tag}"' in card_svg
    assert "แบบขยายประตู-หน้าต่าง" in card_svg
    assert f"QTY: {d1.quantity}" in card_svg
    assert d1.frame_material in card_svg
    assert d1.panel_glazing in card_svg


def test_render_opening_schedule_svg_sheet(sample_house_manifest: ProjectManifest):
    """Test complete A-401 drawing sheet rendering for door & window schedule."""
    resolved = SpatialResolver(sample_house_manifest).resolve()

    cfg = SheetConfig(
        id="A-401",
        title="Door and Window Schedule and Hardware Specifications",
        view_type="SCHEDULE",
        paper_size="A3",
    )

    svg_content = render_opening_schedule_svg(resolved, cfg)

    assert '<?xml version="1.0" encoding="UTF-8"?>' in svg_content
    assert '<svg' in svg_content
    assert 'id="schedule-viewport"' in svg_content
    assert "แบบขยายประตู-หน้าต่าง และรายการอุปกรณ์" in svg_content
    assert 'id="title-block"' in svg_content
    assert "</svg>" in svg_content


def test_sheet_renderer_schedule_integration(sample_house_manifest: ProjectManifest):
    """Test integration into SheetRenderer and view_type normalization."""
    resolved = SpatialResolver(sample_house_manifest).resolve()

    cfg = SheetConfig(
        id="A-401",
        title="Door and Window Schedule",
        view_type="DOOR_WINDOW_SCHEDULE",
        paper_size="A3",
    )

    assert cfg.view_type == "SCHEDULE"

    renderer = SheetRenderer(resolved, cfg)
    svg_out = renderer.render_svg()

    assert 'id="schedule-viewport"' in svg_out
    assert "DOOR &amp; WINDOW ELEVATIONS" in svg_out
