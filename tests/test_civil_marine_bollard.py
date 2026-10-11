"""
Unit test suite for IFC4.3 Civil Marine Infrastructure: IfcMooringDevice (BOLLARD, CLEAT).
"""

from pathlib import Path
import pytest
import ifcopenshell

from debim.compiler import StepSerializer, compile_to_ifc
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


def test_mooring_device_schema_validation():
    """Test Pydantic v2 schema validation for IfcMooringDevice."""
    bollard = IfcMooringDevice(
        tag="BOL-01",
        predefined_type="BOLLARD",
        capacity_tons=100.0,
        base_plate_width=0.80,
        anchor_bolts_count=6,
        height=0.90,
    )
    assert bollard.class_ == "IfcMooringDevice"
    assert bollard.predefined_type == "BOLLARD"
    assert bollard.capacity_tons == 100.0
    assert bollard.base_plate_width == 0.80
    assert bollard.anchor_bolts_count == 6
    assert bollard.height == 0.90

    cleat = IfcMooringDevice(
        tag="CLEAT-01",
        predefined_type="CLEAT",
        capacity_tons=25.0,
    )
    assert cleat.predefined_type == "CLEAT"
    assert cleat.capacity_tons == 25.0


def test_mooring_device_resolution_positioning_and_qto():
    """Test quayside copeline positioning and QTO calculation for mooring bollards and cleats."""
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-MARINE-MOORING", name="Quayside Mooring Facility"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="S1", name="Deck Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 100.0},
            axes_y={"A": 0.0, "B": 20.0},
        ),
        materials=[
            {"id": "MAT_CAST_STEEL", "name": "Cast Steel Grade GS-200", "category": "steel", "unit_cost_ref": "MAT-STEEL"},
            {"id": "MAT_MARINE_CONC", "name": "Marine Concrete C50", "category": "concrete", "unit_cost_ref": "MAT-CONC"},
        ],
        elements=[
            IfcMarinePart(
                tag="QUAY-01",
                predefined_type="QUAY",
                length=100.0,
                width=20.0,
                deck_thickness=0.80,
                material="MAT_MARINE_CONC",
                placement={"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "S1"},
            ),
            IfcMooringDevice(
                tag="BOL-01",
                predefined_type="BOLLARD",
                capacity_tons=100.0,
                base_plate_width=0.80,
                anchor_bolts_count=8,
                material="MAT_CAST_STEEL",
                placement={"from_grid": ["1", "A"], "to_grid": ["2", "A"], "offset_y": 0.50, "storey": "S1"},
            ),
            IfcMooringDevice(
                tag="BOL-02",
                predefined_type="BOLLARD",
                capacity_tons=100.0,
                base_plate_width=0.80,
                anchor_bolts_count=8,
                material="MAT_CAST_STEEL",
                placement={"grid": ["2", "A"], "offset_x": -5.0, "offset_y": 0.50, "storey": "S1"},
            ),
            IfcMooringDevice(
                tag="CLEAT-01",
                predefined_type="CLEAT",
                capacity_tons=30.0,
                material="MAT_CAST_STEEL",
                placement={"position": [10.0, 0.5, 0.0], "storey": "S1"},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.mooring_devices) == 3

    md_bol1 = resolved.mooring_devices[0]
    assert md_bol1.tag == "BOL-01"
    assert md_bol1.position == (50.0, 0.5, 0.0)
    assert md_bol1.capacity_tons == 100.0

    md_cleat = resolved.mooring_devices[2]
    assert md_cleat.tag == "CLEAT-01"
    assert md_cleat.position == (10.0, 0.5, 0.0)
    assert md_cleat.capacity_tons == 30.0

    qto = calculate_qto(resolved)
    assert qto.total_mooring_devices_count == 3
    assert qto.total_mooring_capacity_tons == 230.0

    eqto_bol = qto.get_element("BOL-01")
    assert eqto_bol is not None
    assert eqto_bol.marine is not None
    assert eqto_bol.marine.mooring_count == 1
    assert eqto_bol.marine.mooring_capacity_tons == 100.0


def test_mooring_device_compilation_and_3d_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape generation for IfcMooringDevice."""
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-BOL-COMP", name="Mooring Compilation Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="S1", name="Deck", elevation=0.0, height=3.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 50.0},
            axes_y={"A": 0.0, "B": 10.0},
        ),
        materials=[
            {"id": "MAT_STEEL", "name": "Cast Steel", "category": "steel", "unit_cost_ref": "MAT-STEEL"},
        ],
        elements=[
            IfcMooringDevice(
                tag="BOL-TEST-01",
                predefined_type="BOLLARD",
                capacity_tons=50.0,
                base_plate_width=0.60,
                material="MAT_STEEL",
                placement={"grid": ["1", "A"], "offset_x": 2.0, "storey": "S1"},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    step_str = StepSerializer(manifest).serialize(resolved)
    assert "IfcMooringDevice" in step_str or "IFCMOORINGDEVICE" in step_str
    assert "BOL-TEST-01" in step_str

    ifc_path = tmp_path / "mooring_model.ifc"
    out_file = compile_to_ifc(manifest, ifc_path)
    assert out_file.exists()

    model = ifcopenshell.open(str(out_file))
    try:
        moorings = model.by_type("IfcMooringDevice")
    except Exception:
        moorings = []
    if not moorings:
        moorings = [e for e in model.by_type("IfcBuildingElementProxy") if "MooringDevice" in (e.ObjectType or "")]
    assert len(moorings) == 1

    settings = ifcopenshell.geom.settings()
    shape_bol = ifcopenshell.geom.create_shape(settings, moorings[0])
    assert shape_bol is not None
    assert len(shape_bol.geometry.verts) > 0

    html = generate_viewer_html(manifest)
    assert "IfcMooringDevice" in html
    assert "BOL-TEST-01" in html
