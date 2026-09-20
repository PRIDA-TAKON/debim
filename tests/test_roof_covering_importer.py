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
from debim.schema import (
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
    """Verify that 13 ceiling coverings are extracted."""
    coverings = [e for e in duplex_manifest.elements if isinstance(e, IfcCovering)]
    assert len(coverings) == 13, f"Expected 13 coverings, got {len(coverings)}"

    for cov in coverings:
        assert cov.covering_type == "CEILING"
        assert cov.placement.area is not None and cov.placement.area > 0
        assert cov.thickness > 0


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
