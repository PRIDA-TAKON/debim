"""
Unit test suite for IFC4.3 Civil Marine Infrastructure: IfcMooringDevice quayside bollards and cleats.
Verifies schema validation, quay deck coping line mounting orientation, QTO calculation,
IFC4.3 compilation, and 3D web viewer generation.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcMarinePart,
    IfcMooringDevice,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_marine_bollard_schema_validation():
    """Test Pydantic schema validation and automatic defaults for BOLLARD and CLEAT."""
    bollard = IfcMooringDevice(
        tag="BOL-01",
        name="Quayside Mooring Bollard 50T",
        predefined_type="BOLLARD",
        quay_wall="QUAY-01",
        placement={"face": "FRONT", "offset_x": 10.0, "offset_y": 0.0},
    )
    assert bollard.class_ == "IfcMooringDevice"
    assert bollard.tag == "BOL-01"
    assert bollard.predefined_type == "BOLLARD"
    assert bollard.bollard_type == "TEE"
    assert bollard.capacity_tons == 50.0
    assert bollard.base_plate_width == 0.60
    assert bollard.base_plate_length == 0.60
    assert bollard.anchor_bolts_count == 4
    assert bollard.quay_wall == "QUAY-01"
    assert bollard.placement.quay_wall == "QUAY-01"

    # Test cleat defaults
    cleat = IfcMooringDevice(
        tag="CLT-01",
        name="Small Craft Mooring Cleat",
        predefined_type="CLEAT",
        quay_wall="QUAY-01",
        placement={"face": "FRONT", "offset_x": 2.0},
    )
    assert cleat.predefined_type == "CLEAT"
    assert cleat.bollard_type == "CLEAT"
    assert cleat.capacity_tons == 10.0
    assert cleat.base_plate_width == 0.30
    assert cleat.base_plate_length == 0.50
    assert cleat.anchor_bolts_count == 2

    # Test custom values
    custom_bollard = IfcMooringDevice(
        tag="BOL-HEAVY",
        predefined_type="BOLLARD",
        bollard_type="STAGHORN",
        capacity_tons=150.0,
        base_plate_width=0.90,
        base_plate_length=1.10,
        anchor_bolts_count=8,
    )
    assert custom_bollard.bollard_type == "STAGHORN"
    assert custom_bollard.capacity_tons == 150.0
    assert custom_bollard.base_plate_width == 0.90
    assert custom_bollard.base_plate_length == 1.10
    assert custom_bollard.anchor_bolts_count == 8


def test_marine_bollard_quay_coping_resolution():
    """Test bollard and cleat spatial positioning along quay coping deck edge."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-BOLLARD-01", name="Quay Bollard Placement Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 40.0}),
        materials=[],
        elements=[
            IfcMarinePart(
                tag="QUAY-01",
                predefined_type="QUAY",
                length=60.0,
                width=20.0,
                deck_thickness=0.80,
                deck_elevation=3.0,
                depth=12.0,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
            # Bollard on south coping line (FRONT face)
            IfcMooringDevice(
                tag="BOL-SOUTH",
                predefined_type="BOLLARD",
                capacity_tons=50.0,
                quay_wall="QUAY-01",
                placement={"face": "FRONT", "offset_x": 15.0, "offset_z": 0.0},
            ),
            # Cleat on north coping line (BACK face)
            IfcMooringDevice(
                tag="CLT-NORTH",
                predefined_type="CLEAT",
                capacity_tons=15.0,
                quay_wall="QUAY-01",
                placement={"face": "BACK", "offset_x": -10.0, "offset_z": 0.1},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.mooring_devices) == 2

    # Verify BOL-SOUTH placement on deck top
    bol_res = next(md for md in resolved.mooring_devices if md.tag == "BOL-SOUTH")
    assert bol_res.predefined_type == "BOLLARD"
    assert bol_res.capacity_tons == 50.0
    assert bol_res.anchor_bolts_count == 4
    # Quay position is (0.0, 0.0, 0.0). Deck elevation is 3.0.
    # z_mount = 3.0 + 0.0 = 3.0
    assert bol_res.position[2] == pytest.approx(3.0, abs=1e-3)
    # y on front face is -W/2 + base_w/2 = -10.0 + 0.30 = -9.70
    assert bol_res.position[1] == pytest.approx(-9.70, abs=1e-3)
    assert bol_res.position[0] == pytest.approx(15.0, abs=1e-3)
    assert "bollards" in bol_res.layer

    # Verify CLT-NORTH placement on deck top
    clt_res = next(md for md in resolved.mooring_devices if md.tag == "CLT-NORTH")
    assert clt_res.predefined_type == "CLEAT"
    assert clt_res.capacity_tons == 15.0
    assert clt_res.position[2] == pytest.approx(3.1, abs=1e-3)
    # y on back face is W/2 - base_w/2 = 10.0 - 0.15 = 9.85
    assert clt_res.position[1] == pytest.approx(9.85, abs=1e-3)
    assert clt_res.position[0] == pytest.approx(-10.0, abs=1e-3)


def test_marine_bollard_qto_metrics():
    """Test QTO aggregation of mooring bollard and cleat counts and SWL tonnage."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-BOLLARD-QTO", name="Bollard QTO Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[
            IfcMooringDevice(
                tag="BOL-1",
                predefined_type="BOLLARD",
                capacity_tons=50.0,
                placement={"storey": "GROUND", "offset_x": 0.0},
            ),
            IfcMooringDevice(
                tag="BOL-2",
                predefined_type="BOLLARD",
                capacity_tons=75.0,
                placement={"storey": "GROUND", "offset_x": 20.0},
            ),
            IfcMooringDevice(
                tag="CLT-1",
                predefined_type="CLEAT",
                capacity_tons=10.0,
                placement={"storey": "GROUND", "offset_x": 40.0},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    qto = calculate_qto(resolved)

    assert qto.total_mooring_devices_count == 3
    assert qto.total_mooring_bollards_count == 2
    assert qto.total_mooring_cleats_count == 1
    assert qto.total_mooring_capacity_tons == pytest.approx(135.0, abs=1e-3)

    eqto_bol1 = qto.get_element("BOL-1")
    assert eqto_bol1 is not None
    assert eqto_bol1.mooring_device is not None
    assert eqto_bol1.mooring_device.capacity_tons == 50.0
    assert eqto_bol1.mooring_device.anchor_bolts_count == 4
    assert eqto_bol1.mooring_device.bollard_type == "TEE"


def test_marine_bollard_compiler_and_viewer(tmp_path: Path):
    """Test IFC export and 3D web viewer generation for mooring bollards and cleats."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-BOLLARD-IFC", name="Bollard IFC Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[
            IfcMooringDevice(
                tag="BOL-01",
                predefined_type="BOLLARD",
                capacity_tons=50.0,
                placement={"storey": "GROUND"},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)

    # 1. Test fallback pure Python compiler
    step_file = tmp_path / "bollard_fallback.ifc"
    compile_to_ifc(resolved, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    content = step_file.read_text(encoding="utf-8")
    assert "IfcMooringDevice.BOLLARD" in content
    assert "IFCEXTRUDEDAREASOLID" in content

    # 2. Test 3D Web Viewer generation
    html = generate_viewer_html(resolved)
    assert "IfcMooringDevice" in html
    assert "BOLLARD" in html
    assert "capacity_tons" in html
    assert "BOL-01" in html
