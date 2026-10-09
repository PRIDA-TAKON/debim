"""
Unit test suite for IFC4.3 Civil Marine Infrastructure: IfcMooringDevice quayside rubber fenders.
Verifies schema validation, quay face mounting orientation, QTO calculation, IFC4.3 compilation,
and 3D shape generation with ifcopenshell.geom.create_shape.
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
    IfcMooringDevice,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_marine_fender_schema_validation():
    """Test Pydantic v2 schema validation for IfcMooringDevice and fender types."""
    fender = IfcMooringDevice(
        tag="FEN-01",
        name="Container Berth Fender 1",
        predefined_type="FENDER",
        fender_type="ARCH",
        height_mm=800.0,
        length_mm=1500.0,
        frontal_panel=True,
        quay_wall="QUAY-01",
        placement={"face": "FRONT", "offset_x": 10.0, "offset_z": -0.5},
    )
    assert fender.class_ == "IfcMooringDevice"
    assert fender.tag == "FEN-01"
    assert fender.predefined_type == "FENDER"
    assert fender.fender_type == "ARCH"
    assert fender.height_mm == 800.0
    assert fender.length_mm == 1500.0
    assert fender.frontal_panel is True
    assert fender.quay_wall == "QUAY-01"
    assert fender.placement.quay_wall == "QUAY-01"

    # Test all fender types
    for ftype in ["ARCH", "CONE", "CYLINDRICAL", "CELL"]:
        f = IfcMooringDevice(tag=f"FEN-{ftype}", fender_type=ftype)
        assert f.fender_type == ftype

    # Test alias resolution for marine_part
    f_alias = IfcMooringDevice(
        tag="FEN-02",
        marine_part="BERTH-MAIN",
        height_mm=1000.0,
        length_mm=2000.0,
        frontal_panel=False,
    )
    assert f_alias.quay_wall == "BERTH-MAIN"
    assert f_alias.placement.quay_wall == "BERTH-MAIN"
    assert f_alias.frontal_panel is False


def test_marine_fender_resolution_and_mounting_orientation():
    """Test fender face mounting on quay vertical faces and orientation vectors."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-FENDER-01", name="Quay Fender Placement Test"),
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
            # Front face mounting
            IfcMooringDevice(
                tag="FEN-FRONT",
                fender_type="ARCH",
                height_mm=800.0,
                length_mm=1500.0,
                frontal_panel=True,
                quay_wall="QUAY-01",
                placement={"face": "FRONT", "offset_x": 10.0, "offset_z": 0.0},
            ),
            # Back face mounting
            IfcMooringDevice(
                tag="FEN-BACK",
                fender_type="CONE",
                height_mm=1000.0,
                length_mm=2000.0,
                frontal_panel=True,
                quay_wall="QUAY-01",
                placement={"face": "BACK", "offset_x": -10.0, "offset_z": 0.0},
            ),
            # Left face mounting
            IfcMooringDevice(
                tag="FEN-LEFT",
                fender_type="CELL",
                height_mm=1200.0,
                length_mm=1800.0,
                frontal_panel=False,
                quay_wall="QUAY-01",
                placement={"face": "LEFT", "offset_y": 5.0, "offset_z": 0.0},
            ),
            # Right face mounting
            IfcMooringDevice(
                tag="FEN-RIGHT",
                fender_type="CYLINDRICAL",
                height_mm=600.0,
                length_mm=1200.0,
                frontal_panel=False,
                quay_wall="QUAY-01",
                placement={"face": "RIGHT", "offset_y": -5.0, "offset_z": 0.0},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.mooring_devices) == 4

    # QUAY-01 position is at (0, 0, 0), deck_elevation = 3.0, width = 20.0, length = 60.0
    # 1. Front face (Y = -10.0)
    fen_front = next(d for d in resolved.mooring_devices if d.tag == "FEN-FRONT")
    assert fen_front.position[0] == 10.0
    assert fen_front.position[1] == -10.0
    assert fen_front.position[2] == 3.0 - (0.80 / 2.0)  # 2.6 m
    assert fen_front.normal_vector == (0.0, -1.0, 0.0)
    assert fen_front.frontal_panel_area == pytest.approx(1.5 * 0.8)  # 1.2 m2

    # 2. Back face (Y = +10.0)
    fen_back = next(d for d in resolved.mooring_devices if d.tag == "FEN-BACK")
    assert fen_back.position[0] == -10.0
    assert fen_back.position[1] == 10.0
    assert fen_back.position[2] == 3.0 - (1.00 / 2.0)  # 2.5 m
    assert fen_back.normal_vector == (0.0, 1.0, 0.0)
    assert fen_back.frontal_panel_area == pytest.approx(2.0 * 1.0)  # 2.0 m2

    # 3. Left face (X = -30.0)
    fen_left = next(d for d in resolved.mooring_devices if d.tag == "FEN-LEFT")
    assert fen_left.position[0] == -30.0
    assert fen_left.position[1] == 5.0
    assert fen_left.normal_vector == (-1.0, 0.0, 0.0)
    assert fen_left.frontal_panel_area == 0.0  # frontal_panel is False

    # 4. Right face (X = +30.0)
    fen_right = next(d for d in resolved.mooring_devices if d.tag == "FEN-RIGHT")
    assert fen_right.position[0] == 30.0
    assert fen_right.position[1] == -5.0
    assert fen_right.normal_vector == (1.0, 0.0, 0.0)
    assert fen_right.frontal_panel_area == 0.0


