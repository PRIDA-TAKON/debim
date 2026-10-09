"""
Tests for Declarative Building Code Compliance & Thai Regulations.
"""

from pathlib import Path
import pytest

from debim.schema import load_manifest, ProjectManifest
from debim.compliance import ComplianceChecker


def test_declarative_compliance_rules_pass(tmp_path):
    project_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-THAI-COMPLIANCE
  name: "Thai Building Code Test"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }
site:
  bounding_box: [-5.0, -5.0, 15.0, 15.0]
  front_road_width: 6.0
spatial_structure:
  storeys:
    - id: L1
      name: "Ground Floor"
      elevation: 0.0
      height: 3.5
grids:
  axes_x: { "1": 0.0, "2": 4.0 }
  axes_y: { "A": 0.0, "B": 5.0 }
materials:
  - id: CONC_240
    name: "Concrete 240 ksc"
    category: concrete
    unit_cost_ref: "C240"
elements:
  - class: IfcColumn
    tag: "C1"
    material: CONC_240
    profile: { shape: BOX, width: 0.3, depth: 0.3 }
    placement: { grid: ["1", "A"], base_storey: L1, top_storey: L1 }
  - class: IfcWall
    tag: "W01"
    material: CONC_240
    thickness: 0.10
    height: 3.0
    placement: { from_grid: ["1", "A"], to_grid: ["2", "A"], storey: L1 }
compliances:
  - rule: "TH_MIN_CEILING_HEIGHT_240"
    name: "ความสูงเพดานขั้นต่ำ 2.40 ม."
    threshold: 2.40
  - rule: "TH_SETBACK_BLIND_050"
    name: "ระยะร่นผนังทึบขั้นต่ำ 0.50 ม."
    threshold: 0.50
  - rule: "NO_STRUCTURAL_CLASHES"
    name: "ไม่มีการชนกันขององค์ประกอบ 3D"
"""
    p_file = tmp_path / "project.yaml"
    p_file.write_text(project_yaml, encoding="utf-8")

    manifest = load_manifest(p_file)
    assert len(manifest.compliances) == 3
    assert manifest.site is not None

    checker = ComplianceChecker(manifest)
    results = checker.evaluate_manifest_compliances()
    assert len(results) == 3

    for res in results:
        assert res.passed, f"Rule '{res.rule}' failed: {res.message}"


def test_declarative_compliance_rule_violation(tmp_path):
    project_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-THAI-VIOLATION
  name: "Low Ceiling Violation Test"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }
spatial_structure:
  storeys:
    - id: L1
      name: "Low Storey"
      elevation: 0.0
      height: 2.10
grids:
  axes_x: { "1": 0.0 }
  axes_y: { "A": 0.0 }
materials: []
compliances:
  - rule: "TH_MIN_CEILING_HEIGHT_240"
    threshold: 2.40
"""
    p_file = tmp_path / "project.yaml"
    p_file.write_text(project_yaml, encoding="utf-8")

    manifest = load_manifest(p_file)
    checker = ComplianceChecker(manifest)
    results = checker.evaluate_manifest_compliances()

    assert len(results) == 1
    res = results[0]
    assert not res.passed
    assert "Clear height violation" in res.message
