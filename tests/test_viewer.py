"""
Unit tests for 3D Viewer generator and local HTTP server (debim.viewer)
"""

import re
from pathlib import Path
from typer.testing import CliRunner
from debim.cli import app
from debim.schema import load_manifest
from debim.viewer import generate_viewer_html

runner = CliRunner()


def test_generate_viewer_html_from_path(sample_project_path: Path):
    html = generate_viewer_html(sample_project_path)
    assert "<!DOCTYPE html>" in html
    assert "three.min.js" in html
    assert "OrbitControls.js" in html

    # Check element tags requirement: C-A1, B-A1_B1, W-A1_A2, D1
    assert "C-A1" in html
    assert "B-A1_B1" in html
    assert "W-A1_A2" in html
    assert "D1" in html

    # Check hierarchical layer tree UI
    assert "Hierarchical Layer Explorer" in html
    assert "layerTreeRoot" in html
    assert "buildLayerTree" in html
    assert "renderLayerTree" in html

    # Check 3D Measurement Tool & ISO Camera default
    assert "toggleMeasureTool" in html
    assert "clearMeasurements" in html
    assert "measure-btn" in html
    assert "Default: ISO View" in html

    # Check project metadata
    assert "Townhouse-Feasibility" in html
    assert "PRJ-2026-001" in html


def test_generate_viewer_html_from_manifest_object(sample_project_path: Path):
    manifest = load_manifest(sample_project_path)
    html = generate_viewer_html(manifest)
    assert "<!DOCTYPE html>" in html
    assert "C-A1" in html
    assert "B-A1_B1" in html


def test_skirting_and_cladding_rendering(tmp_path: Path):
    manifest_yaml = tmp_path / "project.yaml"
    manifest_yaml.write_text(
        """
schema: IFC4-Minimal
project:
  id: PRJ-TEST-COVERING
  name: Covering Test Project
  units:
    length: METER
spatial_structure:
  storeys:
    - id: L1
      name: "Level 1"
      elevation: 0.0
      height: 3.5
grids:
  axes_x:
    "1": 0.0
    "2": 4.0
  axes_y:
    "A": 0.0
    "B": 5.0
materials:
  - id: MAT_WOOD
    name: Wood Finish
    category: FINISH
    unit_cost_ref: REF_WOOD
elements:
  - class: IfcCovering
    tag: SKIRT-1
    covering_type: SKIRTING
    material: MAT_WOOD
    thickness: 0.015
    placement:
      storey: L1
      boundary:
        - ["1", "A"]
        - ["2", "A"]
        - ["2", "B"]
        - ["1", "B"]
  - class: IfcCovering
    tag: CLAD-1
    covering_type: CLADDING
    material: MAT_WOOD
    thickness: 0.02
    placement:
      storey: L1
      boundary:
        - ["1", "A"]
        - ["2", "A"]
"""
    )

    manifest = load_manifest(manifest_yaml)
    html = generate_viewer_html(manifest)

    assert "SKIRT-1" in html
    assert "CLAD-1" in html
    assert "architecture/finishes/skirting" in html
    assert "architecture/finishes/cladding" in html
    assert "Skirting" in html
    assert "Cladding" in html


def test_cli_view_help():
    result = runner.invoke(app, ["view", "--help"])
    assert result.exit_code == 0
    clean_output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.output)
    assert "--manifest" in clean_output or "-m" in clean_output
    assert "--port" in clean_output or "-p" in clean_output
    assert "--no-browser" in clean_output or "no-browser" in clean_output


def test_cli_view_missing_manifest():
    result = runner.invoke(app, ["view", "--manifest", "non_existent.yaml"])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_viewer_live_reload_script_injection(sample_project_path: Path):
    html = generate_viewer_html(sample_project_path, live_reload=True)
    assert "/api/version" in html
    assert "debim Live Hot-Reload Watcher" in html
    assert "sessionStorage.setItem('debim_cam_state'" in html