def test_marine_fender_qto_calculation():
    """Test quantity take-off for quayside marine fenders."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-FENDER-QTO", name="Fender QTO Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[
            IfcMooringDevice(
                tag="FEN-QTO-01",
                fender_type="ARCH",
                height_mm=800.0,
                length_mm=1500.0,
                frontal_panel=True,
                placement={"position": [10.0, -5.0, 2.0]},
            ),
            IfcMooringDevice(
                tag="FEN-QTO-02",
                fender_type="CONE",
                height_mm=1000.0,
                length_mm=2000.0,
                frontal_panel=False,
                placement={"position": [20.0, -5.0, 2.0]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    qto = calculate_qto(resolved)

    eqto1 = qto.get_element("FEN-QTO-01")
    assert eqto1 is not None
    assert eqto1.mooring_device is not None
    assert eqto1.mooring_device.count == 1
    assert eqto1.mooring_device.piece_count == 1
    assert eqto1.mooring_device.fender_type == "ARCH"
    assert eqto1.mooring_device.height_mm == 800.0
    assert eqto1.mooring_device.length_mm == 1500.0
    assert eqto1.mooring_device.frontal_panel is True
    assert eqto1.mooring_device.frontal_panel_area == pytest.approx(1.20)

    eqto2 = qto.get_element("FEN-QTO-02")
    assert eqto2 is not None
    assert eqto2.mooring_device is not None
    assert eqto2.mooring_device.count == 1
    assert eqto2.mooring_device.piece_count == 1
    assert eqto2.mooring_device.frontal_panel is False
    assert eqto2.mooring_device.frontal_panel_area == 0.0


def test_marine_fender_ifc43_compilation_and_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape generation with ifcopenshell."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-FENDER-IFC", name="Fender IFC Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[
            IfcMarinePart(
                tag="QUAY-MAIN",
                predefined_type="QUAY",
                length=30.0,
                width=10.0,
                deck_thickness=0.50,
                deck_elevation=2.0,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
            IfcMooringDevice(
                tag="FENDER-01",
                fender_type="ARCH",
                height_mm=800.0,
                length_mm=1500.0,
                frontal_panel=True,
                quay_wall="QUAY-MAIN",
                placement={"face": "FRONT", "offset_x": 0.0},
            ),
        ],
    )

    # 1. Compile to IFC4.3
    ifc_file = tmp_path / "fender_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    # 2. Verify IFC entity counts
    fenders = model.by_type("IfcMooringDevice")
    if not fenders:
        fenders = [e for e in model.by_type("IfcBuildingElementProxy") if "MooringDevice" in (e.ObjectType or "")]

    assert len(fenders) == 1

    # 3. Verify 3D geometry shape creation with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()
    shape_fender = ifcopenshell.geom.create_shape(settings, fenders[0])
    assert shape_fender is not None
    assert len(shape_fender.geometry.verts) > 0

    # 4. STEP physical file fallback export
    step_file = tmp_path / "fender_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCMOORINGDEVICE" in step_content or "IfcMooringDevice" in step_content

    # 5. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcMooringDevice" in html
    assert "FENDER-01" in html
