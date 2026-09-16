"""
Unit tests for 3D Viewer generator and local HTTP server (debim.viewer)
"""

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

    # Check project metadata
    assert "Townhouse-Feasibility" in html
    assert "PRJ-2026-001" in html


def test_generate_viewer_html_from_manifest_object(sample_project_path: Path):
    manifest = load_manifest(sample_project_path)
    html = generate_viewer_html(manifest)
    assert "<!DOCTYPE html>" in html
    assert "C-A1" in html
    assert "B-A1_B1" in html


def test_cli_view_help():
    result = runner.invoke(app, ["view", "--help"])
    assert result.exit_code == 0
    assert "--manifest" in result.output or "-m" in result.output
    assert "--port" in result.output or "-p" in result.output
    assert "--no-browser" in result.output


def test_cli_view_missing_manifest():
    result = runner.invoke(app, ["view", "--manifest", "non_existent.yaml"])
    assert result.exit_code == 1
    assert "Error" in result.output
