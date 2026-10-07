"""
Tests for benchmarks/benchmark_scalability.py.
Verifies generator and benchmark runner execution on small synthetic models.
"""

from pathlib import Path
import tempfile

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.benchmark_scalability import (
    estimate_token_count,
    generate_synthetic_project,
    run_scalability_benchmark,
)
from debim.schema import load_manifest


def test_synthetic_project_generation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        num_elems = 150

        paths = generate_synthetic_project(num_elems, base_dir)

        assert paths["project_yaml"].exists()
        assert paths["monolithic_yaml"].exists()
        assert paths["first_storey_file"].exists()

        manifest = load_manifest(paths["project_yaml"])
        assert manifest.project.id == f"BENCH-{num_elems}"
        assert len(manifest.elements) == num_elems
        assert len(manifest.spatial_structure.storeys) >= 1


def test_token_count_estimation():
    sample_text = "a" * 350
    tokens = estimate_token_count(sample_text)
    assert tokens == 100


def test_run_scalability_benchmark():
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        scales = [50, 100]

        results = run_scalability_benchmark(scales=scales, cache_dir=base_dir)

        assert len(results) == 2
        for r in results:
            assert "scale" in r
            assert r["scale"] in scales
            assert r["load_parse_ms"] > 0
            assert r["spatial_resolution_ms"] >= 0
            assert r["qto_calc_ms"] >= 0
            assert r["ifc_compile_ms"] >= 0
            assert r["peak_memory_mb"] > 0
            assert r["monolithic_tokens"] > 0
            assert r["surgical_tokens"] > 0
            assert r["token_savings_pct"] > 90.0
