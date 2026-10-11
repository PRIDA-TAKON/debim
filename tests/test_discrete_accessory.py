"""
Unit and integration tests for IfcDiscreteAccessory schema, spatial resolution,
QTO takeoff, IFC compiler, 3D viewer generation, and 2D cut-plane projection.
"""

from pathlib import Path
import pytest
import ifcopenshell

from debim.compiler import compile_to_ifc
from debim.draw.projection import slice_storey
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    DiscreteAccessoryPlacement,
    Grids,
    IfcDiscreteAccessory,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    Units,
)
from debim.viewer import generate_viewer_html


def test_discrete_accessory_schema_and_resolution():
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="P1", name="Accessory Test", units=Units()),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST_01", name="Ground Floor", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"GX_1": 0.0, "GX_2": 6.0}, axes_y={"GY_1": 0.0, "GY_2": 6.0}),
        materials=[Material(id="MAT_STEEL", name="Steel S355", category="steel", unit_cost_ref="MAT-STEEL")],
        elements=[
            IfcDiscreteAccessory(
                class_="IfcDiscreteAccessory",
                tag="ANCHOR-01",
                name="Anchor Bolt M24",
                material="MAT_STEEL",
                predefined_type="ANCHORBOLT",
                width=0.25,
                depth=0.25,
                height=0.40,
                placement=DiscreteAccessoryPlacement(
                    storey="ST_01",
                    grid=("GX_1", "GY_1"),
                    offset_x=0.5,
                    offset_y=0.5,
                    offset_z=0.1,
                    rotation=45.0,
                ),
            )
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.discrete_accessories) == 1

    da = resolved.discrete_accessories[0]
    assert da.tag == "ANCHOR-01"
    assert da.predefined_type == "ANCHORBOLT"
    assert da.position == (0.5, 0.5, 0.1)
    assert da.width == 0.25
    assert da.depth == 0.25
    assert da.height == 0.40
    assert da.rotation == (0.0, 0.0, 45.0)

    # Test QTO
    qto = calculate_qto(resolved)
    assert len(qto.elements) == 1
    eqto = qto.elements[0]
    assert eqto.tag == "ANCHOR-01"
    assert eqto.mep is not None
    assert eqto.mep.count == 1
    assert eqto.mep.fixture_type == "ANCHORBOLT"


def test_discrete_accessory_ifc_compilation(tmp_path: Path):
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="P1", name="Accessory IFC Test", units=Units()),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST_01", name="Level 1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"GX_1": 0.0}, axes_y={"GY_1": 0.0}),
        materials=[Material(id="MAT_STEEL", name="Steel", category="steel", unit_cost_ref="MAT-STEEL")],
        elements=[
            IfcDiscreteAccessory(
                class_="IfcDiscreteAccessory",
                tag="BRACKET-01",
                predefined_type="BRACKET",
                width=0.30,
                depth=0.20,
                height=0.50,
                placement=DiscreteAccessoryPlacement(storey="ST_01", position=(1.0, 2.0, 0.5)),
            )
        ],
    )

    resolved = resolve_manifest(manifest)

    # 1. STEP Compilation
    step_out = tmp_path / "accessory.ifc"
    compile_to_ifc(resolved, step_out)
    assert step_out.exists()

    step_model = ifcopenshell.open(str(step_out))
    accs = step_model.by_type("IfcDiscreteAccessory")
    assert len(accs) == 1
    assert accs[0].Name == "BRACKET-01"
    assert accs[0].PredefinedType == "BRACKET"

    # Verify 3D Geometry
    shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), accs[0])
    assert shape is not None


def test_discrete_accessory_viewer_and_projection():
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="P1", name="Accessory View Test", units=Units()),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST_01", name="Level 1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"GX_1": 0.0}, axes_y={"GY_1": 0.0}),
        materials=[Material(id="MAT_STEEL", name="Steel", category="steel", unit_cost_ref="MAT-STEEL")],
        elements=[
            IfcDiscreteAccessory(
                class_="IfcDiscreteAccessory",
                tag="SHOE-01",
                predefined_type="SHOE",
                width=0.40,
                depth=0.40,
                height=0.60,
                placement=DiscreteAccessoryPlacement(storey="ST_01", position=(2.0, 2.0, 0.8)),
            )
        ],
    )

    resolved = resolve_manifest(manifest)

    # 3D Viewer HTML Generation
    html = generate_viewer_html(resolved)
    assert "IfcDiscreteAccessory" in html
    assert "SHOE-01" in html

    # 2D Projection
    cut_res = slice_storey(resolved, storey_id="ST_01", cut_offset_z=1.0)
    all_cut_tags = [e.tag for e in cut_res.cut_elements] + [e.tag for e in cut_res.projection_elements]
    assert "SHOE-01" in all_cut_tags
