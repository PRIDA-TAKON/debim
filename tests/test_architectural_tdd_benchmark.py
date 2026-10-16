"""
Integration benchmark test suite for Baan TDD Residential Benchmark House (examples/architectural_tdd_house/).
Verifies 250+ elements, schema validation, spatial resolution, IFC4 STEP compilation,
and architectural compliance unit test assertions.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.compliance import check_topological_continuity, detect_mep_structural_clashes
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.derive import derive_project_from_spaces
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import load_manifest


FLOORPLAN_MANIFEST = Path("examples/architectural_tdd_house/floorplan.debim")
PROJECT_MANIFEST = Path("examples/architectural_tdd_house/project.debim")


def test_architectural_tdd_house_derivation_and_element_count():
    assert FLOORPLAN_MANIFEST.exists(), f"Floorplan manifest '{FLOORPLAN_MANIFEST}' not found."

    manifest = derive_project_from_spaces(FLOORPLAN_MANIFEST)
    resolved = resolve_manifest(manifest)

    # 1. Total elements count (including resolved wall child doors/windows) >= 250 elements
    total_elements_count = len(resolved.elements)
    assert total_elements_count >= 250, f"Expected 250+ elements in TDD Residential Benchmark, got {total_elements_count}."


def test_architectural_tdd_house_spatial_resolution_and_compliance():
    manifest = load_manifest(PROJECT_MANIFEST)
    resolved = resolve_manifest(manifest)

    # 1. Topological continuity check (0 floating columns or unsupported beams)
    topo_warnings = check_topological_continuity(resolved)
    assert len(topo_warnings) == 0, f"Expected 0 topological continuity warnings, got: {topo_warnings}"

    # 2. MEP vs structural clash detection
    mep_clashes = detect_mep_structural_clashes(resolved)
    assert len(mep_clashes) == 0, f"Expected 0 MEP clashes, got: {mep_clashes}"

    # 3. Architectural Design Assertions
    bathrooms = [s for s in resolved.spaces if "BATH" in s.tag or "TOILET" in s.tag]
    for b in bathrooms:
        assert b.drop_elevation <= -0.10, f"Bathroom {b.tag} must have a floor drop elevation <= -0.10m"

    for s in resolved.spaces:
        assert s.net_floor_area >= 4.0, f"Space {s.tag} area must be at least 4.0 sq.m."
        assert s.height >= 2.60, f"Space {s.tag} clear height must be at least 2.60m"


def test_architectural_tdd_house_qto_and_ifc4_compilation(tmp_path: Path):
    manifest = load_manifest(PROJECT_MANIFEST)
    resolved = resolve_manifest(manifest)

    # 1. Calculate QTO
    project_qto = calculate_qto(resolved)
    assert project_qto.total_concrete_volume > 15.0
    assert project_qto.total_formwork_area > 50.0

    # 2. Compile to IFC4 STEP
    out_ifc = tmp_path / "architectural_tdd_house_test.ifc"
    compiled_path = compile_to_ifc(PROJECT_MANIFEST, out_ifc)

    assert compiled_path.exists()
    assert compiled_path.stat().st_size > 50000  # Valid STEP model file > 50 KB

    content = compiled_path.read_text(encoding="utf-8")
    assert "IFCCOLUMN" in content
    assert "IFCFOOTING" in content
    assert "IFCBEAM" in content
    assert "IFCWALL" in content
    assert "IFCDOOR" in content
    assert "IFCWINDOW" in content
    assert "IFCSLAB" in content
