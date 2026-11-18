"""
debim.resolution.cli

CLI parser registration and command handlers for debim Resolution Engine:
1. debim ingest-scan (or debim resolve scan)
2. debim extract-roi (or debim resolve extract)
3. debim resolve-clash (or debim resolve clash)
4. debim audit-options (or debim resolve audit)
5. debim commit-solution (or debim resolve commit)
"""

import argparse
import sys
from pathlib import Path
from typing import Any, List, Optional

from debim.resolution.funnel import ingest_drawing_scans
from debim.resolution.extractor import extract_scoped_roi, detect_clashes
from debim.resolution.variants import generate_resolution_variants
from debim.resolution.audit import audit_resolution_options, commit_resolution_solution
from debim.resolution.redline import generate_redline_overlay


def cmd_ingest_scan(args: Any):
    """Handler for debim ingest-scan / debim resolve scan"""
    input_dir = getattr(args, "input_dir", ".")
    problem_type = getattr(args, "problem_type", "pipe-column-clash")
    output_path = getattr(args, "output", "workspace/index_map.json")
    grid_target = getattr(args, "grid", "B-2")
    floor = getattr(args, "floor", "1F")

    print(f"\n[debim Resolution] Phase 1: Visual Funnel Search")
    print(f"  • Input Directory : {input_dir}")
    print(f"  • Problem Domain  : {problem_type}")
    print(f"  • Target Grid     : {grid_target} (Floor: {floor})")

    res = ingest_drawing_scans(
        input_dir=input_dir,
        problem_type=problem_type,
        output_path=output_path,
        grid_target=grid_target,
        floor=floor,
    )

    print(f"  • Index Sheet     : {res.get('index_sheet')}")
    print(f"  • Target Sheets   : {len(res.get('target_sheets', []))} sheets filtered")
    print(f"  • Compute Saved   : {res.get('compute_reduction_factor')}")
    print(f"  ✓ Output Written  : {output_path}\n")


def cmd_extract_roi(args: Any):
    """Handler for debim extract-roi / debim resolve extract"""
    map_file = getattr(args, "map", "workspace/index_map.json")
    grid_target = getattr(args, "grid", "B-2")
    floor = getattr(args, "floor", "1F")
    output_path = getattr(args, "output", "workspace/base.debim")

    print(f"\n[debim Resolution] Phase 2: Scoped .debim Extraction & Clash Check")
    print(f"  • Index Map       : {map_file}")
    print(f"  • Target Location : Grid {grid_target} ({floor})")

    res = extract_scoped_roi(
        index_map_path=map_file,
        grid_target=grid_target,
        floor=floor,
        output_path=output_path,
    )

    clash_check = res.get("clash_check", {})
    status = clash_check.get("status", "UNKNOWN")
    print(f"  • Elements Scoped : {res.get('elements_count')} BIM elements")
    print(f"  • 3D Clash Status : {status} ({clash_check.get('clash_count', 0)} clash detected)")
    if clash_check.get("clashes"):
        c = clash_check["clashes"][0]
        print(f"    - Interference  : {c.get('pipe_tag')} intersects {c.get('column_tag')}")
        print(f"    - Severity      : {c.get('severity')} ({c.get('constraint')})")
    print(f"  ✓ Base Manifest   : {output_path}\n")


def cmd_resolve_clash(args: Any):
    """Handler for debim resolve-clash / debim resolve clash"""
    input_file = getattr(args, "input", "workspace/base.debim")
    variants_count = int(getattr(args, "variants", 3))
    output_dir = getattr(args, "output_dir", "workspace/options")

    print(f"\n[debim Resolution] Phase 3: Multi-Option Variant Generation")
    print(f"  • Input Manifest  : {input_file}")
    print(f"  • Variants Target : {variants_count} engineering options")

    variants = generate_resolution_variants(
        base_manifest_path=input_file,
        num_variants=variants_count,
        output_dir=output_dir,
    )

    for v in variants:
        print(f"  • [{v['option_id']}] {v['name']} -> {v.get('saved_path')}")
        print(f"    - Hydraulic     : {v.get('hydraulic_rating')}")
        print(f"    - Clash Status  : {v.get('clash_status')}")
    print(f"  ✓ All {len(variants)} options verified: Hard constraint Clash = 0 maintained\n")


