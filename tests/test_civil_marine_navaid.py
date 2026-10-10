"""
Unit test suite for IFC4.3 Maritime Navigation Aids: IfcNavigationElement (BUOY, BEACON, LIGHT, MARKER).
Verifies schema validation, 3D spatial resolution, QTO calculation, IFC4.3 compilation,
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
    IfcNavigationElement,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_navigation_element_schema_validation():
    """Test Pydantic v2 schema validation for IfcNavigationElement and predefined types."""
    nav = IfcNavigationElement(
        tag="BUOY-01",
        name="Outer Channel Fairway Buoy",
        predefined_type="BUOY",
        focal_height=6.5,
        light_color="GREEN",
        nominal_range_nm=8.0,
        anchor_chain_length=35.0,
        placement={"offset_x": 100.0, "offset_y": 200.0, "offset_z": 0.0},
    )
    assert nav.class_ == "IfcNavigationElement"
    assert nav.tag == "BUOY-01"
    assert nav.predefined_type == "BUOY"
    assert nav.focal_height == 6.5
    assert nav.light_color == "GREEN"
    assert nav.nominal_range_nm == 8.0
    assert nav.anchor_chain_length == 35.0

    # Test predefined types for IfcNavigationElement
    for ptype in ["BUOY", "BEACON", "LIGHT", "MARKER"]:
        n = IfcNavigationElement(tag=f"NAV-{ptype}", predefined_type=ptype)
        assert n.predefined_type == ptype

    # Test defaults
    default_nav = IfcNavigationElement(tag="NAV-DEF")
    assert default_nav.predefined_type == "BUOY"
    assert default_nav.focal_height == 5.0
    assert default_nav.light_color == "GREEN"
    assert default_nav.nominal_range_nm == 6.0
    assert default_nav.anchor_chain_length == 20.0


def test_navigation_element_resolution_and_qto():
    """Test 3D spatial resolution and quantity take-off for maritime navigation aids."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-NAV-01", name="Port Navigation Channel"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="SEA_LEVEL", name="Sea Level", elevation=0.0, height=5.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 500.0}, axes_y={"A": 0.0, "B": 200.0}),
        materials=[
            {"id": "MAT_STEEL_BUOY", "name": "Marine Grade Steel", "category": "steel", "unit_cost_ref": "MAT-STEEL"},
        ],
        elements=[
            IfcNavigationElement(
                tag="BUOY-GREEN",
                material="MAT_STEEL_BUOY",
                predefined_type="BUOY",
                focal_height=5.0,
                light_color="GREEN",
                nominal_range_nm=6.0,
                anchor_chain_length=30.0,
                placement={"storey": "SEA_LEVEL", "grid": ["1", "A"], "offset_x": 50.0, "offset_y": 20.0},
            ),
            IfcNavigationElement(
                tag="BEACON-RED",
                material="MAT_STEEL_BUOY",
                predefined_type="BEACON",
                focal_height=10.0,
                light_color="RED",
                nominal_range_nm=12.0,
                anchor_chain_length=0.0,
                placement={"storey": "SEA_LEVEL", "grid": ["2", "B"]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.navigation_elements) == 2

    r_nav1 = resolved.navigation_elements[0]
    assert r_nav1.tag == "BUOY-GREEN"
    assert r_nav1.focal_height == 5.0
    assert r_nav1.light_color == "GREEN"
    assert r_nav1.nominal_range_nm == 6.0
    assert r_nav1.anchor_chain_length == 30.0
    assert r_nav1.position == (50.0, 20.0, 0.0)

    r_nav2 = resolved.navigation_elements[1]
    assert r_nav2.tag == "BEACON-RED"
    assert r_nav2.focal_height == 10.0
    assert r_nav2.light_color == "RED"
    assert r_nav2.position == (500.0, 200.0, 0.0)

    # QTO
    qto = calculate_qto(resolved)
    eqto1 = qto.get_element("BUOY-GREEN")
    assert eqto1 is not None
    assert eqto1.navigation is not None
    assert eqto1.navigation.count == 1
    assert eqto1.navigation.anchor_chain_length == 30.0
    assert eqto1.navigation.focal_height == 5.0
    assert eqto1.navigation.nominal_range_nm == 6.0
    assert eqto1.navigation.light_color == "GREEN"
    assert eqto1.navigation.predefined_type == "BUOY"

    eqto2 = qto.get_element("BEACON-RED")
    assert eqto2 is not None
    assert eqto2.navigation is not None
    assert eqto2.navigation.count == 1
    assert eqto2.navigation.anchor_chain_length == 0.0
    assert eqto2.navigation.focal_height == 10.0

    assert qto.total_navigation_elements_count == 2
    assert qto.total_anchor_chain_length == 30.0


def test_navigation_element_ifc43_compilation_and_shape_generation(tmp_path: Path):
    """Test IFC4.3 compilation and 3D shape generation with ifcopenshell."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-NAV-02", name="Nautical Aids Model"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="SEA_LEVEL", name="Sea Level", elevation=0.0, height=5.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 100.0}),
        materials=[],
        elements=[
            IfcNavigationElement(
                tag="LIGHT-BEACON-01",
                predefined_type="LIGHT",
                focal_height=12.0,
                light_color="WHITE",
                nominal_range_nm=15.0,
                placement={"storey": "SEA_LEVEL", "grid": ["1", "A"]},
            ),
        ],
    )

    # 1. Compile to IFC4.3
    ifc_file = tmp_path / "navaid_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    # 2. Verify IFC entity counts
    nav_elements = model.by_type("IfcNavigationElement")
    if not nav_elements:
        nav_elements = [e for e in model.by_type("IfcBuildingElementProxy") if "NavigationElement" in (e.ObjectType or "")]

    assert len(nav_elements) == 1

    # 3. Verify 3D geometry shape creation with ifcopenshell.geom.create_shape
    settings = ifcopenshell.geom.settings()
    shape_nav = ifcopenshell.geom.create_shape(settings, nav_elements[0])
    assert shape_nav is not None
    assert len(shape_nav.geometry.verts) > 0

    # 4. STEP physical file fallback export
    step_file = tmp_path / "navaid_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCNAVIGATIONELEMENT" in step_content or "IfcNavigationElement" in step_content

    # 5. Viewer HTML generation
    html = generate_viewer_html(manifest)
    assert "IfcNavigationElement" in html
    assert "LIGHT-BEACON-01" in html
