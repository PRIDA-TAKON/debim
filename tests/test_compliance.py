"""
Automated Building Law & Code Compliance Test Suite for debim.
Tests real-world building regulations, feasibility limits, setback rules, and spatial clash checks.
"""

import pytest
from pathlib import Path

from debim.compliance import (
    ComplianceChecker,
    calculate_clear_height,
    calculate_setback,
    calculate_total_floor_area,
    detect_clashes,
)
from debim.schema import load_manifest


@pytest.fixture
def project_manifest(sample_project_path: Path):
    return load_manifest(sample_project_path)


@pytest.fixture
def compliance_checker(project_manifest):
    return ComplianceChecker(project_manifest)


def test_minimum_clear_ceiling_height(compliance_checker):
    """
    Thai Building Code Ministerial Regulation No. 55:
    Assert that clear height on every storey is >= 2.40m.
    """
    manifest = compliance_checker.manifest
    for storey in manifest.spatial_structure.storeys:
        clear_height = compliance_checker.calculate_clear_height(storey.id)
        assert (
            clear_height >= 2.40
        ), f"Storey '{storey.name}' ({storey.id}) clear height {clear_height:.2f}m is below minimum 2.40m rule."


def test_total_floor_area_limit(compliance_checker):
    """
    Assert that total building area does not exceed project feasibility limits (e.g. <= 4000.0 m²).
    """
    total_area = compliance_checker.calculate_total_floor_area()
    max_area_limit = 4000.0
    assert (
        total_area <= max_area_limit
    ), f"Total floor area {total_area:.2f} m² exceeds feasibility limit of {max_area_limit:.2f} m²."


def test_setback_with_openings(compliance_checker):
    """
    Ministerial Regulation No. 55:
    Assert that any exterior wall with openings (doors/windows) maintains at least 2.00m setback from property lines.
    """
    resolved = compliance_checker.resolved
    for wall in resolved.walls:
        if wall.children:  # Has doors/windows openings
            dist = compliance_checker.calculate_setback(wall)
            assert (
                dist >= 2.00
            ), f"Wall '{wall.tag}' has openings but setback distance is only {dist:.2f}m (minimum required: 2.00m)."


def test_zero_spatial_clash(compliance_checker):
    """
    Assert zero critical clashes between non-hosted structural elements.
    """
    clashes = compliance_checker.detect_clashes()
    assert (
        len(clashes) == 0
    ), f"Found {len(clashes)} unintended structural clashes: {clashes}"