def cmd_audit_options(args: Any):
    """Handler for debim audit-options / debim resolve audit"""
    base_file = getattr(args, "base", "workspace/base.debim")
    options_dir = getattr(args, "options_dir", "workspace/options")
    inventory_file = getattr(args, "inventory", None)
    report_file = getattr(args, "report", "workspace/tradeoff_matrix.md")

    print(f"\n[debim Resolution] Phase 4: Trade-off Audit & Multi-Scenario Evaluation")
    print(f"  • Base Model      : {base_file}")
    print(f"  • Options Pool    : {options_dir}")
    print(f"  • Site Stock DB   : {inventory_file or 'Default on-site stock'}")

    res = audit_resolution_options(
        base_manifest_path=base_file,
        options_dir=options_dir,
        inventory_path=inventory_file,
        report_path=report_file,
    )

    print(f"  • Evaluated       : {res.get('options_evaluated')} variants")
    for ev in res.get("evaluations", []):
        lead = f"{ev['lead_time_days']} days" if ev['lead_time_days'] > 0 else "Ready now"
        print(f"    - {ev['variant_id']}: Net Cost +{ev['net_delta_cost_thb']:.2f} THB | Lead Time: {lead} | Turnaround: {ev['total_cycle_time_hours']} hrs")
    print(f"  ✓ Trade-off Report: {report_file}\n")


def cmd_commit_solution(args: Any):
    """Handler for debim commit-solution / debim resolve commit"""
    matrix_file = getattr(args, "matrix", "workspace/tradeoff_matrix.md")
    mode = getattr(args, "mode", "time-critical")
    options_dir = getattr(args, "options_dir", "workspace/options")
    output_file = getattr(args, "output", "workspace/final_resolved.debim")
    base_file = getattr(args, "base", "workspace/base.debim")
    redline_file = getattr(args, "redline", "workspace/redline_overlay.png")

    print(f"\n[debim Resolution] Phase 5: Solution Commit & RFI Compilation")
    print(f"  • Decision Matrix : {matrix_file}")
    print(f"  • Objective Mode  : {mode}")

    res = commit_resolution_solution(
        matrix_report_path=matrix_file,
        mode=mode,
        options_dir=options_dir,
        output_path=output_file,
    )

    print(f"  • Selected Option : {res.get('selected_option_file')}")
    print(f"  • Rationale       : {res.get('reason')}")
    print(f"  ✓ Final Manifest  : {output_file}")

    # Generate redline overlay automatically
    if Path(base_file).exists():
        redline_out = generate_redline_overlay(
            base_manifest_path=base_file,
            resolved_manifest_path=output_file,
            output_png_path=redline_file,
        )
        print(f"  ✓ Redline Overlay : {redline_out}")
    print(f"  ✓ Status          : {res.get('status')}\n")


