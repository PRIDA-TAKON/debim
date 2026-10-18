"""
Unit tests for debim Class Directory & Encyclopedia Documentation Engine.
"""

import re
import time
from pathlib import Path
from cli_runner import CliRunner

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


def test_bilingual_data_payload_fields():
    """Test that synthesized catalog data items contain both Thai and English fields."""
    first_item = DEFAULT_CLASS_DIRECTORY_DATA[0]

    # Titles and Descriptions
    assert "name_th" in first_item and isinstance(first_item["name_th"], str) and len(first_item["name_th"]) > 0
    assert "name_en" in first_item and isinstance(first_item["name_en"], str) and len(first_item["name_en"]) > 0
    assert "description_th" in first_item and isinstance(first_item["description_th"], str) and len(first_item["description_th"]) > 0
    assert "description_en" in first_item and isinstance(first_item["description_en"], str) and len(first_item["description_en"]) > 0

    # BOQ Line Items Localization
    boq_items = first_item.get("qto_boq", [])
    assert len(boq_items) > 0
    assert "name_th" in boq_items[0] and len(boq_items[0]["name_th"]) > 0
    assert "name_en" in boq_items[0] and len(boq_items[0]["name_en"]) > 0

    # Specification Clauses
    assert "thai_specs" in first_item and "materials" in first_item["thai_specs"]
    assert "english_specs" in first_item and "materials" in first_item["english_specs"]
    assert "specs_th" in first_item and "specs_en" in first_item


def test_language_switcher_ui_elements_in_html():
    """Test that generated standalone HTML includes the bilingual language switcher buttons and JS handlers."""
    html_str = generate_class_directory_html()

    # Switcher container & buttons
    assert 'class="lang-switcher"' in html_str
    assert 'id="lang-btn-th"' in html_str
    assert 'id="lang-btn-en"' in html_str

    # JS Localization engine & state
    assert "setLanguage" in html_str
    assert "localStorage.getItem('debim_lang')" in html_str
    assert "localStorage.setItem('debim_lang'" in html_str
    assert "I18N" in html_str
    assert "name_en" in html_str
    assert "specs_en" in html_str


