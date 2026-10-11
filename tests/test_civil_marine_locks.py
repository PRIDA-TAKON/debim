"""
Unit test suite for IFC4.3 Civil Marine Structures: IfcMarinePart (LOCK, CANAL, DRYDOCK, SLIPWAY).
Verifies schema validation, 3D spatial resolution, chamber water capacity and concrete volume QTOs,
IFC4.3 STEP/IfcOpenShell compilation, and viewer HTML generation.
"""

from pathlib import Path
import pytest
import ifcopenshell

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcMarinePart,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_marine_part_schema_validation():
    """Test Pydantic v2 schema validation for IfcMarinePart."""
    mp = IfcMarinePart(
        tag="LOCK-01",
        name="Navigation Lock Chamber",
        predefined_type="LOCK",
        chamber_length=120.0,
        chamber_width=18.0,
        wall_thickness=1.8,
        wall_height=9.0,
        sill_elevation=0.0,
        floor_thickness=1.2,
    )
    assert mp.class_ == "IfcMarinePart"
    assert mp.tag == "LOCK-01"
    assert mp.predefined_type == "LOCK"
    assert mp.length == 120.0
    assert mp.width == 18.0
    assert mp.height == 9.0

    # Verify predefined types
    for ptype in ["LOCK", "CANAL", "DRYDOCK", "SLIPWAY", "USERDEFINED", "NOTDEFINED"]:
        part = IfcMarinePart(tag=f"MP-{ptype}", predefined_type=ptype)
        assert part.predefined_type == ptype


def test_marine_part_resolution_and_qto():
    """Test 3D spatial resolution and QTO calculations for U-shaped chambers."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-01", name="Marine Lock & Canal"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 20.0}),
        materials=[],
        elements=[
            IfcMarinePart(
                tag="LOCK-01",
                predefined_type="LOCK",
                chamber_length=100.0,
                chamber_width=20.0,
                wall_thickness=2.0,
                wall_height=10.0,
                floor_thickness=1.5,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.marine_parts) == 1

    rmp = resolved.marine_parts[0]
    assert rmp.tag == "LOCK-01"
    assert rmp.chamber_water_volume == 100.0 * 20.0 * 10.0  # 20,000.0 m3
    assert rmp.wall_concrete_volume == 2.0 * 100.0 * 2.0 * 10.0  # 4,000.0 m3
    assert rmp.floor_concrete_volume == 100.0 * (20.0 + 4.0) * 1.5  # 3,600.0 m3
    assert rmp.total_concrete_volume == 7600.0  # 7,600.0 m3

    # QTO
    qto = calculate_qto(resolved)
    assert qto.total_marine_water_volume == 20000.0
    assert qto.total_marine_concrete_volume == 7600.0

    eqto = qto.get_element("LOCK-01")
    assert eqto is not None
    assert eqto.marine is not None
    assert eqto.marine.chamber_water_volume == 20000.0
    assert eqto.marine.total_concrete_volume == 7600.0


def test_marine_part_compilation(tmp_path: Path):
    """Test IFC4.3 compilation and STEP serialization for IfcMarinePart."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-02", name="Shipyard Dry Dock"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[
            IfcMarinePart(
                tag="DRYDOCK-01",
                predefined_type="DRYDOCK",
                chamber_length=150.0,
                chamber_width=25.0,
                wall_thickness=2.5,
                wall_height=12.0,
                floor_thickness=2.0,
            ),
        ],
    )

    # 1. Fallback / Raw STEP compilation
    step_file = tmp_path / "marine_model.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    content = step_file.read_text(encoding="utf-8")
    assert "IFCMARINEPART" in content
    assert "DRYDOCK-01" in content

    # 2. HTML Viewer generation
    html = generate_viewer_html(manifest)
    assert "IfcMarinePart" in html
    assert "DRYDOCK-01" in html
