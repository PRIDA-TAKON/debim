"""
tests.test_resolution_engine

End-to-End Test Suite for debim AI-Driven Construction Engineering & Clash Resolution Engine:
1. Phase 1: Visual Funnel Search (Domain hypothesis, index skimming, title block fingerprinting, ROI drill-down)
2. Phase 2: Scoped .debim Extraction & 3D Clearance Clash Detection
3. Phase 3: Multi-Option Variant Generation (Option A: 45°, Option B: 90°, Option C: Zone Rerouting)
4. Phase 4: Trade-off Audit & Decision Engine (Delta BOQ, Site Stock, Lead Time vs Time-critical / Cost-driven)
5. Phase 5: RFI Commit & Redline Overlay Generation
"""

import json
from pathlib import Path
import pytest
import yaml

from debim.resolution.funnel import VisualFunnelSearcher, ingest_drawing_scans
from debim.resolution.extractor import ScopedExtractor, ClashDetector, extract_scoped_roi
from debim.resolution.variants import VariantGenerator, generate_resolution_variants
from debim.resolution.audit import TradeoffAuditor, audit_resolution_options, commit_resolution_solution
from debim.resolution.redline import generate_redline_overlay


@pytest.fixture
def test_workspace(tmp_path):
    """Sets up synthetic scan directory and workspace for testing."""
    scans_dir = tmp_path / "a0_scans"
    scans_dir.mkdir()

    # Create dummy drawing files
    (scans_dir / "00_DRAWING_INDEX.png").write_bytes(b"dummy index")
    (scans_dir / "S-01_FOUNDATION_PLAN.png").write_bytes(b"dummy structural")
    (scans_dir / "S-02_1F_COLUMN_BEAM_FRAMING.png").write_bytes(b"dummy structural framing")
    (scans_dir / "SN-03_1F_SANITARY_PIPING_LAYOUT.png").write_bytes(b"dummy sanitary mep")
    (scans_dir / "A-05_DOOR_WINDOW_DETAILS.png").write_bytes(b"dummy architectural")

    # Create test inventory stock
    stock_file = tmp_path / "site_stock.json"
    stock_data = {
        "pvc_elbow_45_deg": {"stock_qty": 5, "lead_time_days": 0},
        "pvc_elbow_90_deg": {"stock_qty": 10, "lead_time_days": 0},
        "pvc_pipe_150mm_m": {"stock_qty": 20.0, "lead_time_days": 0},
        "pipe_hanger_clamp": {"stock_qty": 15, "lead_time_days": 0},
    }
    with open(stock_file, "w", encoding="utf-8") as f:
        json.dump(stock_data, f, indent=2)

    return {
        "scans_dir": scans_dir,
        "stock_file": stock_file,
        "work_dir": tmp_path / "workspace",
    }


def test_phase1_visual_funnel_search(test_workspace):
    """Test Visual Funnel filtering and index_map generation."""
    scans_dir = test_workspace["scans_dir"]
    index_map_path = test_workspace["work_dir"] / "index_map.json"

    res = ingest_drawing_scans(
        input_dir=scans_dir,
        problem_type="pipe-column-clash",
        output_path=index_map_path,
        grid_target="B-2",
        floor="1F",
    )

    assert index_map_path.exists()
    assert res["status"] == "FUNNEL_FILTERED"
    assert "S-02" in [s["sheet_code"] for s in res["target_sheets"]]
    assert res["drill_down"]["grid_x"] == "B"
    assert res["drill_down"]["grid_y"] == "2"


def test_phase2_scoped_debim_and_clash_detection(test_workspace):
    """Test scoped declarative manifest extraction and 3D clash verification."""
    scans_dir = test_workspace["scans_dir"]
    work_dir = test_workspace["work_dir"]
    index_map_path = work_dir / "index_map.json"
    base_debim_path = work_dir / "base.debim"

    ingest_drawing_scans(scans_dir, output_path=index_map_path)
    extract_res = extract_scoped_roi(
        index_map_path=index_map_path,
        grid_target="B-2",
        floor="1F",
        output_path=base_debim_path,
    )

    assert base_debim_path.exists()
    clash_check = extract_res["clash_check"]
    assert clash_check["has_clashes"] is True
    assert clash_check["status"] == "CLASH_CONFIRMED"
    assert clash_check["clash_count"] >= 1
    assert clash_check["clashes"][0]["severity"] == "CRITICAL"


def test_phase3_multi_option_variant_generation(test_workspace):
    """Test generating 3 physical rerouting variants with Clash = 0."""
    work_dir = test_workspace["work_dir"]
    scans_dir = test_workspace["scans_dir"]
    index_map_path = work_dir / "index_map.json"
    base_debim_path = work_dir / "base.debim"
    options_dir = work_dir / "options"

    ingest_drawing_scans(scans_dir, output_path=index_map_path)
    extract_scoped_roi(index_map_path=index_map_path, output_path=base_debim_path)

    variants = generate_resolution_variants(
        base_manifest_path=base_debim_path,
        num_variants=3,
        output_dir=options_dir,
    )

    assert len(variants) == 3
    # Check that each option file exists and enforces Clash = 0
    for v in variants:
        opt_file = Path(v["saved_path"])
        assert opt_file.exists()
        assert v["clash_status"] == "CLASH_FREE"
        assert len(v["clashes"]) == 0

    assert (options_dir / "option_a.debim").exists()
    assert (options_dir / "option_b.debim").exists()
    assert (options_dir / "option_c.debim").exists()


def test_phase4_and_5_tradeoff_audit_and_commit(test_workspace):
    """Test trade-off audit matrix, time-critical decision, and redline rendering."""
    work_dir = test_workspace["work_dir"]
    scans_dir = test_workspace["scans_dir"]
    stock_file = test_workspace["stock_file"]
    index_map_path = work_dir / "index_map.json"
    base_debim_path = work_dir / "base.debim"
    options_dir = work_dir / "options"
    matrix_report = work_dir / "tradeoff_matrix.md"
    final_debim = work_dir / "final_resolved.debim"
    redline_png = work_dir / "redline_overlay.png"

    ingest_drawing_scans(scans_dir, output_path=index_map_path)
    extract_scoped_roi(index_map_path=index_map_path, output_path=base_debim_path)
    generate_resolution_variants(base_manifest_path=base_debim_path, output_dir=options_dir)

    # 1. Audit
    audit_res = audit_resolution_options(
        base_manifest_path=base_debim_path,
        options_dir=options_dir,
        inventory_path=stock_file,
        report_path=matrix_report,
    )

    assert matrix_report.exists()
    assert audit_res["options_evaluated"] == 3
    report_text = matrix_report.read_text(encoding="utf-8")
    assert "Option A" in report_text
    assert "Option B" in report_text
    assert "Option C" in report_text

    # 2. Commit solution
    commit_res = commit_resolution_solution(
        matrix_report_path=matrix_report,
        mode="time-critical",
        options_dir=options_dir,
        output_path=final_debim,
    )

    assert final_debim.exists()
    assert commit_res["status"] == "APPROVED_FOR_CONSTRUCTION_RFI"
    assert "option_a" in commit_res["selected_option_file"].lower()

    # 3. Redline overlay
    redline_path = generate_redline_overlay(
        base_manifest_path=base_debim_path,
        resolved_manifest_path=final_debim,
        output_png_path=redline_png,
    )
    assert Path(redline_path).exists()