def test_docs_viewer_playwright_language_switch(tmp_path):
    """Test Playwright interaction switching language from TH to EN and asserting localized text updates."""
    import pytest
    playwright = pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    html_file = tmp_path / "directory.html"
    export_class_directory(html_file)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"file://{html_file.resolve()}")
            page.wait_for_function("typeof classesData !== 'undefined'")

            # Select class IfcColumn explicitly
            page.evaluate("""() => {
                const idx = classesData.findIndex(c => c.class_name === 'IfcColumn');
                selectClass(idx !== -1 ? idx : 0);
            }""")

            # Default language TH
            initial_lang = page.evaluate("currentLang")
            assert initial_lang == "th"

            # Click EN language switcher button
            page.click("#lang-btn-en")

            # Verify currentLang changed to 'en'
            active_lang = page.evaluate("currentLang")
            assert active_lang == "en"

            # Check localized title and description
            title_text = page.inner_text("#title-localized-name")
            desc_text = page.inner_text("#title-desc")
            assert "Structural Column" in title_text or "Column" in title_text
            assert "Structural" in desc_text or "member" in desc_text

            # Check localStorage persistence
            saved_pref = page.evaluate("localStorage.getItem('debim_lang')")
            assert saved_pref == "en"

            browser.close()
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            pytest.skip(f"Browser binary missing: {e}")
        raise e


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

    assert by_class["IfcStair"]["shape"] == "stair_concrete"
    assert by_class["IfcStair"]["steps"] == 10
    assert by_class["IfcStair"]["is_reinforced_concrete"] is True
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

    # HVAC, Mechanical Plant & Fire Suppression additions
    assert by_class["IfcDuctSegment"]["shape"] == "duct_assembly"
    assert by_class["IfcDuctFitting"]["shape"] == "duct_assembly"
    assert by_class["IfcDuctSilencer"]["shape"] == "duct_assembly"

    assert by_class["IfcFan"]["shape"] == "fan_assembly"
    assert by_class["IfcAirToAirHeatRecovery"]["shape"] == "fan_assembly"

    assert by_class["IfcCoolingTower"]["shape"] == "cooling_tower"
    assert by_class["IfcEvaporativeCooler"]["shape"] == "cooling_tower"
    assert by_class["IfcHeatExchanger"]["shape"] == "cooling_tower"

    assert by_class["IfcCoil"]["shape"] == "coil_heat_exchanger"
    assert by_class["IfcEvaporator"]["shape"] == "coil_heat_exchanger"
    assert by_class["IfcCondenser"]["shape"] == "coil_heat_exchanger"

    assert by_class["IfcFilter"]["shape"] == "air_filter"

    assert by_class["IfcSpaceHeater"]["shape"] == "radiator_heater"

    assert by_class["IfcBurner"]["shape"] == "combustion_burner"
    assert by_class["IfcEngine"]["shape"] == "combustion_burner"

    assert by_class["IfcFireSuppressionTerminal"]["shape"] == "fire_suppression"
    assert by_class["IfcStackTerminal"]["shape"] == "fire_suppression"

    assert by_class["IfcTransformer"]["shape"] == "power_plant"
    assert by_class["IfcElectricGenerator"]["shape"] == "power_plant"
    assert by_class["IfcElectricMotor"]["shape"] == "power_plant"

    # Civil Earthworks, Foundations & Structural Fasteners additions
    assert by_class["IfcEarthworksCut"]["shape"] == "earthworks_embankment"
    assert by_class["IfcEarthworksFill"]["shape"] == "earthworks_embankment"
    assert by_class["IfcEarthworksElement"]["shape"] == "earthworks_embankment"
    assert by_class["IfcGeotechnicalStratum"]["shape"] == "earthworks_embankment"
    assert by_class["IfcSoil"]["shape"] == "earthworks_embankment"

    assert by_class["IfcRetainingWall"]["shape"] == "retaining_structure"
    assert by_class["IfcGeographicElement"]["shape"] == "retaining_structure"

    assert by_class["IfcFooting"]["shape"] == "deep_foundation"
    assert by_class["IfcPile"]["shape"] == "deep_foundation"

    assert by_class["IfcTendonAnchor"]["shape"] == "tendon_anchor"
    assert by_class["IfcTendon"]["shape"] == "tendon_anchor"

    assert by_class["IfcFastener"]["shape"] == "structural_fastener"
    assert by_class["IfcMechanicalFastener"]["shape"] == "structural_fastener"
    assert by_class["IfcDiscreteAccessory"]["shape"] == "structural_fastener"

    assert by_class["IfcVibrationIsolator"]["shape"] == "vibration_isolator"
    assert by_class["IfcMember"]["shape"] == "structural_member"
    assert by_class["IfcMemberStandardCase"]["shape"] == "structural_member"

    assert by_class["IfcReinforcingBar"]["shape"] == "reinforcing_bar"
    assert by_class["IfcReinforcingMesh"]["shape"] == "reinforcing_mesh"

    # Electrical & Low-Voltage additions
    assert by_class["IfcSolarDevice"]["shape"] == "solar_panel"
    assert by_class["IfcJunctionBox"]["shape"] == "junction_box"
    assert by_class["IfcProtectiveDevice"]["shape"] == "circuit_breaker"
    if "IfcProtectiveDeviceTrippingUnit" in by_class:
        assert by_class["IfcProtectiveDeviceTrippingUnit"]["shape"] == "circuit_breaker"
    assert by_class["IfcAlarm"]["shape"] == "alarm_device"
    assert by_class["IfcElectricFlowStorageDevice"]["shape"] == "battery_storage"

    # Flow meters, instruments, interceptors, actuators & humidifiers
    assert by_class["IfcFlowMeter"]["shape"] == "flow_meter"
    assert by_class["IfcFlowInstrument"]["shape"] == "flow_instrument"
    assert by_class["IfcActuator"]["shape"] == "valve_actuator"
    assert by_class["IfcInterceptor"]["shape"] == "grease_oil_interceptor"
    assert by_class["IfcHumidifier"]["shape"] == "humidifier_unit"

    # Distribution chambers, tube bundles, treatment & packaged units
    assert by_class["IfcDistributionChamberElement"]["shape"] == "distribution_chamber"
    assert by_class["IfcTubeBundle"]["shape"] == "tube_bundle"
    assert by_class["IfcFlowTreatmentDevice"]["shape"] == "water_treatment_device"
    assert by_class["IfcUnitaryEquipment"]["shape"] == "rooftop_packaged_unit"
    assert by_class["IfcMedicalDevice"]["shape"] == "medical_bed_console"

    # Audio-Visual, Communications & Controller additions
    assert by_class["IfcAudioVisualAppliance"]["shape"] == "audiovisual_display"
    assert by_class["IfcCommunicationsAppliance"]["shape"] == "network_router_rack"
    assert by_class["IfcController"]["shape"] == "thermostat_controller"
    if "IfcUnitaryControlElement" in by_class:
        assert by_class["IfcUnitaryControlElement"]["shape"] == "thermostat_controller"
    if "IfcDistributionControlElement" in by_class:
        assert by_class["IfcDistributionControlElement"]["shape"] == "thermostat_controller"
    assert by_class["IfcElectricTimeControl"]["shape"] == "timer_relay"

    # Abstract, fitting, terminal, connection, proxy & assembly additions
    assert by_class["IfcFlowFitting"]["shape"] == "pipe_fitting_tee"
    assert by_class["IfcFlowSegment"]["shape"] == "insulated_flow_segment"
    assert by_class["IfcFlowTerminal"]["shape"] == "floor_drain_terminal"
    assert by_class["IfcMotorConnection"]["shape"] == "flexible_shaft_coupling"
    assert by_class["IfcElementAssembly"]["shape"] == "truss_assembly"
    assert by_class["IfcCivilElement"]["shape"] == "civil_culvert"
    assert by_class["IfcBuildingElementProxy"]["shape"] == "parametric_component_proxy"
    assert by_class["IfcBuildingElementPart"]["shape"] == "parametric_component_proxy"
    assert by_class["IfcDistributionElement"]["shape"] == "parametric_component_proxy"
    assert by_class["IfcDistributionFlowElement"]["shape"] == "parametric_component_proxy"
    assert by_class["IfcVirtualElement"]["shape"] == "virtual_boundary_zone"


