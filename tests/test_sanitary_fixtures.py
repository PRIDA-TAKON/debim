"""
Unit tests for MEP Plumbing & Sanitation Fixtures (IfcSanitaryTerminal & IfcWasteTerminal).
"""

from pathlib import Path
import pytest
from debim.compiler import compile_to_ifc
from debim.cost import PriceCatalog, estimate_cost
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcSanitaryTerminal,
    IfcWasteTerminal,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    TerminalPlacement,
)


@pytest.fixture
def sample_sanitary_manifest() -> ProjectManifest:
    return ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PRJ-SAN-01", name="Sanitary Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="L1", name="Level 1", elevation=0.0, height=3.5)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[],
        elements=[
            # Sanitary Terminals
            IfcSanitaryTerminal(
                tag="WC-01",
                terminal_type="WATERCLOSET",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1", offset_x=0.5, offset_y=0.5, offset_z=0.0),
                cold_water_inlet_diameter=0.015,
                waste_outlet_diameter=0.100,
            ),
            IfcSanitaryTerminal(
                tag="BASIN-01",
                terminal_type="WASHHANDBASIN",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1", offset_x=1.2, offset_y=0.5, offset_z=0.85),
                cold_water_inlet_diameter=0.015,
                hot_water_inlet_diameter=0.015,
                waste_outlet_diameter=0.032,
            ),
            IfcSanitaryTerminal(
                tag="URINAL-01",
                terminal_type="URINAL",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1", offset_x=2.0, offset_y=0.5, offset_z=0.60),
            ),
            IfcSanitaryTerminal(
                tag="SHOWER-01",
                terminal_type="SHOWER",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1", offset_x=2.8, offset_y=0.5, offset_z=2.00),
            ),
            IfcSanitaryTerminal(
                tag="BATH-01",
                terminal_type="BATH",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1", offset_x=3.5, offset_y=0.5, offset_z=0.0),
            ),
            IfcSanitaryTerminal(
                tag="SINK-01",
                terminal_type="SINK",
                placement=TerminalPlacement(grid=("1", "B"), storey="L1", offset_x=0.5, offset_y=-0.5, offset_z=0.85),
            ),

            # Waste Terminals
            IfcWasteTerminal(
                tag="FD-01",
                terminal_type="FLOORDRAIN",
                placement=TerminalPlacement(grid=("1", "A"), storey="L1", offset_x=1.0, offset_y=1.0, offset_z=0.0),
                waste_outlet_diameter=0.050,
            ),
            IfcWasteTerminal(
                tag="GT-01",
                terminal_type="GREASEINTERCEPTOR",
                placement=TerminalPlacement(grid=("1", "B"), storey="L1", offset_x=1.0, offset_y=-1.0, offset_z=-0.3),
                waste_outlet_diameter=0.075,
            ),
            IfcWasteTerminal(
                tag="RD-01",
                terminal_type="ROOFDRAIN",
                placement=TerminalPlacement(grid=("2", "B"), storey="L1", offset_x=-0.5, offset_y=-0.5, offset_z=3.5),
                waste_outlet_diameter=0.100,
            ),
        ],
    )


def test_sanitary_and_waste_schema_validation(sample_sanitary_manifest: ProjectManifest):
    elems = {e.tag: e for e in sample_sanitary_manifest.elements}
    assert len(elems) == 9

    wc = elems["WC-01"]
    assert isinstance(wc, IfcSanitaryTerminal)
    assert wc.predefined_type == "WATERCLOSET"
    assert wc.cold_water_inlet_diameter == 0.015
    assert wc.waste_outlet_diameter == 0.100

    basin = elems["BASIN-01"]
    assert isinstance(basin, IfcSanitaryTerminal)
    assert basin.predefined_type == "WASHHANDBASIN"

    fd = elems["FD-01"]
    assert isinstance(fd, IfcWasteTerminal)
    assert fd.predefined_type == "FLOORDRAIN"
    assert fd.waste_outlet_diameter == 0.050

    gt = elems["GT-01"]
    assert isinstance(gt, IfcWasteTerminal)
    assert gt.predefined_type == "GREASEINTERCEPTOR"


def test_sanitary_and_waste_spatial_resolution(sample_sanitary_manifest: ProjectManifest):
    resolved = resolve_manifest(sample_sanitary_manifest)
    assert len(resolved.sanitary_terminals) == 6
    assert len(resolved.waste_terminals) == 3

    resolved_wc = resolved.get_element_by_tag("WC-01")
    assert resolved_wc is not None
    assert resolved_wc.position == (0.5, 0.5, 0.0)
    assert resolved_wc.layer == "mep/plumbing/fixtures"

    resolved_fd = resolved.get_element_by_tag("FD-01")
    assert resolved_fd is not None
    assert resolved_fd.position == (1.0, 1.0, 0.0)
    assert resolved_fd.layer == "mep/plumbing/drainage"


def test_sanitary_and_waste_qto_counting(sample_sanitary_manifest: ProjectManifest):
    qto = calculate_qto(sample_sanitary_manifest)
    assert qto.total_sanitary_terminals_count == 6
    assert qto.total_waste_terminals_count == 3


def test_sanitary_and_waste_cost_estimation(sample_sanitary_manifest: ProjectManifest):
    qto = calculate_qto(sample_sanitary_manifest)
    catalog = PriceCatalog(
        currency="THB",
        items={
            "SAN-TOILET": {"name": "Water Closet Bowl", "unit": "set", "material_cost": 3500.0, "labor_cost": 500.0},
            "SAN-BASIN": {"name": "Wash Hand Basin", "unit": "set", "material_cost": 1800.0, "labor_cost": 350.0},
            "PLUMB-FLOORDRAIN": {"name": "Floor Drain 2inch", "unit": "set", "material_cost": 320.0, "labor_cost": 80.0},
            "PLUMB-GREASETRAP": {"name": "Grease Interceptor 40L", "unit": "set", "material_cost": 2500.0, "labor_cost": 400.0},
        },
    )

    cost_est = estimate_cost(qto, catalog, sample_sanitary_manifest)
    assert cost_est.grand_total > 0
    item_codes = [item.code for item in cost_est.line_items]
    assert "SAN-TOILET" in item_codes
    assert "SAN-BASIN" in item_codes
    assert "PLUMB-FLOORDRAIN" in item_codes
    assert "PLUMB-GREASETRAP" in item_codes


def test_sanitary_and_waste_ifc_compilation(sample_sanitary_manifest: ProjectManifest, tmp_path: Path):
    ifc_path = tmp_path / "sanitary_test.ifc"
    out_file = compile_to_ifc(sample_sanitary_manifest, ifc_path, force_fallback=True)
    assert out_file.exists()

    content = out_file.read_text(encoding="utf-8")
    assert "IFCSANITARYTERMINAL" in content
    assert "IFCWASTETERMINAL" in content
    assert ".WATERCLOSET." in content
    assert ".FLOORDRAIN." in content
