"""
End-to-End CLI & Unit Tests for 'debim draw --batch-pdf' Multi-Sheet Blueprint Plotting Engine.
"""

from pathlib import Path
import sys
import tempfile
import yaml
import pytest

tests_dir = str(Path(__file__).parent)
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

from cli_runner import CliRunner
from debim.cli import app
from debim.draw import export_batch_pdf, generate_default_sheet_configs


SAMPLE_MANIFEST_YAML = """
project:
  name: "บ้านพักอาศัย คสล. 2 ชั้น (Thai Modern Villa)"
  id: "PROJ-BLUEPRINT-01"
  units:
    length: "m"
    area: "m2"
    volume: "m3"
  client_name: "คุณสมชาย ใจดี"
  architect_name: "สถาปนิก ปรีดา ตะก้อง"
  architect_license: "ส-สถ. 12345"
  engineer_name: "วิศวกร สมศักดิ์ มั่นคง"
  engineer_license: "สย. 98765"
  engineer_role: "วิศวกรผู้คำนวณโครงสร้าง"

spatial_structure:
  storeys:
    - id: "FL1"
      name: "ชั้น 1"
      elevation: 0.00
      height: 3.50
    - id: "FL2"
      name: "ชั้น 2"
      elevation: 3.50
      height: 3.20

grids:
  axes_x:
    "1": 0.0
    "2": 4.0
    "3": 8.0
  axes_y:
    "ก": 0.0
    "ข": 5.0
    "ค": 10.0

materials:
  - id: "CONC_240"
    name: "Concrete 240 ksc"
    category: "concrete"
    unit_cost_ref: "MAT-CONC"

elements:
  - tag: "C1"
    class: "IfcColumn"
    material: "CONC_240"
    profile:
      shape: "BOX"
      width: 0.25
      depth: 0.25
    placement:
      grid: ["1", "ก"]
      base_storey: "FL1"
      top_storey: "FL1"

  - tag: "W1"
    class: "IfcWall"
    material: "CONC_240"
    thickness: 0.15
    height: 3.50
    placement:
      from_grid: ["1", "ก"]
      to_grid: ["2", "ก"]
      storey: "FL1"

  - tag: "D1"
    class: "IfcDoor"
    host_wall: "W1"
    dimensions:
      width: 0.90
      height: 2.10
    offset_distance: 1.20

  - tag: "W2"
    class: "IfcWindow"
    host_wall: "W1"
    dimensions:
      width: 1.20
      height: 1.50
    offset_distance: 2.50
"""


@pytest.fixture
def manifest_file(tmp_path):
    m_path = tmp_path / "project.debim.yaml"
    m_path.write_text(SAMPLE_MANIFEST_YAML, encoding="utf-8")
    return m_path


def test_generate_default_sheet_configs(manifest_file):
    configs = generate_default_sheet_configs(manifest_file, paper_size="A3", scale=100)
    assert len(configs) >= 14

    sheet_ids = [c.id for c in configs]
    assert "G-001" in sheet_ids
    assert "A-001" in sheet_ids
    assert "A-101" in sheet_ids
    assert "A-201" in sheet_ids
    assert "A-301" in sheet_ids
    assert "A-401" in sheet_ids
    assert "S-001" in sheet_ids
    assert "S-101" in sheet_ids
    assert "S-102" in sheet_ids
    assert "S-201" in sheet_ids
    assert "EE-001" in sheet_ids
    assert "EE-101" in sheet_ids
    assert "SN-001" in sheet_ids
    assert "SN-101" in sheet_ids


def test_export_batch_pdf_python_api(manifest_file, tmp_path):
    out_pdf = tmp_path / "blueprint_package.pdf"
    res_path = export_batch_pdf(
        manifest_or_resolved=manifest_file,
        output_path=out_pdf,
        paper_size="A3",
        scale="1:100",
    )
    assert res_path.exists()
    assert res_path.stat().st_size > 0


def test_cli_draw_batch_pdf_default(manifest_file, tmp_path):
    runner = CliRunner()
    out_pdf = tmp_path / "cli_blueprints.pdf"

    res = runner.invoke(
        app,
        ["draw", "-m", str(manifest_file), "--layout", "A3", "--scale", "1:100", "--batch-pdf", str(out_pdf)],
    )

    assert res.exit_code == 0
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0
    assert "Multi-Sheet Blueprint Batch PDF Plotting Complete!" in res.output
    assert "PdfCraft Hand-off Ready" in res.output


def test_cli_draw_batch_pdf_custom_layout_scale(manifest_file, tmp_path):
    runner = CliRunner()
    out_pdf = tmp_path / "blueprints_a2_scale50.pdf"

    res = runner.invoke(
        app,
        ["draw", "-m", str(manifest_file), "--layout", "A2", "--scale", "1:50", "--batch-pdf", str(out_pdf)],
    )

    assert res.exit_code == 0
    assert out_pdf.exists()
    assert "Paper Space Layout: A2" in res.output
    assert "Plot Scale: 1:50" in res.output


def test_cli_draw_subcommand_batch_pdf(manifest_file, tmp_path):
    runner = CliRunner()
    out_pdf = tmp_path / "subcommand_blueprints.pdf"

    res = runner.invoke(
        app,
        ["draw", "batch-pdf", "-m", str(manifest_file), "--layout", "A1", "--scale", "1:100", "-o", str(out_pdf)],
    )

    assert res.exit_code == 0
    assert out_pdf.exists()
    assert "Paper Space Layout: A1" in res.output


def test_cli_draw_metadata_propagation(tmp_path):
    runner = CliRunner()

    # Modify engineer and project metadata
    data = yaml.safe_load(SAMPLE_MANIFEST_YAML)
    data["project"]["name"] = "โครงการอาคารสำนักงานนวัตกรรม"
    data["project"]["engineer_name"] = "ดร.วิศวกร ชัยชนะ"
    data["project"]["engineer_license"] = "สย.7777"

    m_path = tmp_path / "custom_project.yaml"
    m_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    out_pdf = tmp_path / "custom_metadata_blueprints.pdf"

    res = runner.invoke(
        app,
        ["draw", "-m", str(m_path), "--layout", "A3", "--scale", "1:100", "--batch-pdf", str(out_pdf)],
    )

    assert res.exit_code == 0
    assert out_pdf.exists()
    assert "โครงการอาคารสำนักงานนวัตกรรม" in res.output
    assert "ดร.วิศวกร ชัยชนะ (สย.7777)" in res.output
