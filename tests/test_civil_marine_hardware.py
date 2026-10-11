"""
Unit test suite for IFC4.3 Marine Hardware Elements: IfcMooringDevice and IfcNavigationElement.
Verifies schema validation, quay edge spatial resolution, QTO piece counts and capacity attributes,
and IFC compilation (STEP & IfcOpenShell).
"""

from pathlib import Path
import pytest
import ifcopenshell

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcMooringDevice,
    IfcNavigationElement,
    IfcRetainingWall,
    MarinePlacement,
    Material,
    ProjectInfo,
    ProjectManifest,
    RetainingWallPlacement,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_marine_hardware_schema_validation():
    """Test Pydantic v2 schema validation for IfcMooringDevice and IfcNavigationElement."""
    # 1. IfcMooringDevice predefined types and parameters
    for ptype in ["BOLLARD", "CLEAT", "FENDER", "HOOK", "USERDEFINED"]:
        md = IfcMooringDevice(
            tag=f"MD-{ptype}",
            predefined_type=ptype,
            capacity_tons=50.0 if ptype == "BOLLARD" else None,
            fender_diameter=1.2 if ptype == "FENDER" else None,
            fender_projection=0.8 if ptype == "FENDER" else None,
        )
        assert md.class_ == "IfcMooringDevice"
        assert md.predefined_type == ptype
        if ptype == "BOLLARD":
            assert md.capacity_tons == 50.0
        if ptype == "FENDER":
            assert md.fender_diameter == 1.2
            assert md.fender_projection == 0.8

    # 2. IfcNavigationElement predefined types
    for ntype in ["BEACON", "BUOY", "LIGHT", "MARKER", "USERDEFINED"]:
        nav = IfcNavigationElement(
            tag=f"NAV-{ntype}",
            predefined_type=ntype,
            width=0.8,
            height=2.0,
        )
        assert nav.class_ == "IfcNavigationElement"
        assert nav.predefined_type == ntype
        assert nav.width == 0.8
        assert nav.height == 2.0


def test_marine_hardware_resolution_and_qto():
    """Test 3D spatial resolution along quay wall edge and QTO calculation."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-01", name="Marine Terminal Port"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="PORT", name="Port Base", elevation=0.0, height=4.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 20.0}),
        materials=[
            Material(id="MAT_CONC", name="Marine Concrete", category="concrete", unit_cost_ref="CIVIL-CONC"),
            Material(id="MAT_STEEL", name="Cast Steel", category="steel", unit_cost_ref="CIVIL-STEEL"),
        ],
        elements=[
            IfcRetainingWall(
                tag="QUAY-WALL-01",
                material="MAT_CONC",
                predefined_type="DIAPHRAGM_WALL",
                placement=RetainingWallPlacement(
                    storey="PORT",
                    from_grid=["1", "A"],
                    to_grid=["2", "A"],
                ),
            ),
            IfcMooringDevice(
                tag="BOLLARD-01",
                material="MAT_STEEL",
                predefined_type="BOLLARD",
                capacity_tons=100.0,
                placement=MarinePlacement(
                    quay_edge="QUAY-WALL-01",
                    position_offset=30.0,
                ),
            ),
            IfcMooringDevice(
                tag="FENDER-01",
                material="MAT_STEEL",
                predefined_type="FENDER",
                fender_diameter=1.5,
                fender_projection=0.9,
                placement=MarinePlacement(
                    quay_edge="QUAY-WALL-01",
                    position_offset=40.0,
                ),
            ),
            IfcNavigationElement(
                tag="BEACON-01",
                material="MAT_STEEL",
                predefined_type="BEACON",
                placement=MarinePlacement(
                    position=(10.0, -20.0, 2.0),
                ),
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.mooring_devices) == 2
    assert len(resolved.navigation_elements) == 1

    bollard = resolved.mooring_devices[0]
    assert bollard.tag == "BOLLARD-01"
    assert bollard.position == (30.0, 0.0, 0.0)
    assert bollard.capacity_tons == 100.0

    fender = resolved.mooring_devices[1]
    assert fender.tag == "FENDER-01"
    assert fender.position == (40.0, 0.0, 0.0)
    assert fender.fender_diameter == 1.5

    beacon = resolved.navigation_elements[0]
    assert beacon.tag == "BEACON-01"
    assert beacon.position == (10.0, -20.0, 2.0)

    # QTO
    qto = calculate_qto(resolved)
    eqto_bollard = qto.get_element("BOLLARD-01")
    assert eqto_bollard is not None
    assert eqto_bollard.mep is not None
    assert eqto_bollard.mep.count == 1
    assert eqto_bollard.mep.capacity_tons == 100.0

    eqto_fender = qto.get_element("FENDER-01")
    assert eqto_fender is not None
    assert eqto_fender.mep.fender_diameter == 1.5


def test_marine_hardware_compilation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape creation for marine elements."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-02", name="Marine Compile Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="PORT", name="Port Base", elevation=0.0, height=4.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 50.0}, axes_y={"A": 0.0, "B": 10.0}),
        materials=[],
        elements=[
            IfcMooringDevice(
                tag="MD-BOLLARD-01",
                predefined_type="BOLLARD",
                capacity_tons=80.0,
                placement=MarinePlacement(position=(5.0, 0.0, 0.0)),
            ),
            IfcNavigationElement(
                tag="NAV-LIGHT-01",
                predefined_type="LIGHT",
                placement=MarinePlacement(position=(15.0, -5.0, 3.0)),
            ),
        ],
    )

    # 1. Compile to IFC4.3
    ifc_file = tmp_path / "marine_hardware.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))
    moorings = model.by_type("IfcMooringDevice")
    navigations = model.by_type("IfcNavigationElement")

    assert len(moorings) == 1
    assert len(navigations) == 1
    assert moorings[0].Name == "MD-BOLLARD-01"
    assert navigations[0].Name == "NAV-LIGHT-01"

    # 2. STEP physical file fallback export
    step_file = tmp_path / "marine_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCMOORINGDEVICE" in step_content
    assert "IFCNAVIGATIONELEMENT" in step_content

    # 3. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcMooringDevice" in html
    assert "IfcNavigationElement" in html
    assert "MD-BOLLARD-01" in html
