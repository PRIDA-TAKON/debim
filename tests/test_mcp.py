"""
Unit tests for debim MCP tools.
"""

from pathlib import Path
import pytest
from debim.mcp import (
    debim_validate,
    debim_qto,
    debim_cost_template,
    debim_cost,
    debim_compile_ifc,
    debim_generate_viewer,
)

SAMPLE_YAML = """
schema: IFC4-Minimal
project:
  id: PRJ-TEST-MCP-01
  name: "MCP Test Pavilion"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }

spatial_structure:
  storeys:
    - { id: Ground, name: "Ground", elevation: 0.0, height: 3.0 }
    - { id: Roof, name: "Roof", elevation: 3.0, height: 0.3 }

grids:
  axes_x: { A: 0.0, B: 5.0 }
  axes_y: { 1: 0.0, 2: 5.0 }

materials:
  - { id: CONC, name: "Concrete 240 ksc", category: concrete, unit_cost_ref: "MAT-CONC-01" }

elements:
  - class: IfcColumn
    tag: C1
    material: CONC
    profile: { shape: BOX, width: 0.3, depth: 0.3 }
    placement: { grid: [A, 1], base_storey: Ground, top_storey: Roof }
  - class: IfcColumn
    tag: C2
    material: CONC
    profile: { shape: BOX, width: 0.3, depth: 0.3 }
    placement: { grid: [B, 2], base_storey: Ground, top_storey: Roof }
"""


def test_mcp_validate():
    res = debim_validate(SAMPLE_YAML)
    assert res["valid"] is True
    assert res["project_id"] == "PRJ-TEST-MCP-01"
    assert res["elements_count"] == 2
    assert res["resolved_columns"] == 2


def test_mcp_validate_invalid():
    res = debim_validate("invalid: [yaml: broken")
    assert res["valid"] is False
    assert "error" in res


def test_mcp_qto():
    res = debim_qto(SAMPLE_YAML)
    assert res["success"] is True
    summary = res["summary"]
    # 2 columns * 0.3 * 0.3 * 3.0 = 0.54 m3
    assert summary["concrete_volume_m3"] == pytest.approx(0.54, rel=1e-2)
    assert summary["formwork_area_m2"] > 0


def test_mcp_cost_template():
    res = debim_cost_template(SAMPLE_YAML)
    assert res["success"] is True
    assert "MAT-CONC-01" in res["prices_template_yaml"]


def test_mcp_cost(tmp_path):
    csv_file = tmp_path / "test_boq.csv"
    res = debim_cost(SAMPLE_YAML, export_csv_path=str(csv_file))
    assert res["success"] is True
    assert res["line_items_count"] > 0
    assert csv_file.exists()


def test_mcp_compile_ifc(tmp_path):
    ifc_file = tmp_path / "model.ifc"
    res = debim_compile_ifc(SAMPLE_YAML, str(ifc_file))
    assert res["success"] is True
    assert ifc_file.exists()
    assert res["file_size_kb"] > 0


def test_mcp_generate_viewer(tmp_path):
    viewer_file = tmp_path / "viewer.html"
    res = debim_generate_viewer(SAMPLE_YAML, str(viewer_file))
    assert res["success"] is True
    assert viewer_file.exists()
    assert res["file_size_kb"] > 0
