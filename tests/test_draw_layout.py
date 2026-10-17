"""
Unit tests for Paper Space Layout Engine (A3/A2/A1) with Title Block and dynamic metadata propagation.
"""

from pathlib import Path
import pytest
import yaml

from debim.draw import (
    export_paper_space_layout_dxf,
    export_paper_space_layout_set,
    export_paper_space_layout_svg,
)
from debim.draw.renderer import SheetConfig, SheetRenderer
from debim.resolver import resolve_manifest
from debim.schema import ProjectManifest, load_manifest


@pytest.fixture
def project_manifest_path():
    return Path("tests/fixtures/contemporary_thai_house/project.yaml")


def test_paper_space_sheet_geometry():
    cfg_a3 = SheetConfig(paper_size="A3", orientation="landscape", binding_margin_enabled=True)
    w, h = cfg_a3.get_paper_dimensions_mm()
    assert w == 420.0
    assert h == 297.0
    m_left, m_top, m_right, m_bottom = cfg_a3.get_margins_mm()
    assert m_left == 20.0
    assert m_top == 10.0
    assert m_right == 10.0
    assert m_bottom == 10.0

    cfg_a2 = SheetConfig(paper_size="A2", orientation="landscape", binding_margin_enabled=True)
    w2, h2 = cfg_a2.get_paper_dimensions_mm()
    assert w2 == 594.0
    assert h2 == 420.0

    cfg_a1 = SheetConfig(paper_size="A1", orientation="landscape", binding_margin_enabled=True)
    w1, h1 = cfg_a1.get_paper_dimensions_mm()
    assert w1 == 841.0
    assert h1 == 594.0


def test_dynamic_project_metadata_propagation(project_manifest_path):
    manifest = load_manifest(project_manifest_path)
    manifest.project.engineer_name = "นายสมศักดิ์ มั่นคง"
    manifest.project.engineer_license = "วศ. 98765"
    manifest.project.engineer_role = "วิศวกรโครงสร้างหลัก"
    manifest.project.architect_name = "นายสมชาย สถาปนิก"
    manifest.project.architect_license = "สถ. 12345"

    resolved = resolve_manifest(manifest)
    cfg = SheetConfig(id="S-101", title="แปลนฐานรากและเสา", paper_size="A3")

    svg_out = export_paper_space_layout_svg(resolved, cfg)

    assert "นายสมศักดิ์ มั่นคง (วศ. 98765)" in svg_out
    assert "วิศวกรโครงสร้างหลัก" in svg_out
    assert "PROFESSIONAL STAMP & SIGNATURE" in svg_out
    assert "signature-box" in svg_out


def test_changing_engineer_name_instantly_updates_title_block(project_manifest_path):
    manifest = load_manifest(project_manifest_path)

    manifest.project.engineer_name = "วิศวกร คนที่ 1"
    manifest.project.engineer_license = "วศ. 1111"
    resolved1 = resolve_manifest(manifest)
    svg1 = export_paper_space_layout_svg(resolved1, SheetConfig(id="S-101"))
    assert "วิศวกร คนที่ 1 (วศ. 1111)" in svg1

    manifest.project.engineer_name = "วิศวกร คนที่ 2"
    manifest.project.engineer_license = "วศ. 2222"
    resolved2 = resolve_manifest(manifest)
    svg2 = export_paper_space_layout_svg(resolved2, SheetConfig(id="S-101"))
    assert "วิศวกร คนที่ 2 (วศ. 2222)" in svg2
    assert "วิศวกร คนที่ 1" not in svg2


def test_sheet_numbering_and_set_export(project_manifest_path, tmp_path):
    sheets = [
        SheetConfig(id="A-101", title="แปลนพื้นชั้น 1"),
        SheetConfig(id="A-102", title="แปลนพื้นชั้น 2"),
        SheetConfig(id="S-101", title="แปลนวิศวกรรมโครงสร้าง"),
    ]

    results = export_paper_space_layout_set(
        project_manifest_path,
        sheets,
        output_dir=tmp_path / "layout_set",
    )

    assert len(results) == 3
    # Verify file output
    exported_files = list((tmp_path / "layout_set").glob("*.svg"))
    assert len(exported_files) == 3

    # Verify Sheet X of N numbering in title block
    svg_a101 = results[0][1]
    assert "A-101 (1/3)" in svg_a101

    svg_a102 = results[1][1]
    assert "A-102 (2/3)" in svg_a102


def test_paper_space_dxf_layout_export(project_manifest_path, tmp_path):
    dxf_out = tmp_path / "paper_space_layout.dxf"
    res_path = export_paper_space_layout_dxf(
        project_manifest_path,
        output_path=dxf_out,
        sheet_config=SheetConfig(id="A-101", paper_size="A3"),
    )
    assert res_path.exists()
    assert res_path.stat().st_size > 0
