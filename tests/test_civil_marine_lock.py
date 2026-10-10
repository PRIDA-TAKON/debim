"""
Unit test suite for IFC4.3 Civil Marine Infrastructure: Navigation Locks & Canal Chambers (IfcMarinePart LOCK and CANAL).
Verifies schema validation, 2D U-channel profile generation, 3D spatial resolution,
concrete & water volume QTO calculations, IFC4.3 compilation, and 3D shape generation with ifcopenshell.geom.create_shape.
"""

from pathlib import Path
import pytest
import ifcopenshell
import ifcopenshell.geom

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


def test_marine_lock_schema_validation():
    """Test Pydantic v2 schema validation for navigation locks and canal lock chambers."""
    lock = IfcMarinePart(
        tag="LOCK-01",
        name="Panama Canal Expansion Lock Chamber",
        predefined_type="LOCK",
        chamber_length=120.0,
        chamber_width=18.0,
        wall_height=14.0,
        wall_thickness=3.0,
        invert_thickness=2.5,
        placement={"offset_x": 0.0, "offset_y": 0.0, "offset_z": 0.0},
    )
    assert lock.class_ == "IfcMarinePart"
    assert lock.tag == "LOCK-01"
    assert lock.predefined_type == "LOCK"
    assert lock.chamber_length == 120.0
    assert lock.chamber_width == 18.0
    assert lock.wall_height == 14.0
    assert lock.wall_thickness == 3.0
    assert lock.invert_thickness == 2.5

    canal = IfcMarinePart(
        tag="CANAL-01",
        predefined_type="CANAL",
        length=200.0,
        width=20.0,
        wall_height=10.0,
        wall_thickness=2.0,
        invert_thickness=1.5,
    )
    assert canal.predefined_type == "CANAL"
    assert canal.chamber_length == 200.0
    assert canal.chamber_width == 20.0


def test_marine_lock_resolution_and_qto():
    """Test U-channel profile resolution, concrete volume, water retention volume, and QTO for locks."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-LOCK-01", name="Lock System Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 30.0}),
        materials=[
            {"id": "MAT_LOCK_CONC", "name": "Heavy Hydraulic Concrete C40/50", "category": "concrete", "unit_cost_ref": "MAT-CONC"},
        ],
        elements=[
            IfcMarinePart(
                tag="LOCK-MAIN",
                material="MAT_LOCK_CONC",
                predefined_type="LOCK",
                chamber_length=100.0,
                chamber_width=16.0,
                wall_height=12.0,
                wall_thickness=2.5,
                invert_thickness=2.0,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            )
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.marine_parts) == 1

    rlock = resolved.marine_parts[0]
    assert rlock.tag == "LOCK-MAIN"
    assert rlock.chamber_length == 100.0
    assert rlock.chamber_width == 16.0
    assert rlock.wall_height == 12.0
    assert rlock.wall_thickness == 2.5
    assert rlock.invert_thickness == 2.0

    # Verify U-channel profile
    # outer_W = 16.0 + 2 * 2.5 = 21.0
    # total_H = 12.0 + 2.0 = 14.0
    # section_area = (21.0 * 14.0) - (16.0 * 12.0) = 294.0 - 192.0 = 102.0 m2
    # expected_conc_vol = 102.0 * 100.0 = 10200.0 m3
    # expected_water_vol = 100.0 * 16.0 * 12.0 = 19200.0 m3
    expected_section_area = (21.0 * 14.0) - (16.0 * 12.0)
    expected_conc_vol = expected_section_area * 100.0
    expected_water_vol = 100.0 * 16.0 * 12.0

    assert len(rlock.u_channel_profile_points) == 8
    assert rlock.concrete_volume == pytest.approx(expected_conc_vol, rel=1e-5)
    assert rlock.chamber_water_volume == pytest.approx(expected_water_vol, rel=1e-5)

    # QTO
    qto = calculate_qto(resolved)
    eqto = qto.get_element("LOCK-MAIN")
    assert eqto is not None
    assert eqto.concrete_volume == pytest.approx(expected_conc_vol, rel=1e-5)
    assert eqto.marine is not None
    assert eqto.marine.chamber_length == 100.0
    assert eqto.marine.chamber_width == 16.0
    assert eqto.marine.wall_height == 12.0
    assert eqto.marine.wall_thickness == 2.5
    assert eqto.marine.invert_thickness == 2.0
    assert eqto.marine.chamber_water_volume == pytest.approx(expected_water_vol, rel=1e-5)


def test_marine_lock_ifc43_compilation_and_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape creation with ifcopenshell for lock chamber."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-LOCK-02", name="Canal Lock 3D Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 80.0}, axes_y={"A": 0.0, "B": 20.0}),
        materials=[],
        elements=[
            IfcMarinePart(
                tag="LOCK-CHAMBER-01",
                predefined_type="LOCK",
                chamber_length=80.0,
                chamber_width=14.0,
                wall_height=10.0,
                wall_thickness=2.0,
                invert_thickness=1.8,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
        ],
    )

    # 1. Compile to IFC4.3
    ifc_file = tmp_path / "lock_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    # 2. Verify IFC entity creation
    marine_parts = model.by_type("IfcMarinePart")
    if not marine_parts:
        marine_parts = [e for e in model.by_type("IfcBuildingElementProxy") if "MarinePart" in (e.ObjectType or "")]

    assert len(marine_parts) == 1

    # 3. Verify 3D geometry shape creation with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()
    shape_lock = ifcopenshell.geom.create_shape(settings, marine_parts[0])
    assert shape_lock is not None
    assert len(shape_lock.geometry.verts) > 0

    # 4. STEP physical file fallback export
    step_file = tmp_path / "lock_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCMARINEPART" in step_content or "IfcMarinePart" in step_content

    # 5. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcMarinePart" in html
    assert "LOCK-CHAMBER-01" in html
