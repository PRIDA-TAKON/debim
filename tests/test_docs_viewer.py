"""
Unit tests for debim Class Directory & Encyclopedia Documentation Engine.
"""

import re
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


def test_125_class_coverage():
    """Test that DEFAULT_CLASS_DIRECTORY_DATA and HTML output cover all 125+ IFC physical element classes."""
    assert len(DEFAULT_CLASS_DIRECTORY_DATA) >= 125
    html_str = generate_class_directory_html()
    matches = re.findall(r'\"class_name\":\s*\"([^\"]+)\"', html_str)
    assert len(matches) >= 125, f"Expected >= 125 classes, found {len(matches)}"


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


def test_procedural_3d_shapes_payloads():
    """Test that architectural and circulation classes return procedural sample_3d payloads."""
    by_class = {item["class_name"]: item["sample_3d"] for item in DEFAULT_CLASS_DIRECTORY_DATA}

    assert by_class["IfcStair"]["shape"] == "stair_flight"
    assert by_class["IfcStair"]["steps"] == 10
    assert by_class["IfcStairFlight"]["shape"] == "stair_flight"

    assert by_class["IfcRamp"]["shape"] == "ramp"
    assert by_class["IfcRampFlight"]["shape"] == "ramp"

    assert by_class["IfcRailing"]["shape"] == "railing"
    assert "length" in by_class["IfcRailing"]

    assert by_class["IfcDoor"]["shape"] == "door"
    assert by_class["IfcDoorStandardCase"]["shape"] == "door"

    assert by_class["IfcWindow"]["shape"] == "window"
    assert by_class["IfcWindowStandardCase"]["shape"] == "window"

    assert by_class["IfcRoof"]["shape"] == "roof"

    assert by_class["IfcFurniture"]["shape"] == "furniture"
    assert by_class["IfcSystemFurnitureElement"]["shape"] == "furniture"
    assert by_class["IfcFurnishingElement"]["shape"] == "furniture"

    assert by_class["IfcPump"]["shape"] == "pump"
    assert by_class["IfcFlowMovingDevice"]["shape"] == "pump"

    assert by_class["IfcValve"]["shape"] == "valve"
    assert by_class["IfcFlowController"]["shape"] == "valve"

    assert by_class["IfcSanitaryTerminal"]["shape"] == "sanitary_terminal"
    assert by_class["IfcWasteTerminal"]["shape"] == "sanitary_terminal"

    assert by_class["IfcBoiler"]["shape"] == "equipment_vessel"
    assert by_class["IfcChiller"]["shape"] == "equipment_vessel"
    assert by_class["IfcTank"]["shape"] == "equipment_vessel"

    assert by_class["IfcAirTerminal"]["shape"] == "air_terminal"
    assert by_class["IfcDamper"]["shape"] == "air_terminal"

    assert by_class["IfcLightFixture"]["shape"] == "light_fixture"
    assert by_class["IfcLamp"]["shape"] == "light_fixture"

    assert by_class["IfcElectricDistributionBoard"]["shape"] == "electric_panel"
    assert by_class["IfcElectricAppliance"]["shape"] == "electric_panel"

    assert by_class["IfcOutlet"]["shape"] == "outlet_switch"
    assert by_class["IfcSwitchingDevice"]["shape"] == "outlet_switch"
    assert by_class["IfcSensor"]["shape"] == "outlet_switch"

    assert by_class["IfcBridge"]["shape"] == "bridge_structure"
    assert by_class["IfcBridgePart"]["shape"] == "bridge_structure"
    assert by_class["IfcBearing"]["shape"] == "bridge_structure"

    assert by_class["IfcRoad"]["shape"] == "road_infrastructure"

    assert by_class["IfcRailway"]["shape"] == "railway_infrastructure"
    assert by_class["IfcTrackElement"]["shape"] == "railway_infrastructure"

    assert by_class["IfcMooringDevice"]["shape"] == "marine_facility"
    assert by_class["IfcMarineFacility"]["shape"] == "marine_facility"
    assert by_class["IfcMarinePart"]["shape"] == "marine_facility"

    # Enclosure & Vertical Transport additions
    assert by_class["IfcTransportElement"]["shape"] == "transport_element"
    assert by_class["IfcCurtainWall"]["shape"] == "curtain_wall"
    assert by_class["IfcShadingDevice"]["shape"] == "shading_device"
    assert by_class["IfcWall"]["shape"] == "wall_system"
    assert by_class["IfcWallStandardCase"]["shape"] == "wall_system"
    assert by_class["IfcWallElementedCase"]["shape"] == "wall_system"
    assert by_class["IfcCovering"]["shape"] == "covering"
    assert by_class["IfcChimney"]["shape"] == "chimney"


def test_procedural_3d_geometry_handlers_in_html():
    """Test that generated HTML contains Three.js composite geometry handlers."""
    html_str = generate_class_directory_html()
    assert "stair_flight" in html_str
    assert "ramp" in html_str
    assert "railing" in html_str
    assert "door" in html_str
    assert "window" in html_str
    assert "roof" in html_str
    assert "furniture" in html_str
    assert "pump" in html_str
    assert "valve" in html_str
    assert "sanitary_terminal" in html_str
    assert "equipment_vessel" in html_str
    assert "air_terminal" in html_str
    assert "light_fixture" in html_str
    assert "electric_panel" in html_str
    assert "outlet_switch" in html_str
    assert "bridge_structure" in html_str
    assert "railway_infrastructure" in html_str
    assert "road_infrastructure" in html_str
    assert "marine_facility" in html_str
    assert "transport_element" in html_str
    assert "curtain_wall" in html_str
    assert "shading_device" in html_str
    assert "wall_system" in html_str
    assert "covering" in html_str
    assert "chimney" in html_str
