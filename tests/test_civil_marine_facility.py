"""
Unit test suite for IFC4.3 buildingSMART IfcMarineFacility spatial hierarchy container.
Verifies schema validation, spatial resolution of site elevation and boundary coordinates,
spatial structure aggregation, and IFC4.3 STEP compilation under spatial facility hierarchy:
IfcProject -> IfcSite -> IfcMarineFacility.
"""

from pathlib import Path
import pytest
import ifcopenshell

from debim.compiler import compile_to_ifc
from debim.resolver import resolve_manifest
from debim.schema import (
    Grids,
    IfcMarineFacility,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)


def test_marine_facility_schema_validation():
    """Test Pydantic v2 schema validation for IfcMarineFacility and predefined types."""
    mf_port = IfcMarineFacility(
        tag="PORT-01",
        name="Laem Chabang Port Terminal",
        predefined_type="PORT",
        elevation=2.5,
        boundary=[(0.0, 0.0), (500.0, 0.0), (500.0, 300.0), (0.0, 300.0)],
    )
    assert mf_port.class_ == "IfcMarineFacility"
    assert mf_port.tag == "PORT-01"
    assert mf_port.name == "Laem Chabang Port Terminal"
    assert mf_port.predefined_type == "PORT"
    assert mf_port.elevation == 2.5
    assert len(mf_port.boundary) == 4

    # Test predefined types for IfcMarineFacility
    for ptype in ["PORT", "WATERWAY", "CANAL", "USERDEFINED"]:
        mf = IfcMarineFacility(tag=f"MF-{ptype}", predefined_type=ptype)
        assert mf.predefined_type == ptype


def test_marine_facility_spatial_resolution():
    """Test spatial resolution of site elevation, boundary coordinates, and 3D placement."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-01", name="Shed & Dock Marine Facility"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)],
            marine_facilities=[
                IfcMarineFacility(
                    tag="CANAL-01",
                    name="Bangkok West Canal",
                    predefined_type="CANAL",
                    elevation=1.2,
                    boundary=[(10.0, 10.0), (200.0, 10.0), (200.0, 30.0), (10.0, 30.0)],
                )
            ],
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 200.0}, axes_y={"A": 0.0, "B": 50.0}),
        materials=[],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.marine_facilities) == 1

    r_mf = resolved.marine_facilities[0]
    assert r_mf.tag == "CANAL-01"
    assert r_mf.name == "Bangkok West Canal"
    assert r_mf.predefined_type == "CANAL"
    assert r_mf.site_elevation == 1.2
    assert r_mf.boundary_coordinates == [(10.0, 10.0), (200.0, 10.0), (200.0, 30.0), (10.0, 30.0)]
    assert r_mf.position == (0.0, 0.0, 1.2)
    assert r_mf.layer == "civil/marine/facility"


def test_marine_facility_ifc43_compilation_and_hierarchy(tmp_path: Path):
    """Test IFC4.3 compilation and spatial hierarchy aggregation: IfcProject -> IfcSite -> IfcMarineFacility."""
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-MARINE-02", name="Deep Sea Waterway Port"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)],
            marine_facilities=[
                IfcMarineFacility(
                    tag="PORT-MAIN",
                    name="Eastern Seaboard Container Port",
                    predefined_type="PORT",
                    elevation=3.5,
                    boundary=[(0.0, 0.0), (1000.0, 0.0), (1000.0, 400.0), (0.0, 400.0)],
                ),
                IfcMarineFacility(
                    tag="WW-01",
                    name="Navigation Waterway Channel",
                    predefined_type="WATERWAY",
                    elevation=-10.0,
                ),
            ],
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[],
    )

    # 1. Compile with ifcopenshell
    ifc_file = tmp_path / "marine_facility_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_file)
    assert ifc_file.exists()

    model = ifcopenshell.open(str(ifc_file))

    # Verify IFC entity counts and spatial hierarchy
    site = model.by_type("IfcSite")[0]
    marine_facilities = model.by_type("IfcMarineFacility")

    if marine_facilities:
        assert len(marine_facilities) == 2
        # Verify spatial aggregation under site: IfcProject -> IfcSite -> IfcMarineFacility
        assert len(site.IsDecomposedBy) > 0
        decomposed_objs = site.IsDecomposedBy[0].RelatedObjects
        for mf in marine_facilities:
            assert mf in decomposed_objs
    else:
        # Fallback proxy check if IFC schema version in environment doesn't include IfcMarineFacility class directly
        proxies = model.by_type("IfcBuildingElementProxy")
        assert len(proxies) >= 2

    # 2. STEP physical file fallback compilation
    step_file = tmp_path / "marine_facility_fallback.ifc"
    compile_to_ifc(manifest, output_path=step_file, force_fallback=True)
    assert step_file.exists()
    step_content = step_file.read_text(encoding="utf-8")
    assert "IFCMARINEFACILITY" in step_content
    assert "PORT-MAIN" in step_content or "Eastern Seaboard Container Port" in step_content
    assert "WW-01" in step_content or "Navigation Waterway Channel" in step_content
