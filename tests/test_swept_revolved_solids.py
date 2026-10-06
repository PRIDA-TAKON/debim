"""
Unit tests for Swept Disk Solids (IfcSweptDiskSolid) and Revolved Area Solids (IfcRevolvedAreaSolid).
"""

import math
import tempfile
from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.schema import (
    BoxProfile,
    CircularProfile,
    CustomElementPlacement,
    Grids,
    IfcCustomElement,
    Material,
    ProjectInfo,
    ProjectManifest,
    RevolvedAreaSolid,
    SpatialStructure,
    Storey,
    SweptDiskSolid,
)
from debim.resolver import (
    ResolvedRevolvedArea,
    ResolvedSweptDisk,
    resolve_manifest,
)
from debim.qto import calculate_element_qto, calculate_qto
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html


def create_test_manifest_with_solids(
    swept_disk: SweptDiskSolid,
    revolved_area: RevolvedAreaSolid,
) -> ProjectManifest:
    """Helper fixture creating a ProjectManifest containing custom elements with solids."""
    return ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PROJ-SOLIDS", name="Solids Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="L1", name="Level 1", elevation=0.0, height=3.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[
            Material(id="MAT-STEEL", name="Steel SS400", category="steel", unit_cost_ref="COST-STEEL")
        ],
        elements=[
            IfcCustomElement(
                class_="IfcCustomElement",
                tag="PIPE-CURVED-01",
                name="Curved MEP Pipe",
                material="MAT-STEEL",
                placement=CustomElementPlacement(position=(1.0, 1.0, 0.5), storey="L1"),
                solid=swept_disk,
                layer="mep/plumbing/pipes",
            ),
            IfcCustomElement(
                class_="IfcCustomElement",
                tag="DOME-TANK-01",
                name="Water Tank Dome",
                material="MAT-STEEL",
                placement=CustomElementPlacement(position=(3.0, 3.0, 0.0), storey="L1"),
                solid=revolved_area,
                layer="structure/tanks",
            ),
        ],
    )


