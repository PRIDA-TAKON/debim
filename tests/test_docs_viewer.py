"""
Unit tests for debim Class Directory & Encyclopedia Documentation Engine.
"""

import time
from pathlib import Path
from typer.testing import CliRunner

from debim.cli import app
from debim.docs import (
    DEFAULT_CLASS_DIRECTORY_DATA,
    export_class_directory,
    generate_class_directory_html,
)

runner = CliRunner()


def test_generate_class_directory_html_basic():
    """Test generating Class Directory HTML string."""
    html_str = generate_class_directory_html()
    assert isinstance(html_str, str)
    assert len(html_str) > 1000
    assert "<!DOCTYPE html>" in html_str
    assert "debim BIM Class Directory & Encyclopedia" in html_str


def test_export_class_directory(tmp_path):
    """Test exporting Class Directory webpage to file path."""
    out_file = tmp_path / "directory.html"
    exported_path = export_class_directory(out_file)
    assert exported_path.exists()
    assert exported_path.stat().st_size > 1000
    content = exported_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content


def test_class_directory_disciplines():
    """Test that all 4 required disciplines are covered in catalog data."""
    disciplines = {item["discipline"] for item in DEFAULT_CLASS_DIRECTORY_DATA}
    assert "Structure" in disciplines
    assert "Architecture" in disciplines
    assert "MEP" in disciplines
    assert "Civil" in disciplines


def test_class_directory_6_dimension_viewer_features():
    """Test that generated HTML contains all 6-dimension viewer features."""
    html_str = generate_class_directory_html()

    # 1. Sidebar & Search
    assert 'id="sidebar"' in html_str
    assert 'id="search-input"' in html_str
    assert "filterClasses" in html_str

    # 2. 3D Viewport
    assert 'id="canvas-3d"' in html_str
    assert "toggleWireframe" in html_str
    assert "toggleBBox" in html_str

    # 3. 2D Blueprint View
    assert 'id="tab-2d"' in html_str
    assert 'id="svg-wrapper"' in html_str

    # 4. Rosetta Stone Comparison
    assert 'id="tab-rosetta"' in html_str
    assert "Declarative .debim YAML" in html_str
    assert "Compiled IFC4 STEP" in html_str

    # 5. BOQ & QTO Table
    assert 'id="tab-boq"' in html_str
    assert "boq-tbody" in html_str
    assert "BOQ & QTO" in html_str

    # 6. Thai Specifications
    assert 'id="tab-specs"' in html_str
    assert "ข้อกำหนดทั่วไปและวัสดุ" in html_str
    assert "ข้อกำหนดการฝีมือและการติดตั้ง" in html_str
    assert "ข้อกำหนดการทดสอบและตรวจรับ" in html_str


def test_fast_rendering_performance():
    """Test fast initial generation (< 1 sec execution time)."""
    t0 = time.perf_counter()
    html_str = generate_class_directory_html()
    t1 = time.perf_counter()
    duration = t1 - t0
    assert duration < 1.0, f"Rendering took {duration:.3f} seconds, expected < 1.0s"
    assert len(html_str) > 5000


def test_cli_docs_directory(tmp_path):
    """Test CLI subcommand 'debim docs directory'."""
    out_file = tmp_path / "class_directory.html"
    result = runner.invoke(app, ["docs", "directory", "-o", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    assert out_file.stat().st_size > 5000
    assert "Class Directory Web Application Exported Successfully" in result.output