def test_procedural_3d_geometry_handlers_in_html():
    """Test that generated HTML contains Three.js composite geometry handlers."""
    html_str = generate_class_directory_html()
    assert "stair_flight" in html_str
    assert "stair_concrete" in html_str
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
    assert "duct_assembly" in html_str
    assert "fan_assembly" in html_str
    assert "cooling_tower" in html_str
    assert "coil_heat_exchanger" in html_str
    assert "air_filter" in html_str
    assert "radiator_heater" in html_str
    assert "combustion_burner" in html_str
    assert "fire_suppression" in html_str
    assert "power_plant" in html_str
    assert "earthworks_embankment" in html_str
    assert "retaining_structure" in html_str
    assert "deep_foundation" in html_str
    assert "tendon_anchor" in html_str
    assert "structural_fastener" in html_str
    assert "vibration_isolator" in html_str
    assert "structural_member" in html_str
    assert "reinforcing_bar" in html_str
    assert "reinforcing_mesh" in html_str
    assert "solar_panel" in html_str
    assert "junction_box" in html_str
    assert "circuit_breaker" in html_str
    assert "alarm_device" in html_str
    assert "battery_storage" in html_str
    assert "flow_meter" in html_str
    assert "flow_instrument" in html_str
    assert "valve_actuator" in html_str
    assert "grease_oil_interceptor" in html_str
    assert "humidifier_unit" in html_str
    assert "distribution_chamber" in html_str
    assert "tube_bundle" in html_str
    assert "water_treatment_device" in html_str
    assert "rooftop_packaged_unit" in html_str
    assert "medical_bed_console" in html_str
    assert "audiovisual_display" in html_str
    assert "network_router_rack" in html_str
    assert "thermostat_controller" in html_str
    assert "timer_relay" in html_str
    assert "pipe_fitting_tee" in html_str
    assert "insulated_flow_segment" in html_str
    assert "floor_drain_terminal" in html_str
    assert "flexible_shaft_coupling" in html_str
    assert "truss_assembly" in html_str
    assert "civil_culvert" in html_str
    assert "parametric_component_proxy" in html_str
    assert "virtual_boundary_zone" in html_str