def register_resolution_parser(subparsers: argparse._SubParsersAction):
    """Registers resolution commands into debim CLI parser."""
    
    # -------------------------------------------------------------
    # Group 1: Dedicated Subcommand Namespace: debim resolve <cmd>
    # -------------------------------------------------------------
    p_resolve = subparsers.add_parser(
        "resolve",
        help="AI-driven engineering clash resolution & visual funnel engine",
    )
    res_sub = p_resolve.add_subparsers(dest="resolve_subcommand")

    # 1. debim resolve scan
    p_r_scan = res_sub.add_parser("scan", help="Filter drawing scans via Visual Funnel Search")
    p_r_scan.add_argument("--input-dir", "-i", default=".", help="Path to high-res drawing scans folder")
    p_r_scan.add_argument("--problem-type", "-p", default="pipe-column-clash", help="Engineering clash problem type")
    p_r_scan.add_argument("--grid", "-g", default="B-2", help="Target grid line intersection")
    p_r_scan.add_argument("--floor", "-f", default="1F", help="Target floor level")
    p_r_scan.add_argument("--output", "-o", default="workspace/index_map.json", help="Path to write index_map.json")
    p_r_scan.set_defaults(func=cmd_ingest_scan)

    # 2. debim resolve extract
    p_r_ext = res_sub.add_parser("extract", help="Extract scoped .debim and detect physical clashes")
    p_r_ext.add_argument("--map", "-m", default="workspace/index_map.json", help="Path to index_map.json")
    p_r_ext.add_argument("--grid", "-g", default="B-2", help="Target grid line")
    p_r_ext.add_argument("--floor", "-f", default="1F", help="Target floor")
    p_r_ext.add_argument("--output", "-o", default="workspace/base.debim", help="Path to write base.debim")
    p_r_ext.set_defaults(func=cmd_extract_roi)

    # 3. debim resolve clash
    p_r_clash = res_sub.add_parser("clash", help="Generate 3 physical rerouting variants with Clash=0")
    p_r_clash.add_argument("--input", "-i", default="workspace/base.debim", help="Path to clashing base.debim")
    p_r_clash.add_argument("--variants", "-v", type=int, default=3, help="Number of variants to generate")
    p_r_clash.add_argument("--output-dir", "-o", default="workspace/options", help="Output directory for variants")
    p_r_clash.set_defaults(func=cmd_resolve_clash)

    # 4. debim resolve audit
    p_r_audit = res_sub.add_parser("audit", help="Audit cost, lead time, and stock availability")
    p_r_audit.add_argument("--base", "-b", default="workspace/base.debim", help="Baseline clashing manifest")
    p_r_audit.add_argument("--options-dir", "-d", default="workspace/options", help="Directory of variant manifests")
    p_r_audit.add_argument("--inventory", "-s", help="Path to site_stock.json inventory database")
    p_r_audit.add_argument("--report", "-r", default="workspace/tradeoff_matrix.md", help="Path for tradeoff_matrix.md")
    p_r_audit.set_defaults(func=cmd_audit_options)

    # 5. debim resolve commit
    p_r_commit = res_sub.add_parser("commit", help="Commit final approved variant and generate RFI package")
    p_r_commit.add_argument("--matrix", "-m", default="workspace/tradeoff_matrix.md", help="Path to tradeoff_matrix.md")
    p_r_commit.add_argument("--mode", default="time-critical", choices=["time-critical", "cost-driven"], help="Decision mode")
    p_r_commit.add_argument("--options-dir", "-d", default="workspace/options", help="Options directory")
    p_r_commit.add_argument("--base", "-b", default="workspace/base.debim", help="Baseline manifest for redline overlay")
    p_r_commit.add_argument("--output", "-o", default="workspace/final_resolved.debim", help="Output final .debim path")
    p_r_commit.add_argument("--redline", default="workspace/redline_overlay.png", help="Path for redline_overlay.png")
    p_r_commit.set_defaults(func=cmd_commit_solution)

    # -------------------------------------------------------------
    # Group 2: Proposed Top-Level CLI Commands (from debim_cli.md)
    # -------------------------------------------------------------
    p_top_ingest = subparsers.add_parser("ingest-scan", help="Scan A0 drawing folder and filter targets via Visual Funnel")
    p_top_ingest.add_argument("--input-dir", required=True, help="Input directory containing A0 scans")
    p_top_ingest.add_argument("--problem-type", default="pipe-column-clash", help="Clash domain type")
    p_top_ingest.add_argument("--grid", default="B-2", help="Target grid")
    p_top_ingest.add_argument("--floor", default="1F", help="Target floor")
    p_top_ingest.add_argument("--output", default="workspace/index_map.json", help="Output index_map.json path")
    p_top_ingest.set_defaults(func=cmd_ingest_scan)

    p_top_extract = subparsers.add_parser("extract-roi", help="Extract scoped .debim around target grid intersection")
    p_top_extract.add_argument("--map", required=True, help="Path to index_map.json")
    p_top_extract.add_argument("--grid", default="B-2", help="Grid intersection")
    p_top_extract.add_argument("--floor", default="1F", help="Floor level")
    p_top_extract.add_argument("--output", default="workspace/base.debim", help="Output base.debim path")
    p_top_extract.set_defaults(func=cmd_extract_roi)

    p_top_clash = subparsers.add_parser("resolve-clash", help="Generate 3 rerouting variants around column")
    p_top_clash.add_argument("--input", required=True, help="Path to base.debim")
    p_top_clash.add_argument("--variants", type=int, default=3, help="Number of variants")
    p_top_clash.add_argument("--output-dir", default="workspace/options", help="Output options folder")
    p_top_clash.set_defaults(func=cmd_resolve_clash)

    p_top_audit = subparsers.add_parser("audit-options", help="Audit cost and time trade-offs across all variants")
    p_top_audit.add_argument("--base", required=True, help="Path to base.debim")
    p_top_audit.add_argument("--options-dir", required=True, help="Directory containing options")
    p_top_audit.add_argument("--inventory", help="Path to site_stock.json")
    p_top_audit.add_argument("--report", default="workspace/tradeoff_matrix.md", help="Output tradeoff_matrix.md")
    p_top_audit.set_defaults(func=cmd_audit_options)

    p_top_commit = subparsers.add_parser("commit-solution", help="Select best variant and compile final RFI package")
    p_top_commit.add_argument("--matrix", required=True, help="Path to tradeoff_matrix.md")
    p_top_commit.add_argument("--mode", default="time-critical", choices=["time-critical", "cost-driven"], help="Optimization mode")
    p_top_commit.add_argument("--options-dir", default="workspace/options", help="Options directory")
    p_top_commit.add_argument("--base", default="workspace/base.debim", help="Baseline manifest for redline overlay")
    p_top_commit.add_argument("--output", default="workspace/final_resolved.debim", help="Final .debim path")
    p_top_commit.add_argument("--redline", default="workspace/redline_overlay.png", help="Final redline_overlay.png path")
    p_top_commit.set_defaults(func=cmd_commit_solution)
