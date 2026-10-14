"""
Unit tests for parametric IfcRoof generator (GABLE_HIP) and pitch_deg member orientation.
Verifies GABLE_HIP (Manila / Vernacular Thai-Isan) roof spatial resolution,
rafter and purlin framing member counts, 3D bounding box,
and pitch_deg member orientation for IfcBeam and IfcMember.
"""

import math
from pathlib import Path
import pytest

from debim.schema import (
    BeamPlacement,
    BoxProfile,
    Grids,
    IfcBeam,
    IfcMember,
    IfcRoof,
    Material,
    ProjectInfo,
    ProjectManifest,
    RoofCoveringConfig,
    RoofFramingConfig,
    RoofPlacement,
    SpatialStructure,
    Storey,
)
from debim.resolver import resolve_manifest
from debim.compiler import compile_to_ifc


@pytest.fixture
def sample_gable_hip_manifest() -> ProjectManifest:
    """Fixture providing a project manifest with a GABLE_HIP (Manila) roof and pitched members."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-GABLE-HIP-TEST", name="Parametric Roof Test Pavilion"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Ground Level", elevation=0.0, height=3.0),
                Storey(id="L2_ROOF", name="Roof Level", elevation=3.0, height=1.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 10.0},
            axes_y={"A": 0.0, "B": 6.0},
        ),
        materials=[
            Material(
                id="STEEL_SS400",
                name="Structural Steel SS400",
                category="steel",
                unit_cost_ref="MAT-STEEL-01",
            ),
            Material(
                id="ROOF_TILE",
                name="CPAC Monier Concrete Tile",
                category="covering",
                unit_cost_ref="MAT-ROOF-TILE",
            ),
        ],
        elements=[
            IfcRoof(
                tag="ROOF-GABLE-HIP-01",
                material="STEEL_SS400",
                roof_type="GABLE_HIP",
                pitch_deg=32.5,  # 32.5 degrees pitch_deg without manual Euler calculation
                placement=RoofPlacement(
                    boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                    storey="L2_ROOF",
                    offset_z=0.0,
                    overhang=1.0,  # 1.0m eave overhang
                    ridge_orientation="X",
                ),
                covering=RoofCoveringConfig(
                    tile_type="CONCRETE_TILE",
                    insulation=True,
                    fascia_board=True,
                    ridge_cap=True,
                ),
                framing=RoofFramingConfig(
                    truss_type="STEEL_TRUSS",
                    material="STEEL_SS400",
                    rafter_spacing=1.0,
                    purlin_spacing=0.32,
                    profiles={
                        "rafter": "C100x50x20x3.2",
                        "purlin": "C75x45x15x2.3",
                        "ridge": "2C150x50x20x3.2",
                    },
                ),
            ),
            IfcBeam(
                tag="PITCHED-BEAM-01",
                material="STEEL_SS400",
                profile=BoxProfile(width=0.15, depth=0.30),
                placement=BeamPlacement(
                    from_grid=("1", "A"),
                    to_grid=("2", "A"),
                    storey="L1",
                    offset_z=0.0,
                ),
                pitch_deg=30.0,
            ),
            IfcMember(
                tag="PITCHED-MEMBER-01",
                material="STEEL_SS400",
                profile=BoxProfile(width=0.10, depth=0.10),
                placement=BeamPlacement(
                    from_grid=("1", "A"),
                    to_grid=("1", "B"),
                    storey="L1",
                    offset_z=0.0,
                ),
                pitch_deg=45.0,
            ),
        ],
    )


def test_gable_hip_roof_resolution(sample_gable_hip_manifest):
    """Test 3D coordinate resolution of GABLE_HIP roof."""
    resolved = resolve_manifest(sample_gable_hip_manifest)
    assert len(resolved.roofs) == 1
    r_roof = resolved.roofs[0]

    assert r_roof.roof_type == "GABLE_HIP"
    assert r_roof.pitch == 32.5

    # Footprint calculation:
    # Grid X is 0.0 to 10.0 (width 10.0m), with 1.0m overhang -> -1.0 to 11.0 (width 12.0m)
    # Grid Y is 0.0 to 6.0 (length 6.0m), with 1.0m overhang -> -1.0 to 7.0 (length 8.0m)
    # Total footprint area = 12.0 * 8.0 = 96.0 m2
    assert math.isclose(r_roof.total_footprint_area, 96.0, rel_tol=1e-3)

    # Elevation calculations:
    # Half-span along Y = 8.0 / 2.0 = 4.0m
    # Peak rise = 4.0 * tan(32.5 deg)
    expected_rise = 4.0 * math.tan(math.radians(32.5))
    expected_ridge_elev = 3.0 + expected_rise
    assert math.isclose(r_roof.eaves_elevation, 3.0, rel_tol=1e-3)
    assert math.isclose(r_roof.ridge_elevation, expected_ridge_elev, rel_tol=1e-3)

    # 6 planes for GABLE_HIP: 2 main slopes (South, North) + 2 end hips (WestHip, EastHip) + 2 gable faces (WestGable, EastGable)
    assert len(r_roof.planes) == 6
    plane_tags = {p.tag for p in r_roof.planes}
    assert any("SouthSlope" in tag for tag in plane_tags)
    assert any("NorthSlope" in tag for tag in plane_tags)
    assert any("WestHip" in tag for tag in plane_tags)
    assert any("WestGable" in tag for tag in plane_tags)
    assert any("EastHip" in tag for tag in plane_tags)
    assert any("EastGable" in tag for tag in plane_tags)

    # Check framing member counts and profiles
    rafters = [m for m in r_roof.framing_members if m.member_type in ("COMMON_RAFTER", "JACK_RAFTER")]
    purlins = [m for m in r_roof.framing_members if m.member_type == "PURLIN"]

    assert len(rafters) > 0
    assert len(purlins) > 0

    for raf in rafters:
        assert raf.profile == "C100x50x20x3.2"
        assert raf.length > 0.0

    for pur in purlins:
        assert pur.profile == "C75x45x15x2.3"
        assert pur.length > 0.0

    # 3D bounding box verification
    min_x = min(p[0] for plane in r_roof.planes for p in plane.polygon)
    max_x = max(p[0] for plane in r_roof.planes for p in plane.polygon)
    min_y = min(p[1] for plane in r_roof.planes for p in plane.polygon)
    max_y = max(p[1] for plane in r_roof.planes for p in plane.polygon)
    min_z = min(p[2] for plane in r_roof.planes for p in plane.polygon)
    max_z = max(p[2] for plane in r_roof.planes for p in plane.polygon)

    assert math.isclose(min_x, -1.0, abs_tol=1e-2)
    assert math.isclose(max_x, 11.0, abs_tol=1e-2)
    assert math.isclose(min_y, -1.0, abs_tol=1e-2)
    assert math.isclose(max_y, 7.0, abs_tol=1e-2)
    assert math.isclose(min_z, 3.0, abs_tol=1e-2)
    assert math.isclose(max_z, expected_ridge_elev, abs_tol=1e-2)


def test_pitch_deg_member_orientation(sample_gable_hip_manifest):
    """Test pitch_deg member orientation for IfcBeam and IfcMember."""
    resolved = resolve_manifest(sample_gable_hip_manifest)

    # Pitch Beam test (span 10.0m along X, pitch 30 deg)
    r_beam = resolved.get_element_by_tag("PITCHED-BEAM-01")
    assert r_beam is not None
    assert math.isclose(r_beam.start_point[2], 0.0, rel_tol=1e-3)

    # Expected dz = 10.0 * tan(30 deg) = 5.7735m
    expected_dz_beam = 10.0 * math.tan(math.radians(30.0))
    assert math.isclose(r_beam.end_point[2], expected_dz_beam, rel_tol=1e-3)
    assert math.isclose(math.degrees(r_beam.pitch_angle), 30.0, rel_tol=1e-2)

    # Pitch Member test (span 6.0m along Y, pitch 45 deg)
    r_member = resolved.get_element_by_tag("PITCHED-MEMBER-01")
    assert r_member is not None
    assert math.isclose(r_member.start_point[2], 0.0, rel_tol=1e-3)

    # Expected dz = 6.0 * tan(45 deg) = 6.0m
    expected_dz_member = 6.0 * math.tan(math.radians(45.0))
    assert math.isclose(r_member.end_point[2], expected_dz_member, rel_tol=1e-3)
    assert math.isclose(math.degrees(r_member.pitch_angle), 45.0, rel_tol=1e-2)


def test_gable_hip_ifc_compilation(sample_gable_hip_manifest, tmp_path):
    """Test compiling GABLE_HIP roof and pitched members to IFC file."""
    out_ifc = tmp_path / "gable_hip_roof.ifc"
    compile_to_ifc(sample_gable_hip_manifest, out_ifc)
    assert out_ifc.exists()

    content = out_ifc.read_text(encoding="utf-8")
    assert "IFCROOF" in content.upper()
    assert "HIPPED_GABLE_ROOF" in content.upper()
    assert "IFCMEMBER" in content.upper()
    assert "PITCHED-MEMBER-01" in content