def test_spatial_transform_controls_in_html():
    """Test that generated HTML contains interactive spatial positioning, rotation, and sizing test controls."""
    html_str = generate_class_directory_html()

    # Toolbar button & panel
    assert 'id="transform-btn"' in html_str
    assert "Transform &amp; Sizing" in html_str or "Transform & Sizing" in html_str
    assert 'id="transform-panel"' in html_str
    assert "Spatial &amp; Parametric Test" in html_str or "Spatial & Parametric Test" in html_str

    # Positioning controls
    assert 'id="pos-x-range"' in html_str
    assert 'id="pos-x-num"' in html_str
    assert 'id="pos-y-range"' in html_str
    assert 'id="pos-y-num"' in html_str
    assert 'id="pos-z-range"' in html_str
    assert 'id="pos-z-num"' in html_str

    # Rotation controls
    assert 'id="rot-x-range"' in html_str
    assert 'id="rot-x-num"' in html_str
    assert 'id="rot-y-range"' in html_str
    assert 'id="rot-y-num"' in html_str
    assert 'id="rot-z-range"' in html_str
    assert 'id="rot-z-num"' in html_str

    # Parametric sizing scale controls
    assert 'id="scale-w-range"' in html_str
    assert 'id="scale-w-num"' in html_str
    assert 'id="scale-d-range"' in html_str
    assert 'id="scale-d-num"' in html_str
    assert 'id="scale-h-range"' in html_str
    assert 'id="scale-h-num"' in html_str

    # Reset button
    assert 'id="reset-transform-btn"' in html_str

    # JS Handler functions
    assert "toggleTransformPanel" in html_str
    assert "syncAndApplyTransform" in html_str
    assert "resetTransform" in html_str
    assert "applyTransform" in html_str


def test_spatial_transform_benchmark_execution(tmp_path):
    """Test running spatial transform benchmark script with Playwright against a single class."""
    import sys
    import pytest
    pytest.importorskip("playwright")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.benchmark_spatial_transforms import run_spatial_transform_benchmark

    out_dir = tmp_path / "spatial_benchmark_test"
    try:
        res = run_spatial_transform_benchmark(
            output_dir=out_dir,
            headless=True,
            save_snapshots=True,
            classes_to_test=["IfcColumn"],
        )
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            pytest.skip(f"Browser binary missing: {e}")
        raise e

    assert res["total_tested"] == 1
    assert res["total_passed"] == 1
    assert res["ground_passes"] == 1
    assert res["elev_passes"] == 1
    assert res["yaw_passes"] == 1
    assert res["scale_passes"] == 1
    assert Path(res["report_path"]).exists()


def test_docs_viewer_transform_ground_and_scale(tmp_path):
    """Test Playwright assertions for ground resting, elevation offset, yaw rotation, and scaling on representative classes."""
    import pytest
    playwright = pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    html_file = tmp_path / "directory.html"
    export_class_directory(html_file)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"file://{html_file.resolve()}")
            page.wait_for_function("typeof classesData !== 'undefined'")

            # Select IfcColumn (index 0)
            page.evaluate("selectClass(0)")

            # 1. Ground Rest Verification (PosY = 0)
            ground_res = page.evaluate("""() => {
                const bbox = new THREE.Box3().setFromObject(currentMesh);
                return { minY: bbox.min.y, posY: currentMesh.position.y };
            }""")
            assert abs(ground_res["minY"]) < 0.05

            # 2. Elevation Shift (+3.0m)
            page.evaluate("""() => {
                document.getElementById('pos-y-num').value = '3.0';
                applyTransform();
            }""")
            elev_res = page.evaluate("""() => {
                const bbox = new THREE.Box3().setFromObject(currentMesh);
                return { minY: bbox.min.y };
            }""")
            assert abs(elev_res["minY"] - 3.0) < 0.05

            # 3. Yaw Rotation (180 deg)
            page.evaluate("""() => {
                document.getElementById('pos-y-num').value = '0.0';
                document.getElementById('rot-y-num').value = '180';
                applyTransform();
            }""")
            rot_res = page.evaluate("""() => {
                return { rotY: currentMesh.rotation.y, minY: new THREE.Box3().setFromObject(currentMesh).min.y };
            }""")
            assert abs(rot_res["minY"]) < 0.05
            assert abs(rot_res["rotY"] - 3.14159) < 0.02

            # 4. Parametric Scaling (Scale H = 1.5x)
            page.evaluate("""() => {
                resetTransform();
                document.getElementById('scale-h-num').value = '1.5';
                applyTransform();
            }""")
            scale_res = page.evaluate("""() => {
                const bbox = new THREE.Box3().setFromObject(currentMesh);
                return { minY: bbox.min.y, height: bbox.max.y - bbox.min.y, hasEdges: !!edgesGroup };
            }""")
            assert abs(scale_res["minY"]) < 0.05
            assert scale_res["hasEdges"] is True

            browser.close()
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            pytest.skip(f"Browser binary missing: {e}")
        raise e
