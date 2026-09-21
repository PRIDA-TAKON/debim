"""
Unit tests for Precision Geometric Extraction (Rotation, Exact Dimensions, True Elevation)
for OpenBIM Models in debim.
"""

from pathlib import Path
import pytest

from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.schema import Dimensions


DUPLEX_A_PATH = Path(__file__).parent / "fixtures" / "Duplex_A_20110907.ifc"


def test_precision_rotation_extraction():
    """Test that furniture and custom elements have non-trivial rotation angles extracted."""
    manifest = import_ifc_to_manifest(DUPLEX_A_PATH)
    furniture_elements = [
        e for e in manifest.elements if getattr(e, "layer", "") == "interior/furniture"
    ]
    assert len(furniture_elements) > 0

    rotations = [e.placement.rotation for e in furniture_elements if e.placement.rotation]
    assert len(rotations) > 0

    # Ensure various rotation angles (e.g. 90, 180 degrees in radians ~ 1.57, 3.14) are extracted
    has_non_zero_rot = any(
        any(abs(angle) > 0.01 for angle in rot) for rot in rotations
    )
    assert has_non_zero_rot, "Expected furniture to have extracted rotation angles"


def test_precision_elevation_correctness():
    """Test elevation correctness: upper level furniture sits at z ~ 3.10m, not double-elevated at 6.20m+."""
    manifest = import_ifc_to_manifest(DUPLEX_A_PATH)
    resolved = resolve_manifest(manifest)

    # Find upper floor furniture (e.g. beds with tag M_Bed-Standard)
    beds = [
        c for c in resolved.custom_elements if "Bed" in c.tag
    ]
    assert len(beds) > 0

    for bed in beds:
        world_z = bed.position[2]
        # Bed on level 2 should be at elevation ~3.10m, NOT double-elevated (6.20m+)
        assert 3.0 <= world_z <= 3.5, f"Expected bed elevation around 3.10m, got {world_z}"


def test_precision_bounding_box_dimensions():
    """Test that exact bounding box dimensions (width, depth, height) are populated on custom elements."""
    manifest = import_ifc_to_manifest(DUPLEX_A_PATH)
    furniture_elements = [
        e for e in manifest.elements if getattr(e, "layer", "") == "interior/furniture"
    ]

    elements_with_dims = [e for e in furniture_elements if e.dimensions is not None]
    assert len(elements_with_dims) > 0

    for elem in elements_with_dims:
        dims = elem.dimensions
        assert isinstance(dims, Dimensions)
        assert dims.width > 0.0
        assert dims.depth is not None and dims.depth > 0.0
        assert dims.height > 0.0
