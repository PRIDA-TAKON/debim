"""
Unit tests for IfcRoof, skylights, IfcCovering, IfcStair, IfcRailing, and IfcMember
extraction and roundtrip retention.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from debim.compiler import compile_to_ifc
from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.schema import (
    CoveringPlacement,
    IfcCovering,
    IfcCustomElement,
    IfcRoof,
    IfcWindow,
)
from tools.compare_ifc import compare_ifc_files, count_ifc_elements


@pytest.fixture
def duplex_manifest():
    fixture_path = Path(__file__).parent / "fixtures" / "Duplex_A_20110907.ifc"
    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")
    return import_ifc_to_manifest(fixture_path)


def test_extract_roofs_and_skylights(duplex_manifest):
    """Verify that IfcRoof and its skylight windows are extracted."""
    roofs = [e for e in duplex_manifest.elements if isinstance(e, IfcRoof)]
    assert len(roofs) == 1, f"Expected 1 roof, got {len(roofs)}"

    roof = roofs[0]
    assert roof.roof_type == "FLAT"
    assert len(roof.children) == 2, f"Expected 2 skylights on roof, got {len(roof.children)}"

    for child in roof.children:
        assert isinstance(child, IfcWindow)
        assert child.dimensions.width > 0
        assert child.dimensions.height > 0


def test_extract_coverings(duplex_manifest):
    """Verify that 13 ceiling coverings are extracted with correct storey offset and thickness."""
    coverings = [e for e in duplex_manifest.elements if isinstance(e, IfcCovering)]
    assert len(coverings) == 13, f"Expected 13 coverings, got {len(coverings)}"

    for cov in coverings:
        assert cov.covering_type == "CEILING"
        assert cov.placement.area is not None and cov.placement.area > 0
        assert cov.thickness > 0
        assert cov.placement.offset_z == 2.6, f"Expected offset_z 2.6, got {cov.placement.offset_z}"


def test_ceiling_resolution_and_normal_vector_alignment(duplex_manifest):
    """Verify resolved ceiling 3D coordinates, storey elevation, and downward normal orientation."""
    resolved = resolve_manifest(duplex_manifest)
    assert len(resolved.coverings) == 13

    for r_cov in resolved.coverings:
        assert r_cov.covering_type == "CEILING"
        st_id = r_cov.element.placement.storey
        # Level 1 elevation is 0.0 -> center Z should be 2.6
        # Level 2 elevation is 3.1 -> center Z should be 5.7
        if st_id == "Level 1":
            assert abs(r_cov.center[2] - 2.6) < 0.01, f"Expected Level 1 ceiling Z=2.6, got {r_cov.center[2]}"
        elif st_id == "Level 2":
            assert abs(r_cov.center[2] - 5.7) < 0.01, f"Expected Level 2 ceiling Z=5.7, got {r_cov.center[2]}"

        # Verify normal vector faces down towards floor (-Z)
        if r_cov.polygon and len(r_cov.polygon) >= 3:
            pts = r_cov.polygon
            p1, p2, p3 = pts[0], pts[1], pts[2]
            v1 = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
            v2 = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
            nz = v1[0] * v2[1] - v1[1] * v2[0]
            assert nz < 0, f"Expected downward normal (nz < 0), got {nz}"


def test_covering_default_thickness_fallback(tmp_path):
    """Verify that an imported IfcCovering with missing/0.0 thickness defaults to 0.02m (20mm)."""
    import ifcopenshell
    f = ifcopenshell.file(schema="IFC4")
    proj = f.create_entity("IfcProject", Name="TestProj")
    site = f.create_entity("IfcSite", Name="TestSite")
    bldg = f.create_entity("IfcBuilding", Name="TestBldg")
    st = f.create_entity("IfcBuildingStorey", Name="Level 1", Elevation=0.0)
    cov = f.create_entity("IfcCovering", Name="Ceiling_NoThick", PredefinedType="CEILING")
    f.create_entity("IfcRelContainedInSpatialStructure", RelatedElements=[cov], RelatingStructure=st)

    ifc_file_path = tmp_path / "test_no_thick.ifc"
    f.write(str(ifc_file_path))

    manifest = import_ifc_to_manifest(ifc_file_path)
    imported_covs = [e for e in manifest.elements if isinstance(e, IfcCovering)]
    assert len(imported_covs) == 1
    assert imported_covs[0].thickness == 0.02


def test_extract_stairs_railings_members(duplex_manifest):
    """Verify stairs, stair flights, railings, and structural members are extracted."""
    customs = [e for e in duplex_manifest.elements if isinstance(e, IfcCustomElement)]

    stairs = [c for c in customs if c.layer and "stairs" in c.layer and "stairflights" not in c.layer]
    flights = [c for c in customs if c.layer and "stairflights" in c.layer]
    railings = [c for c in customs if c.layer and "railings" in c.layer]
    members = [c for c in customs if c.layer and "members" in c.layer]

    assert len(stairs) == 2, f"Expected 2 stairs, got {len(stairs)}"
    assert len(flights) == 2, f"Expected 2 stair flights, got {len(flights)}"
    assert len(railings) == 4, f"Expected 4 railings, got {len(railings)}"
    assert len(members) == 4, f"Expected 4 members, got {len(members)}"


def test_duplex_roundtrip_100_percent_retention(tmp_path):
    """Verify 100% element retention rate on Duplex benchmark IFC."""
    fixture_path = Path(__file__).parent / "fixtures" / "Duplex_A_20110907.ifc"
    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    manifest = import_ifc_to_manifest(fixture_path)
    recompiled_path = tmp_path / "duplex_recompiled.ifc"
    compile_to_ifc(manifest, recompiled_path)

    stats = compare_ifc_files(fixture_path, recompiled_path, output_table=False)

    assert stats["original_total"] == 218
    assert stats["recompiled_total"] == 218
    assert stats["retention_rate"] == 100.0

    orig_counts = stats["original_counts"]
    recomp_counts = stats["recompiled_counts"]

    assert recomp_counts["IfcWindow"] == 24
    assert recomp_counts["IfcCovering"] == 13
    assert recomp_counts["IfcRoof"] == 1
    assert recomp_counts["IfcRailing"] == 4
    assert recomp_counts["IfcMember"] == 4
    assert recomp_counts["IfcStair"] == 2
    assert recomp_counts["IfcStairFlight"] == 2
