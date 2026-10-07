"""
Unit tests for 2D Architectural Sheet Renderer (debim.draw.renderer).
Tests sheet configuration parsing, SVG DOM generation, paper sizes, viewBox calculations,
CSS lineweights, Thai Google Fonts embedding, annotative scaling, text background masking,
automatic grid dimensions, title block, and Sheet Index table generation.
"""

from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
import yaml

from debim.draw.renderer import (
    CropBox,
    PAPER_SIZES_MM,
    SheetConfig,
    SheetIndexItem,
    SheetRenderer,
    VisibilityFilter,
    load_sheet_config,
    render_sheet,
    render_sheet_set,
)
from debim.schema import load_manifest


@pytest.fixture
def project_manifest_path():
    return Path("tests/fixtures/contemporary_thai_house/project.yaml")


def test_sheet_config_defaults_and_paper_dimensions():
    cfg = SheetConfig()
    assert cfg.id == "A-101"
    assert cfg.paper_size == "A3"
    assert cfg.orientation == "landscape"
    assert cfg.scale == 100
    assert cfg.margin_mm == 10.0

    # A3 Landscape dimensions
    w, h = cfg.get_paper_dimensions_mm()
    assert w == 420.0
    assert h == 297.0

    # A4 Portrait dimensions
    cfg_a4 = SheetConfig(paper_size="A4", orientation="portrait")
    w_a4, h_a4 = cfg_a4.get_paper_dimensions_mm()
    assert w_a4 == 210.0
    assert h_a4 == 297.0

    # A1 Landscape dimensions
    cfg_a1 = SheetConfig(paper_size="A1", orientation="landscape")
    w_a1, h_a1 = cfg_a1.get_paper_dimensions_mm()
    assert w_a1 == 841.0
    assert h_a1 == 594.0


def test_sheet_config_yaml_loading(tmp_path):
    yaml_content = """
id: "A-102"
title: "Second Floor Plan"
paper_size: "A2"
orientation: "landscape"
scale: 50
storey_id: "storey_2"
cut_offset_z: 1.50
crop: [0.0, 0.0, 15.0, 12.0]
visibility:
  show_grid: true
  show_dimensions: true
  show_title_block: true
client_name: "นายสมชาย ใจดี"
architect_name: "debim Studio"
"""
    yaml_file = tmp_path / "sheet_a102.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    cfg = load_sheet_config(yaml_file)
    assert cfg.id == "A-102"
    assert cfg.title == "Second Floor Plan"
    assert cfg.paper_size == "A2"
    assert cfg.scale == 50
    assert cfg.storey_id == "storey_2"
    assert cfg.cut_offset_z == 1.50
    assert isinstance(cfg.crop, CropBox)
    assert cfg.crop.min_x == 0.0
    assert cfg.crop.max_x == 15.0
    assert cfg.client_name == "นายสมชาย ใจดี"


def test_svg_dom_generation_and_viewbox(project_manifest_path):
    cfg = SheetConfig(
        id="A-101",
        title="ผังพื้นชั้น 1 (Ground Floor Plan)",
        paper_size="A3",
        orientation="landscape",
        scale=100,
    )

    renderer = SheetRenderer(project_manifest_path, cfg)
    svg_content = renderer.render_svg()

    assert svg_content.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in svg_content
    assert 'viewBox="0 0 420.0 297.0"' in svg_content
    assert 'width="420.0mm"' in svg_content
    assert 'height="297.0mm"' in svg_content

    # Check embedded Google Fonts import
    assert "https://fonts.googleapis.com/css2?family=Prompt" in svg_content
    assert "family=Sarabun" in svg_content


def test_lineweights_and_architectural_classes(project_manifest_path):
    svg_content = render_sheet(project_manifest_path)

    # Check CSS class definitions in embedded style
    assert ".cut-heavy {" in svg_content
    assert "stroke-width: 0.50mm;" in svg_content
    assert ".cut-medium {" in svg_content
    assert "stroke-width: 0.35mm;" in svg_content
    assert ".projection {" in svg_content
    assert "stroke-width: 0.18mm;" in svg_content
    assert ".grid-line {" in svg_content
    assert "stroke-dasharray:" in svg_content

    # Check SVG elements rendered with architectural classes
    assert 'class="cut-heavy"' in svg_content
    assert 'class="cut-medium"' in svg_content
    assert 'class="projection"' in svg_content
    assert 'class="grid-line"' in svg_content
    assert 'class="grid-bubble"' in svg_content
    assert 'class="grid-text"' in svg_content


