"""
Unit tests for Standalone Interactive 2D HTML Viewer (debim.draw.viewer_2d).
Tests HTML generation, template substitution, SVG sheet embedding, standalone file export,
and CLI command integration ('debim draw view').
"""

import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from debim.cli import app
from debim.draw.renderer import SheetConfig
from debim.draw.viewer_2d import export_2d_viewer, generate_2d_viewer_html


@pytest.fixture
def project_manifest_path():
    return Path("tests/fixtures/contemporary_thai_house/project.yaml")


def test_generate_2d_viewer_html_basic(project_manifest_path):
    html_content = generate_2d_viewer_html(project_manifest_path)

    assert "<!DOCTYPE html>" in html_content
    assert "debim 2D Viewer" in html_content
    assert "const sheetsData =" in html_content

    # Check that SVG DOM content is embedded inside JSON payload
    assert "<svg" in html_content
    assert 'class=\\"cut-heavy\\"' in html_content or 'class=\\"cut-medium\\"' in html_content or 'class=\\"grid-line\\"' in html_content


def test_generate_2d_viewer_html_with_custom_sheets(project_manifest_path):
    custom_configs = [
        SheetConfig(id="A-101", title="Ground Floor Architectural Plan", paper_size="A3", scale=100),
        SheetConfig(id="S-101", title="Ground Floor Framing Plan", paper_size="A3", scale=100),
    ]

    html_content = generate_2d_viewer_html(project_manifest_path, sheets_dir_or_configs=custom_configs)

    assert "A-101" in html_content
    assert "S-101" in html_content
    assert "Ground Floor Architectural Plan" in html_content
    assert "Ground Floor Framing Plan" in html_content


def test_export_2d_viewer_to_file(tmp_path, project_manifest_path):
    output_file = tmp_path / "dist" / "viewer_2d.html"
    res_path = export_2d_viewer(project_manifest_path, output_path=output_file)

    assert res_path.exists()
    assert res_path == output_file
    file_content = res_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in file_content
    assert len(file_content) > 5000


def test_cli_draw_view_command(tmp_path, project_manifest_path):
    runner = CliRunner()
    output_html = tmp_path / "viewer_2d.html"

    result = runner.invoke(
        app,
        ["draw", "view", "-m", str(project_manifest_path), "-o", str(output_html)],
    )

    assert result.exit_code == 0
    assert "2D Blueprint Viewer Export Successful" in result.output
    assert output_html.exists()
    assert "<!DOCTYPE html>" in output_html.read_text(encoding="utf-8")