def test_swept_disk_solid_schema_validation():
    """Test schema instantiation and validation for SweptDiskSolid."""
    # Valid solid
    solid = SweptDiskSolid(
        directrix=[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 3.0, 1.0]],
        radius=0.10,
        inner_radius=0.08,
    )
    assert solid.type == "SWEPT_DISK"
    assert solid.radius == 0.10
    assert solid.inner_radius == 0.08
    assert len(solid.directrix) == 3

    # Invalid radius <= 0
    with pytest.raises(ValidationError):
        SweptDiskSolid(
            directrix=[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
            radius=-0.05,
        )

    # Invalid inner_radius >= radius
    with pytest.raises(ValidationError):
        SweptDiskSolid(
            directrix=[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
            radius=0.10,
            inner_radius=0.12,
        )

    # Invalid directrix points (< 2 points)
    with pytest.raises(ValidationError):
        SweptDiskSolid(
            directrix=[[0.0, 0.0, 0.0]],
            radius=0.10,
        )


def test_revolved_area_solid_schema_validation():
    """Test schema instantiation and validation for RevolvedAreaSolid."""
    profile = BoxProfile(width=0.4, depth=0.2)
    solid = RevolvedAreaSolid(
        profile=profile,
        axis_point=(1.0, 0.0, 0.0),
        axis_direction=(0.0, 0.0, 1.0),
        revolution_angle=180.0,
    )
    assert solid.type == "REVOLVED_AREA"
    assert solid.profile.shape == "BOX"
    assert solid.axis_point == (1.0, 0.0, 0.0)
    assert solid.revolution_angle == 180.0

    # Invalid revolution angle <= 0 or > 360
    with pytest.raises(ValidationError):
        RevolvedAreaSolid(
            profile=profile,
            revolution_angle=400.0,
        )

    # Invalid zero axis direction
    with pytest.raises(ValidationError):
        RevolvedAreaSolid(
            profile=profile,
            axis_direction=(0.0, 0.0, 0.0),
        )


def test_spatial_resolver_solids():
    """Test spatial resolution of 3D SweptDisk and RevolvedArea solids."""
    swept = SweptDiskSolid(
        directrix=[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [3.0, 4.0, 0.0]],
        radius=0.15,
        inner_radius=0.10,
    )
    revolved = RevolvedAreaSolid(
        profile=BoxProfile(width=0.2, depth=0.5),
        axis_point=(2.0, 0.0, 0.0),
        axis_direction=(0.0, 0.0, 1.0),
        revolution_angle=360.0,
    )

    manifest = create_test_manifest_with_solids(swept, revolved)
    resolved = resolve_manifest(manifest)

    # Inspect Resolved Custom Elements
    pipe_elem = resolved.get_element_by_tag("PIPE-CURVED-01")
    assert pipe_elem is not None
    assert pipe_elem.resolved_solid is not None
    assert isinstance(pipe_elem.resolved_solid, ResolvedSweptDisk)

    s_disk = pipe_elem.resolved_solid
    # Directrix length = 3.0 + 4.0 = 7.0m
    assert s_disk.length == pytest.approx(7.0, abs=1e-4)
    assert s_disk.radius == 0.15
    assert s_disk.inner_radius == 0.10
    # World placement offset = (1.0, 1.0, 0.5)
    assert s_disk.directrix[0] == (1.0, 1.0, 0.5)
    assert s_disk.directrix[1] == (4.0, 1.0, 0.5)
    assert s_disk.directrix[2] == (4.0, 5.0, 0.5)

    tank_elem = resolved.get_element_by_tag("DOME-TANK-01")
    assert tank_elem is not None
    assert tank_elem.resolved_solid is not None
    assert isinstance(tank_elem.resolved_solid, ResolvedRevolvedArea)

    r_area = tank_elem.resolved_solid
    assert r_area.revolution_angle == 360.0
    assert r_area.distance_to_axis == pytest.approx(2.0, abs=1e-4)
    assert r_area.profile_area == pytest.approx(0.2 * 0.5, abs=1e-4)
    assert r_area.profile_perimeter == pytest.approx(2.0 * (0.2 + 0.5), abs=1e-4)


def test_deterministic_qto_solids():
    """Test deterministic volume and lateral surface area QTO formulas."""
    swept = SweptDiskSolid(
        directrix=[[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]],  # L = 10.0m
        radius=0.20,
        inner_radius=0.10,
    )
    # Revolved 2D Box (0.1m x 0.2m -> Area = 0.02 m², Perimeter = 0.6 m) around Z-axis at distance d = 1.5m
    revolved = RevolvedAreaSolid(
        profile=BoxProfile(width=0.1, depth=0.2),
        axis_point=(1.5, 0.0, 0.0),
        axis_direction=(0.0, 0.0, 1.0),
        revolution_angle=360.0,
    )

    manifest = create_test_manifest_with_solids(swept, revolved)
    resolved = resolve_manifest(manifest)
    qto = calculate_qto(resolved)

    # 1. Swept Disk QTO Check
    pipe_qto = qto.get_element("PIPE-CURVED-01")
    assert pipe_qto is not None
    # Expected Volume V = pi * (r^2 - r_in^2) * L = pi * (0.04 - 0.01) * 10 = 0.3 * pi m³
    expected_pipe_vol = math.pi * (0.20**2 - 0.10**2) * 10.0
    assert pipe_qto.concrete_volume == pytest.approx(expected_pipe_vol, rel=1e-4)

    # Expected Lateral Surface Area A = 2 * pi * (r + r_in) * L = 2 * pi * (0.30) * 10 = 6 * pi m²
    expected_pipe_area = 2.0 * math.pi * (0.20 + 0.10) * 10.0
    assert pipe_qto.formwork_area == pytest.approx(expected_pipe_area, rel=1e-4)

    # 2. Revolved Area QTO Check (Pappus's Centroid Theorem)
    # V = A_profile * 2 * pi * d * (360/360) = 0.02 * 2 * pi * 1.5 = 0.06 * pi m³
    tank_qto = qto.get_element("DOME-TANK-01")
    assert tank_qto is not None
    expected_tank_vol = (0.1 * 0.2) * (2.0 * math.pi * 1.5) * (360.0 / 360.0)
    assert tank_qto.concrete_volume == pytest.approx(expected_tank_vol, rel=1e-4)

    # Lateral Surface Area A = P_profile * 2 * pi * d * (360/360) = 0.6 * 2 * pi * 1.5 = 1.8 * pi m²
    expected_tank_area = (2.0 * (0.1 + 0.2)) * (2.0 * math.pi * 1.5) * (360.0 / 360.0)
    assert tank_qto.formwork_area == pytest.approx(expected_tank_area, rel=1e-4)


def test_ifc_export_solids():
    """Test IFC STEP physical file export containing IfcSweptDiskSolid and IfcRevolvedAreaSolid."""
    swept = SweptDiskSolid(
        directrix=[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 0.0]],
        radius=0.10,
    )
    revolved = RevolvedAreaSolid(
        profile=CircularProfile(radius=0.25),
        axis_point=(1.0, 0.0, 0.0),
        axis_direction=(0.0, 0.0, 1.0),
        revolution_angle=180.0,
    )

    manifest = create_test_manifest_with_solids(swept, revolved)
    resolved = resolve_manifest(manifest)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_ifc_fallback = Path(tmp_dir) / "solids_fallback.ifc"
        compile_to_ifc(resolved, output_path=tmp_ifc_fallback, force_fallback=True)

        assert tmp_ifc_fallback.exists()
        content = tmp_ifc_fallback.read_text(encoding="utf-8")
        assert "IFCSWEPTDISKSOLID" in content
        assert "IFCREVOLVEDAREASOLID" in content

        # Test ifcopenshell export
        tmp_ifc_native = Path(tmp_dir) / "solids_native.ifc"
        compile_to_ifc(resolved, output_path=tmp_ifc_native, force_fallback=False)
        assert tmp_ifc_native.exists()
        native_content = tmp_ifc_native.read_text(encoding="utf-8")
        assert "IFCSWEPTDISKSOLID" in native_content or "IFCREVOLVEDAREASOLID" in native_content


def test_viewer_html_generation_solids():
    """Test 3D HTML viewer generation containing solid representations."""
    swept = SweptDiskSolid(
        directrix=[[0.0, 0.0, 0.0], [1.0, 2.0, 0.0]],
        radius=0.08,
    )
    revolved = RevolvedAreaSolid(
        profile=BoxProfile(width=0.3, depth=0.3),
        axis_point=(0.5, 0.0, 0.0),
        axis_direction=(0.0, 0.0, 1.0),
        revolution_angle=360.0,
    )

    manifest = create_test_manifest_with_solids(swept, revolved)
    html = generate_viewer_html(manifest)

    assert "swept_disk" in html
    assert "revolved_area" in html
    assert "TubeGeometry" in html
    assert "LatheGeometry" in html
