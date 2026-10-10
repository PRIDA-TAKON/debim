"""
Unit test suite for IFC4.3 Civil Marine Infrastructure: Dry Docks and Slipways (IfcMarinePart).
Validates schema validation, dock/slipway geometry resolution, QTO concrete & basin excavation volume calculation,
IFC4.3 compilation, and 3D shape generation with ifcopenshell.geom.create_shape.
"""

from pathlib import Path
import pytest
import ifcopenshell
import ifcopenshell.geom

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    FootingPiles,
    Grids,
    IfcMarinePart,
    PileProfile,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_drydock_and_slipway_schema_validation():
    """Test Pydantic v2 schema validation for dry dock and slipway parameters."""
    dd = IfcMarinePart(
        tag="DRYDOCK-01",
        name="Graving Dock 1",
        predefined_type="DRYDOCK",
        dock_length=120.0,
        dock_width=25.0,
        dock_depth=10.0,
        deck_thickness=0.60,
        sill_elevation=-3.0,
    )
    assert dd.class_ == "IfcMarinePart"
    assert dd.predefined_type == "DRYDOCK"
    assert dd.dock_length == 120.0
    assert dd.dock_width == 25.0
    assert dd.dock_depth == 10.0
    assert dd.length == 120.0
    assert dd.width == 25.0
    assert dd.depth == 10.0
    assert dd.sill_elevation == -3.0

    sw = IfcMarinePart(
        tag="SLIPWAY-01",
        name="Shipyard Slipway Ramp 1",
        predefined_type="SLIPWAY",
        dock_length=80.0,
        dock_width=15.0,
        dock_depth=6.0,
        floor_slope=0.05,  # 1:20 slope
        deck_thickness=0.50,
    )
    assert sw.predefined_type == "SLIPWAY"
    assert sw.dock_length == 80.0
    assert sw.dock_width == 15.0
    assert sw.floor_slope == 0.05


def test_drydock_and_slipway_resolution_and_qto():
    """Test 3D spatial resolution and QTO calculation for dry dock and slipway."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-SHIPYARD-01", name="Naval Shipyard Dockyard"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 150.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[
            {"id": "MAT_MARINE_CONC", "name": "Marine Grade C50 Concrete", "category": "concrete", "unit_cost_ref": "MAT-CONC"},
        ],
        elements=[
            IfcMarinePart(
                tag="DOCK-01",
                material="MAT_MARINE_CONC",
                predefined_type="DRYDOCK",
                dock_length=100.0,
                dock_width=20.0,
                dock_depth=10.0,
                deck_thickness=0.50,
                floor_slope=0.0,
                sill_elevation=-2.5,
                placement={"storey": "GROUND", "from_grid": ["1", "A"], "to_grid": ["2", "A"]},
            ),
            IfcMarinePart(
                tag="SLIP-01",
                material="MAT_MARINE_CONC",
                predefined_type="SLIPWAY",
                dock_length=60.0,
                dock_width=12.0,
                dock_depth=5.0,
                deck_thickness=0.40,
                floor_slope=0.05,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.marine_parts) == 2

    # 1. Dry dock verification
    r_dd = resolved.marine_parts[0]
    assert r_dd.tag == "DOCK-01"
    assert r_dd.dock_length == 100.0
    assert r_dd.dock_width == 20.0
    assert r_dd.dock_depth == 10.0

    # Floor slab concrete = L * W * t = 100 * 20 * 0.5 = 1000 m3
    assert r_dd.dock_floor_concrete_volume == 1000.0
    # Wall concrete = (2*L + W) * D * t = (200 + 20) * 10 * 0.5 = 1100 m3
    assert r_dd.dock_wall_concrete_volume == 1100.0
    # Total concrete = 1000 + 1100 = 2100 m3
    assert r_dd.concrete_volume == 2100.0
    # Basin excavation = L * W * D = 100 * 20 * 10 = 20000 m3
    assert r_dd.basin_excavation_volume == 20000.0

    # 2. QTO calculation
    qto = calculate_qto(resolved)
    eqto_dd = qto.get_element("DOCK-01")
    assert eqto_dd is not None
    assert eqto_dd.concrete_volume == 2100.0
    assert eqto_dd.marine is not None
    assert eqto_dd.marine.dock_floor_concrete_volume == 1000.0
    assert eqto_dd.marine.dock_wall_concrete_volume == 1100.0
    assert eqto_dd.marine.basin_excavation_volume == 20000.0

    eqto_sw = qto.get_element("SLIP-01")
    assert eqto_sw is not None
    assert eqto_sw.marine is not None
    assert eqto_sw.marine.basin_excavation_volume > 0

    assert qto.total_concrete_volume >= 2100.0
    assert qto.total_excavation_volume >= 20000.0


def test_drydock_ifc43_compilation_and_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape generation for dry docks."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-SHIPYARD-02", name="Drydock IFC Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 30.0}),
        materials=[],
        elements=[
            IfcMarinePart(
                tag="DRYDOCK-MAIN",
                predefined_type="DRYDOCK",
                dock_length=100.0,
                dock_width=25.0,
                dock_depth=8.0,
                deck_thickness=0.60,
                sill_elevation=-2.0,
                placement={"storey": "GROUND", "grid": ["1", "A"]},
            ),
        ],
    )

    # 1. Compile to IFC4.3
    ifc_file = tmp_path / "drydock_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    marine_parts = model.by_type("IfcMarinePart")
    if not marine_parts:
        marine_parts = [e for e in model.by_type("IfcBuildingElementProxy") if "MarinePart" in (e.ObjectType or "")]

    assert len(marine_parts) == 1

    settings = ifcopenshell.geom.settings()
    shape_dock = ifcopenshell.geom.create_shape(settings, marine_parts[0])
    assert shape_dock is not None
    assert len(shape_dock.geometry.verts) > 0

    # 2. STEP physical file fallback export
    step_file = tmp_path / "drydock_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCMARINEPART" in step_content or "IfcMarinePart" in step_content

    # 3. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcMarinePart" in html
    assert "DRYDOCK-MAIN" in html
    assert "basin_excavation_volume" in html
