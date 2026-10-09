"""
Unit tests for Declarative & Flexible Title Block in 2D Blueprint Engine.
"""

from pathlib import Path
import pytest
import yaml

from debim.draw.renderer import (
    SheetConfig,
    SheetRenderer,
    TitleBlockConfig,
    TitleBlockField,
    render_sheet,
)
from debim.schema import load_manifest


@pytest.fixture
def project_manifest_path():
    return Path("tests/fixtures/contemporary_thai_house/project.yaml")


def test_title_block_schema_models():
    field = TitleBlockField(
        label="วิศวกรโครงสร้าง",
        value="นายสมชาย มั่นคง (วฟ. 12345)",
        subtext="วุฒิวิศวกรโยธา",
    )
    assert field.label == "วิศวกรโครงสร้าง"
    assert field.value == "นายสมชาย มั่นคง (วฟ. 12345)"
    assert field.subtext == "วุฒิวิศวกรโยธา"

    tb_config = TitleBlockConfig(
        enabled=True,
        layout="horizontal_bottom",
        width_mm=80.0,
        height_mm=36.0,
        fields=[field],
    )
    assert tb_config.layout == "horizontal_bottom"
    assert tb_config.height_mm == 36.0
    assert len(tb_config.fields) == 1

    sheet_cfg = SheetConfig(
        id="A-101",
        title="แปลนพื้นชั้นล่าง",
        paper_size="A3",
        title_block=tb_config,
    )
    assert sheet_cfg.title_block.layout == "horizontal_bottom"
    assert sheet_cfg.title_block.fields[0].label == "วิศวกรโครงสร้าง"


def test_horizontal_bottom_title_block_rendering(project_manifest_path):
    tb_config = TitleBlockConfig(
        enabled=True,
        layout="horizontal_bottom",
        height_mm=36.0,
        fields=[
            TitleBlockField(
                label="สถาปนิกโครงการ",
                value="นายสมชาย ดีไซน์ (สถ. 1122)",
            ),
            TitleBlockField(
                label="วิศวกรโครงสร้าง",
                value="นายวิเชียร โครงสร้าง (สย. 3344)",
                subtext="วุฒิวิศวกรโยธา",
            ),
        ],
    )
    sheet_cfg = SheetConfig(
        id="A-101",
        title="แปลนพื้นชั้นล่าง",
        paper_size="A3",
        orientation="landscape",
        scale=100,
        margin_mm=10.0,
        title_block=tb_config,
    )

    renderer = SheetRenderer(project_manifest_path, sheet_cfg)
    svg_str = renderer.render_svg()

    # Verify horizontal bottom title block container and positioning
    # A3 Landscape = 420mm x 297mm. Margin = 10mm.
    # Printable area: x=10, y=10, w=400, h=277.
    # Title block height = 36mm.
    # title_y = 10 + 277 - 36 = 251.0
    assert 'id="title-block"' in svg_str
    assert 'transform="translate(10.0, 251.0)"' in svg_str
    assert 'width="400.0" height="36.0"' in svg_str

    # Verify custom fields content in SVG
    assert "สถาปนิกโครงการ" in svg_str
    assert "นายสมชาย ดีไซน์ (สถ. 1122)" in svg_str
    assert "วิศวกรโครงสร้าง" in svg_str
    assert "นายวิเชียร โครงสร้าง (สย. 3344)" in svg_str
    assert "วุฒิวิศวกรโยธา" in svg_str


def test_vertical_right_title_block_rendering(project_manifest_path):
    tb_config = TitleBlockConfig(
        enabled=True,
        layout="vertical_right",
        width_mm=80.0,
        fields=[
            TitleBlockField(
                label="วิศวกรไฟฟ้า/สุขาภิบาล",
                value="นายธนา งานระบบ (ภฟ. 5566)",
            )
        ],
    )
    sheet_cfg = SheetConfig(
        id="E-101",
        title="แปลนระบบไฟฟ้า",
        paper_size="A3",
        orientation="landscape",
        margin_mm=10.0,
        title_block=tb_config,
    )

    renderer = SheetRenderer(project_manifest_path, sheet_cfg)
    svg_str = renderer.render_svg()

    # A3 Landscape: printable x=10, y=10, w=400, h=277.
    # Title block width = 80mm.
    # title_x = 10 + 400 - 80 = 330.0
    assert 'id="title-block"' in svg_str
    assert 'transform="translate(330.0, 10.0)"' in svg_str
    assert 'width="80.0" height="277.0"' in svg_str

    assert "วิศวกรไฟฟ้า/สุขาภิบาล" in svg_str
    assert "นายธนา งานระบบ (ภฟ. 5566)" in svg_str


def test_corner_bottom_right_title_block_rendering(project_manifest_path):
    tb_config = TitleBlockConfig(
        enabled=True,
        layout="corner_bottom_right",
        width_mm=90.0,
        height_mm=40.0,
        fields=[
            TitleBlockField(
                label="ผู้อนุมัติแบบ",
                value="นายกเทศมนตรี",
            )
        ],
    )
    sheet_cfg = SheetConfig(
        id="A-102",
        title="รูปด้าน",
        paper_size="A3",
        orientation="landscape",
        margin_mm=10.0,
        title_block=tb_config,
    )

    renderer = SheetRenderer(project_manifest_path, sheet_cfg)
    svg_str = renderer.render_svg()

    # A3 Landscape: printable x=10, y=10, w=400, h=277.
    # Title block size = 90mm x 40mm.
    # title_x = 10 + 400 - 90 = 320.0
    # title_y = 10 + 277 - 40 = 247.0
    assert 'id="title-block"' in svg_str
    assert 'transform="translate(320.0, 247.0)"' in svg_str
    assert 'width="90.0" height="40.0"' in svg_str

    assert "ผู้อนุมัติแบบ" in svg_str
    assert "นายกเทศมนตรี" in svg_str


def test_declarative_yaml_sheet_parsing(project_manifest_path):
    yaml_content = """
id: 'A-101'
title: 'แปลนพื้นชั้นล่าง'
paper_size: 'A3'
scale: 100
title_block:
  layout: 'horizontal_bottom'
  height_mm: 36.0
  fields:
    - label: 'สถาปนิกโครงการ'
      value: 'นายสมชาย ดีไซน์ (สถ. 1122)'
    - label: 'วิศวกรโครงสร้าง'
      value: 'นายวิเชียร โครงสร้าง (สย. 3344)'
    - label: 'วิศวกรไฟฟ้า/สุขาภิบาล'
      value: 'นายธนา งานระบบ (ภฟ. 5566)'
    - label: 'ผู้อนุมัติแบบ'
      value: 'นายอำเภอเมือง / นายกเทศมนตรี'
"""
    sheet_cfg = SheetConfig.model_validate(yaml.safe_load(yaml_content))
    assert sheet_cfg.title_block.layout == "horizontal_bottom"
    assert sheet_cfg.title_block.height_mm == 36.0
    assert len(sheet_cfg.title_block.fields) == 4
    assert sheet_cfg.title_block.fields[0].label == "สถาปนิกโครงการ"

    svg_out = render_sheet(project_manifest_path, sheet_cfg)
    assert 'id="title-block"' in svg_out
    assert "นายสมชาย ดีไซน์ (สถ. 1122)" in svg_out
    assert "นายวิเชียร โครงสร้าง (สย. 3344)" in svg_out
    assert "นายธนา งานระบบ (ภฟ. 5566)" in svg_out
    assert "นายอำเภอเมือง / นายกเทศมนตรี" in svg_out
