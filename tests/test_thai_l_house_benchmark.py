"""
Integration benchmark test suite for Baan Thai L-Shape benchmark model (examples/thai_l_house/project.debim).
Verifies 220+ elements, schema validation, spatial resolution, IFC4 STEP compilation,
and Thai CGD ว480 QTO/BOQ pricing rules.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.compliance import check_topological_continuity, detect_mep_structural_clashes
from debim.cost import estimate_cost, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import load_manifest


BENCHMARK_MANIFEST = Path("examples/thai_l_house/project.debim")
BENCHMARK_PRICES = Path("examples/thai_l_house/prices.yaml")


def test_thai_l_house_manifest_loading_and_element_count():
    assert BENCHMARK_MANIFEST.exists(), f"Benchmark manifest '{BENCHMARK_MANIFEST}' not found."
    manifest = load_manifest(BENCHMARK_MANIFEST)

    # 1. Verify project identity and schema version
    assert manifest.schema_version == "IFC4-Minimal"
    assert manifest.project.id == "PRJ-THAI-L-HOUSE-2025"

    # 2. Assert element count >= 220 elements
    elem_count = len(manifest.elements)
    assert elem_count >= 220, f"Expected 220+ elements in Baan Thai L-Shape, got {elem_count}."


def test_thai_l_house_spatial_resolution_and_compliance():
    manifest = load_manifest(BENCHMARK_MANIFEST)
    resolved = resolve_manifest(manifest)

    # Verify resolved element collections
    assert len(resolved.footings) == 24
    assert len(resolved.columns) == 48  # 24 stub + 24 FL1
    assert len(resolved.beams) >= 50    # Ground + FL1 + Roof ring beams
    assert len(resolved.walls) >= 20
    assert len(resolved.roofs) >= 1
    assert len(resolved.pipes) >= 6
    assert len(resolved.light_fixtures) >= 10

    # Verify 0 topological continuity errors or warnings
    topo_warnings = check_topological_continuity(resolved)
    assert len(topo_warnings) == 0, f"Expected 0 topological continuity warnings, got: {topo_warnings}"

    # Verify 0 MEP structural AABB clashes
    mep_clashes = detect_mep_structural_clashes(resolved)
    assert len(mep_clashes) == 0, f"Expected 0 MEP structural clashes, got: {mep_clashes}"


def test_thai_l_house_qto_and_cgd_v480_boq_estimation():
    assert BENCHMARK_PRICES.exists(), f"Benchmark price catalog '{BENCHMARK_PRICES}' not found."
    manifest = load_manifest(BENCHMARK_MANIFEST)

    # 1. Calculate QTO
    project_qto = calculate_qto(manifest)
    assert project_qto.total_concrete_volume > 40.0
    assert project_qto.total_roof_covering_area > 200.0
    assert project_qto.total_roof_steel_weight > 4000.0

    # 2. Load Price Catalog & Estimate Cost
    catalog = load_price_catalog(BENCHMARK_PRICES)
    estimate = estimate_cost(project_qto, catalog, manifest)

    assert estimate.grand_total > 500000.0  # THB direct cost > 500,000

    # 3. Test Thai CGD ว480 PR.5 Factor F sheet generation
    pr5 = estimate.generate_pr5(project_name=manifest.project.name)
    assert pr5.direct_cost == estimate.grand_total
    assert 1.25 <= pr5.factor_f <= 1.35  # Official Factor F bracket (~1.3062)
    assert pr5.total_construction_cost > pr5.direct_cost


def test_thai_l_house_ifc4_compilation(tmp_path: Path):
    out_ifc = tmp_path / "thai_l_house_test.ifc"
    compiled_path = compile_to_ifc(BENCHMARK_MANIFEST, out_ifc)

    assert compiled_path.exists()
    assert compiled_path.stat().st_size > 100000  # > 100 KB valid STEP model file

    content = compiled_path.read_text(encoding="utf-8")
    assert "IFCCOLUMN" in content
    assert "IFCFOOTING" in content
    assert "IFCBEAM" in content
    assert "IFCROOF" in content
    assert "IFCPIPE-SEGMENT" in content or "IFCPIPESEGMENT" in content
