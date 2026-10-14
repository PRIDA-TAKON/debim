"""
Unit tests for debim v0.6.0 CLI subcommands:
debim validate (schema, topological continuity, and MEP-structure AABB clash checks)
debim boq --rules cg-v480 (Thai CGD v480 public works pricing, provincial price index, Excel/CSV export)
"""

import os
from pathlib import Path
import pytest

from cli_runner import CliRunner
from debim.cli import app


def test_cli_validate_success(tmp_path):
    """Test debim validate on valid manifest returning exit code 0."""
    valid_yaml = """
project:
  id: PROJ-VAL-OK
  name: Valid Test Model
grids:
  axes_x:
    "1": 0.0
    "2": 4.0
  axes_y:
    A: 0.0
    B: 4.0
spatial_structure:
  storeys:
    - id: L1
      name: Level 1
      elevation: 0.0
      height: 3.5
materials:
  - id: CONC_240
    name: Concrete 240 ksc
    category: concrete
    unit_cost_ref: MAT-CONC
elements:
  - class: IfcFooting
    tag: F-01
    material: CONC_240
    profile:
      shape: BOX
      width: 1.5
      depth: 1.5
      thickness: 0.5
    placement:
      grid: ["1", "A"]
      storey: L1
      offset_z: -0.5
  - class: IfcColumn
    tag: COL-01
    material: CONC_240
    profile:
      shape: BOX
      width: 0.3
      depth: 0.3
    placement:
      grid: ["1", "A"]
      base_storey: L1
      top_storey: L1
      offset_base: [0, 0, 0]
      offset_top: [0, 0, 3.5]
"""
    manifest_file = tmp_path / "valid.debim.yaml"
    manifest_file.write_text(valid_yaml, encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["validate", "-m", str(manifest_file)])
    assert res.exit_code == 0
    assert "Pydantic Schema Validation passed" in res.output
    assert "Topological Continuity Validation passed" in res.output
    assert "AABB Clash Detection passed" in res.output


def test_cli_validate_floating_column_and_clash(tmp_path):
    """Test debim validate reporting diagnostic warnings for floating column and MEP clash."""
    invalid_yaml = """
project:
  id: PROJ-VAL-ERR
  name: Invalid Test Model
grids:
  axes_x:
    "1": 0.0
    "2": 4.0
  axes_y:
    A: 0.0
    B: 4.0
spatial_structure:
  storeys:
    - id: L1
      name: Level 1
      elevation: 0.0
      height: 3.5
materials:
  - id: CONC_240
    name: Concrete 240 ksc
    category: concrete
    unit_cost_ref: MAT-CONC
elements:
  # Floating column suspended at elevation +2.0m without support
  - class: IfcColumn
    tag: COL-FLOAT
    material: CONC_240
    profile:
      shape: BOX
      width: 0.3
      depth: 0.3
    placement:
      grid: ["2", "B"]
      base_storey: L1
      top_storey: L1
      offset_base: [0, 0, 2.0]
      offset_top: [0, 0, 5.0]

  # Beam on level 1
  - class: IfcBeam
    tag: B-101
    material: CONC_240
    profile:
      shape: BOX
      width: 0.2
      depth: 0.4
    placement:
      from_grid: ["1", "A"]
      to_grid: ["2", "A"]
      storey: L1
      offset_z: 3.0

  # MEP Duct passing directly through Beam B-101 causing AABB Clash
  - class: IfcDuctSegment
    tag: DUCT-CLASH
    system_type: SUPPLY_AIR
    width: 0.4
    height: 0.3
    placement:
      storey: L1
      from_grid: ["1", "A"]
      to_grid: ["2", "A"]
      from_offset: [0.5, 0.0, 2.9]
      to_offset: [1.5, 0.0, 2.9]
"""
    manifest_file = tmp_path / "clash.debim.yaml"
    manifest_file.write_text(invalid_yaml, encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["validate", "-m", str(manifest_file)])
    assert res.exit_code == 1
    assert "FLOATING_COLUMN" in res.output or "Floating Column" in res.output
    assert "AABB Clash" in res.output or "MEP vs Structural AABB Clash" in res.output or "Diagnostic Warnings" in res.output


def test_cli_boq_cg_v480(tmp_path):
    """Test debim boq --rules cg-v480 subcommand with province multiplier and Excel export."""
    manifest_yaml = """
project:
  id: PROJ-BOQ-V060
  name: House BOQ Test
grids:
  axes_x:
    "1": 0.0
    "2": 4.0
  axes_y:
    A: 0.0
    B: 5.0
spatial_structure:
  storeys:
    - id: L1
      name: Level 1
      elevation: 0.0
      height: 3.5
materials:
  - id: CONC_240
    name: Concrete 240 ksc
    category: concrete
    unit_cost_ref: MAT-CONC
elements:
  - class: IfcFooting
    tag: F-1
    material: CONC_240
    profile:
      shape: BOX
      width: 1.5
      depth: 1.5
      thickness: 0.5
    placement:
      grid: ["1", "A"]
      storey: L1
      offset_z: -0.5
  - class: IfcColumn
    tag: C-1
    material: CONC_240
    profile:
      shape: BOX
      width: 0.3
      depth: 0.3
    placement:
      grid: ["1", "A"]
      base_storey: L1
      top_storey: L1
      offset_base: [0, 0, 0]
      offset_top: [0, 0, 3.5]
"""
    manifest_file = tmp_path / "boq_house.debim.yaml"
    manifest_file.write_text(manifest_yaml, encoding="utf-8")

    excel_file = tmp_path / "boq_output.xlsx"

    runner = CliRunner()
    res = runner.invoke(app, [
        "boq",
        "-m", str(manifest_file),
        "--rules", "cg-v480",
        "--province", "Chiang Mai",
        "--export-excel", str(excel_file),
    ])

    assert res.exit_code == 0
    assert "แบบ ปร.4 - รายการปริมาณงานและราคา" in res.output
    assert "แบบ ปร.4(พ)" in res.output
    assert "แบบ ปร.5 - สรุปราคากลางค่าก่อสร้าง" in res.output
    assert "Factor F (กรมบัญชีกลาง ว480)" in res.output
    assert "Chiang Mai" in res.output or "ดัชนีราคาจังหวัด" in res.output

    # Verify exported file exists (either .xlsx or fallback .csv)
    assert excel_file.exists() or excel_file.with_suffix(".csv").exists()
