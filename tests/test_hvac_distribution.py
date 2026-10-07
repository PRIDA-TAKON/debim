"""
Unit tests for MEP HVAC Distribution entities:
IfcAirTerminal, IfcDamper, IfcFlowController.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcAirTerminal,
    IfcDamper,
    IfcFlowController,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    TerminalPlacement,
)
from debim.viewer import generate_viewer_html


def test_hvac_terminal_creation_and_predefined_type():
    air_term = IfcAirTerminal(
        tag="AT-SUPPLY-01",
        terminal_type="DIFFUSER",
        air_flow_rate_m3h=340.0,
        neck_size=(0.25, 0.25),
        throw_distance_m=3.5,
        placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.7),
    )
    assert air_term.predefined_type == "DIFFUSER"
    assert pytest.approx(air_term.flow_rate_cfm, 0.1) == 200.11
    assert air_term.neck_width == 0.25
    assert air_term.neck_depth == 0.25

    damper = IfcDamper(
        tag="DAMP-FIRE-01",
        damper_type="FIRE_DAMPER",
        duct_width=0.40,
        duct_depth=0.30,
        actuator_type="FUSIBLE_LINK",
        placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.8),
    )
    assert damper.predefined_type == "FIREDAMPER"
    assert damper.actuator_type == "FUSIBLE_LINK"

    flow_ctrl = IfcFlowController(
        tag="VAV-UNIT-01",
        controller_type="AIR_CONTROLLER",
        air_flow_rate_m3h=850.0,
        duct_width=0.50,
        duct_depth=0.35,
        placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.8),
    )
    assert flow_ctrl.predefined_type == "AIR_CONTROLLER"


def test_hvac_spatial_resolution_and_layering():
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-HVAC", name="HVAC Test Building"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.5)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 5.0}, axes_y={"A": 0.0, "B": 5.0}),
        materials=[Material(id="MAT_MEP", name="MEP Steel", category="mep", unit_cost_ref="REF_MEP")],
        elements=[
            IfcAirTerminal(
                tag="AT-DIFFUSER-1",
                terminal_type="DIFFUSER",
                air_flow_rate_m3h=500.0,
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.6),
            ),
            IfcDamper(
                tag="FD-01",
                damper_type="FIRE_DAMPER",
                duct_width=0.45,
                duct_depth=0.35,
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.7),
            ),
            IfcFlowController(
                tag="VAV-01",
                controller_type="AIR_CONTROLLER",
                air_flow_rate_m3h=1000.0,
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.8),
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.air_terminals) == 1
    assert len(resolved.dampers) == 1
    assert len(resolved.flow_controllers) == 1

    r_air = resolved.air_terminals[0]
    assert r_air.layer == "mep/hvac/terminals"
    assert r_air.position == (0.0, 0.0, 2.6)

    r_damper = resolved.dampers[0]
    assert r_damper.layer == "mep/hvac/dampers"
    assert r_damper.predefined_type == "FIREDAMPER"

    r_fc = resolved.flow_controllers[0]
    assert r_fc.layer == "mep/hvac/equipment"
    assert r_fc.predefined_type == "AIR_CONTROLLER"


def test_hvac_qto_takeoff_and_cost():
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-HVAC", name="HVAC QTO Building"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.5)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[Material(id="MAT_MEP", name="MEP Material", category="mep", unit_cost_ref="REF_MEP")],
        elements=[
            IfcAirTerminal(
                tag="AT-DIFFUSER-1",
                terminal_type="DIFFUSER",
                air_flow_rate_m3h=600.0,
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.6),
            ),
            IfcDamper(
                tag="FD-01",
                damper_type="FIRE_DAMPER",
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.7),
            ),
            IfcFlowController(
                tag="VAV-01",
                controller_type="AIR_CONTROLLER",
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.8),
            ),
        ],
    )

    qto = calculate_qto(manifest)
    assert qto.total_air_terminals_count == 1
    assert qto.total_dampers_count == 1
    assert qto.total_flow_controllers_count == 1

    tmpl_path = generate_cost_template(manifest, output_path="dist/test_hvac_prices.yaml")
    assert tmpl_path.exists()

    catalog = load_price_catalog(tmpl_path)
    catalog.items["MEP-AIR-TERMINAL"].material_cost = 1200.0
    catalog.items["MEP-DAMPER"].material_cost = 2500.0
    catalog.items["MEP-FLOW-CONTROLLER"].material_cost = 8500.0

    estimate = estimate_cost(qto, catalog, manifest=manifest)
    assert estimate.grand_total == 1200.0 + 2500.0 + 8500.0


def test_hvac_ifc_compilation_and_viewer(tmp_path):
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-HVAC", name="HVAC Export Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.5)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[Material(id="MAT_MEP", name="MEP Material", category="mep", unit_cost_ref="REF_MEP")],
        elements=[
            IfcAirTerminal(
                tag="AT-DIFFUSER-1",
                terminal_type="DIFFUSER",
                air_flow_rate_m3h=600.0,
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.6),
            ),
            IfcDamper(
                tag="FD-01",
                damper_type="FIRE_DAMPER",
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.7),
            ),
            IfcFlowController(
                tag="VAV-01",
                controller_type="AIR_CONTROLLER",
                placement=TerminalPlacement(grid=["1", "A"], storey="FL1", offset_z=2.8),
            ),
        ],
    )

    # 1. IFC Compilation using IfcOpenShell
    ifc_file_ifcopenshell = tmp_path / "hvac_ifcopenshell.ifc"
    compile_to_ifc(manifest, output_path=ifc_file_ifcopenshell, force_fallback=False)
    assert ifc_file_ifcopenshell.exists()

    content_ios = ifc_file_ifcopenshell.read_text(encoding="utf-8")
    assert "IFCAIRTERMINAL" in content_ios
    assert "IFCDAMPER" in content_ios
    assert "IFCFLOWCONTROLLER" in content_ios

    # 2. IFC Compilation using fallback STEP serializer
    ifc_file_fallback = tmp_path / "hvac_fallback.ifc"
    compile_to_ifc(manifest, output_path=ifc_file_fallback, force_fallback=True)
    assert ifc_file_fallback.exists()

    content_fb = ifc_file_fallback.read_text(encoding="utf-8")
    assert "IFCAIRTERMINAL" in content_fb
    assert "IFCDAMPER" in content_fb
    assert "IFCFLOWCONTROLLER" in content_fb

    # 3. Viewer HTML Generation
    html = generate_viewer_html(manifest)
    assert "IfcAirTerminal" in html
    assert "IfcDamper" in html
    assert "IfcFlowController" in html