def test_annotative_scaling_and_masking(project_manifest_path):
    svg_content = render_sheet(project_manifest_path)

    # Check annotative CSS typography rules
    assert ".dimension-text {" in svg_content
    assert "font-size: 2.0mm;" in svg_content
    assert ".room-tag {" in svg_content
    assert "font-size: 3.5mm;" in svg_content
    assert ".sheet-title {" in svg_content
    assert "font-size: 5.0mm;" in svg_content

    # Check background mask rects
    assert 'class="text-mask"' in svg_content
    assert 'fill="#ffffff"' in svg_content


def test_automatic_dimensions_and_title_block(project_manifest_path):
    cfg = SheetConfig(
        id="A-101",
        title="ผังพื้นชั้น 1",
        project_name="บ้านพักอาศัยสองชั้น",
        client_name="คุณสมชาย",
        scale=100,
        sheet_index=[
            SheetIndexItem(sheet_no="A-101", title="ผังพื้นชั้น 1", scale="1:100"),
            SheetIndexItem(sheet_no="A-102", title="ผังพื้นชั้น 2", scale="1:100"),
            SheetIndexItem(sheet_no="A-201", title="รูปด้าน 1-2", scale="1:100"),
        ],
    )

    renderer = SheetRenderer(project_manifest_path, cfg)
    svg_content = renderer.render_svg()

    # Dimension primitives
    assert 'class="dimension-line"' in svg_content
    assert 'class="dimension-tick"' in svg_content
    assert 'class="dimension-text"' in svg_content

    # Title Block
    assert 'id="title-block"' in svg_content
    assert "PROJECT / โครงการ" in svg_content
    assert "บ้านพักอาศัยสองชั้น" in svg_content
    assert "ผังพื้นชั้น 1" in svg_content
    assert "1:100" in svg_content
    assert "คุณสมชาย" in svg_content

    # Sheet Index Table
    assert "SHEET INDEX /สารบัญแบบ" in svg_content
    assert "A-101" in svg_content
    assert "A-102" in svg_content
    assert "A-201" in svg_content


def test_crop_box_and_visibility_filters(project_manifest_path):
    cfg = SheetConfig(
        crop=(0.0, 0.0, 8.0, 8.0),
        visibility=VisibilityFilter(
            show_grid=False,
            show_dimensions=False,
            show_title_block=False,
        ),
    )

    renderer = SheetRenderer(project_manifest_path, cfg)
    svg_content = renderer.render_svg()

    # Grid and dimensions should be omitted
    assert 'class="grid-line"' not in svg_content
    assert 'class="dimension-line"' not in svg_content
    assert 'id="title-block"' not in svg_content

    # Building cut elements should still be rendered
    assert 'class="cut-heavy"' in svg_content or 'class="cut-medium"' in svg_content


def test_render_sheet_set(tmp_path, project_manifest_path):
    sheet1_content = """
id: "A-101"
title: "Ground Floor Plan"
paper_size: "A3"
scale: 100
"""
    sheet2_content = """
id: "A-102"
title: "Second Floor Plan"
paper_size: "A3"
scale: 100
"""
    sheets_dir = tmp_path / "sheets"
    sheets_dir.mkdir()
    (sheets_dir / "A-101.yaml").write_text(sheet1_content, encoding="utf-8")
    (sheets_dir / "A-102.yaml").write_text(sheet2_content, encoding="utf-8")

    results = render_sheet_set(project_manifest_path, sheets_dir)

    assert len(results) == 2
    cfg1, svg1 = results[0]
    cfg2, svg2 = results[1]

    assert cfg1.id == "A-101"
    assert cfg2.id == "A-102"
    assert len(svg1) > 1000
    assert len(svg2) > 1000
    assert "A-101" in svg1
    assert "A-102" in svg1


def test_save_svg(tmp_path, project_manifest_path):
    renderer = SheetRenderer(project_manifest_path)
    output_file = tmp_path / "output_sheet.svg"
    saved_path = renderer.save_svg(output_file)

    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8").startswith('<?xml version="1.0"')
