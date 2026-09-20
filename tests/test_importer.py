"""
Unit tests for IFC Importer.
Tests importing IFC files into declarative ProjectManifest, verifying element extraction,
grid generation, and QTO readiness.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto


def test_import_ifc_roundtrip(tmp_path):
    manifest_path = Path("examples/townhouse/project.yaml")
    ifc_path = tmp_path / "test_model.ifc"

    # Compile townhouse to IFC first
    compile_to_ifc(manifest_path, ifc_path)
    assert ifc_path.exists()

    # Import back to ProjectManifest
    manifest = import_ifc_to_manifest(ifc_path)
    assert manifest is not None
    assert len(manifest.elements) > 0

    # Ensure storeys, grids, materials are present
    assert len(manifest.spatial_structure.storeys) > 0
    assert len(manifest.grids.axes_x) > 0
    assert len(manifest.grids.axes_y) > 0
    assert len(manifest.materials) > 0

    # Verify spatial resolution and QTO calculation on imported manifest
    resolved = resolve_manifest(manifest)
    assert len(resolved.elements) > 0

    qto = calculate_qto(resolved)
    assert qto.total_concrete_volume >= 0.0
    assert qto.total_formwork_area >= 0.0
