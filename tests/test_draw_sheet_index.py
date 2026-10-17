"""
Unit tests for automated Drawing Sheet Index generator across multi-discipline drawing sets (A, S, EE, SN, G).
"""

from pathlib import Path
import pytest

from debim.draw import (
    DrawingIndexItem,
    SheetConfig,
    SheetRenderer,
    discover_and_aggregate_sheets,
    generate_default_project_sheets,
    infer_discipline,
    render_sheet_index_svg,
    render_sheet_set,
)
from debim.schema import ProjectManifest, load_manifest


@pytest.fixture
def sample_manifest() -> ProjectManifest:
    manifest_path = Path("tests/fixtures/contemporary_thai_house/project.yaml")
    return load_manifest(manifest_path)


def test_infer_discipline():
    assert infer_discipline("G-001") == "G"
    assert infer_discipline("A-101") == "A"
    assert infer_discipline("A-001") == "A"
    assert infer_discipline("S-101") == "S"
    assert infer_discipline("EE-101") == "EE"
    assert infer_discipline("SN-101") == "SN"
    assert infer_discipline("M-101") == "OTHER"

    # Explicit override
    assert infer_discipline("CUSTOM-1", explicit_discipline="Structural") == "S"
    assert infer_discipline("CUSTOM-2", explicit_discipline="Electrical") == "EE"


def test_generate_default_project_sheets(sample_manifest):
    items = generate_default_project_sheets(sample_manifest)
    assert len(items) >= 12
    sheet_nos = [it.sheet_no for it in items]

    assert "G-001" in sheet_nos
    assert "A-001" in sheet_nos
    assert "A-101" in sheet_nos
    assert "S-001" in sheet_nos
    assert "S-101" in sheet_nos
    assert "EE-001" in sheet_nos
    assert "EE-101" in sheet_nos
    assert "SN-001" in sheet_nos
    assert "SN-101" in sheet_nos


def test_discover_and_aggregate_sheets(sample_manifest, tmp_path):
    # Test auto-discovery from explicit SheetConfigs
    configs = [
        SheetConfig(id="A-101", title="Ground Floor Plan", scale=100),
        SheetConfig(id="S-101", title="Foundation Plan", scale=100),
        SheetConfig(id="EE-101", title="Electrical Single Line Diagram", scale=1),
        SheetConfig(id="SN-101", title="Sanitation Riser Diagram", scale=1),
        SheetConfig(id="G-001", title="Master Index", scale=1),
    ]

    items, total_count = discover_and_aggregate_sheets(sample_manifest, configs)
    assert total_count == 5
    # Order should be sorted naturally: G-001, A-101, S-101, EE-101, SN-101
    assert [it.sheet_no for it in items] == ["G-001", "A-101", "S-101", "EE-101", "SN-101"]


def test_render_master_index_g001_svg(sample_manifest):
    cfg = SheetConfig(id="G-001", title="สารบัญแบบรวมทั้งโครงการ", view_type="INDEX")
    svg = render_sheet_index_svg(sample_manifest, cfg)

    assert "<?xml version" in svg
    assert "<svg" in svg
    assert "G-001" in svg
    assert "รวมแบบทั้งชุด" in svg
    assert "TOTAL" in svg
    assert "SHEETS" in svg
    assert "เลขที่แบบ (SHEET NO.)" in svg
    assert "ชื่อแบบ (SHEET TITLE)" in svg
    assert "มาตราส่วน (SCALE)" in svg
    assert "ครั้งที่แก้ไข (REV.)" in svg
    assert "หมายเหตุ (REMARKS)" in svg


def test_render_discipline_specific_index_svg(sample_manifest):
    # Architectural Index Cover A-001
    cfg_a = SheetConfig(id="A-001", title="สารบัญแบบงานสถาปัตยกรรม", view_type="INDEX")
    svg_a = render_sheet_index_svg(sample_manifest, cfg_a)
    assert "A-001" in svg_a
    assert "หมวดงานสถาปัตยกรรม" in svg_a or "งานสถาปัตยกรรม" in svg_a

    # Structural Index Cover S-001
    cfg_s = SheetConfig(id="S-001", title="สารบัญแบบงานวิศวกรรมโครงสร้าง", view_type="INDEX")
    svg_s = render_sheet_index_svg(sample_manifest, cfg_s)
    assert "S-001" in svg_s
    assert "วิศวกรรมโครงสร้าง" in svg_s

    # Electrical Index Cover EE-001
    cfg_ee = SheetConfig(id="EE-001", title="สารบัญแบบงานวิศวกรรมไฟฟ้า", view_type="INDEX")
    svg_ee = render_sheet_index_svg(sample_manifest, cfg_ee)
    assert "EE-001" in svg_ee
    assert "วิศวกรรมไฟฟ้า" in svg_ee

    # Sanitation Index Cover SN-001
    cfg_sn = SheetConfig(id="SN-001", title="สารบัญแบบงานวิศวกรรมสุขาภิบาล", view_type="INDEX")
    svg_sn = render_sheet_index_svg(sample_manifest, cfg_sn)
    assert "SN-001" in svg_sn
    assert "วิศวกรรมสุขาภิบาล" in svg_sn


def test_dynamic_auto_sync_on_sheet_set(sample_manifest):
    # Initial set of configs
    configs = [
        SheetConfig(id="G-001", title="Master Index", view_type="INDEX"),
        SheetConfig(id="A-101", title="Ground Floor Plan"),
        SheetConfig(id="S-101", title="Foundation Plan"),
    ]

    results1 = render_sheet_set(sample_manifest, configs)
    assert len(results1) == 3
    # Check total sheets in title block / index metadata
    g001_svg1 = results1[0][1]
    assert "รวมแบบทั้งชุด 3 แผ่น" in g001_svg1 or "TOTAL 3 SHEETS" in g001_svg1

    # Dynamically add two new sheets and re-run render_sheet_set
    configs.extend([
        SheetConfig(id="A-102", title="Second Floor Plan"),
        SheetConfig(id="EE-101", title="Electrical Single Line Diagram"),
    ])

    results2 = render_sheet_set(sample_manifest, configs)
    assert len(results2) == 5

    g001_svg2 = results2[0][1]
    assert "รวมแบบทั้งชุด 5 แผ่น" in g001_svg2 or "TOTAL 5 SHEETS" in g001_svg2
    assert "A-102" in g001_svg2
    assert "EE-101" in g001_svg2


def test_sheet_renderer_routing_for_index(sample_manifest):
    cfg = SheetConfig(id="G-001", title="Master Drawing Index")
    renderer = SheetRenderer(sample_manifest, cfg)
    svg = renderer.render_svg()
    assert "G-001" in svg
    assert "MASTER DRAWING INDEX" in svg or "สารบัญแบบ" in svg
