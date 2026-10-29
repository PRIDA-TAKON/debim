"""
Unit tests for CI Diff Reporter and GitHub PR Bot module (debim.ci).
"""

import copy
from pathlib import Path
import yaml
from cli_runner import CliRunner

from debim.ci import (
    ComplianceSummary,
    CostDiffResult,
    compare_manifest_costs,
    generate_pr_markdown_report,
    run_pr_compliance_check,
)
from debim.cli import app

runner = CliRunner()


def test_compare_manifest_costs(tmp_path: Path):
    base_file = Path("tests/fixtures/townhouse/project.yaml")
    prices_file = Path("tests/fixtures/townhouse/prices.json")

    # Read base manifest and create modified head manifest with added columns/beams
    with open(base_file, "r", encoding="utf-8") as f:
        base_data = yaml.safe_load(f)

    head_data = copy.deepcopy(base_data)
    head_data["elements"].append({
        "class": "IfcColumn",
        "tag": "C_EXTRA",
        "material": "CONC_240",
        "profile": {"shape": "BOX", "width": 0.40, "depth": 0.40},
        "placement": {"grid": ["A", "1"], "base_storey": "L1", "top_storey": "L2"},
    })

    head_file = tmp_path / "head_project.yaml"
    head_file.write_text(yaml.dump(head_data), encoding="utf-8")

    diff_res = compare_manifest_costs(
        base_manifest_path=base_file,
        head_manifest_path=head_file,
        rules="cg-v480",
        price_catalog_path=prices_file,
    )

    assert isinstance(diff_res, CostDiffResult)
    assert diff_res.head_concrete_m3 > diff_res.base_concrete_m3
    assert diff_res.delta_concrete_m3 > 0
    assert diff_res.pct_concrete > 0
    assert diff_res.head_cost > diff_res.base_cost
    assert diff_res.delta_cost > 0
    assert len(diff_res.detailed_items_diff) > 0


def test_run_pr_compliance_check():
    head_file = Path("examples/farnsworth_house/project.debim")
    comp_res = run_pr_compliance_check(head_file, jurisdiction="th")

    assert isinstance(comp_res, ComplianceSummary)
    assert comp_res.status in ("PASS", "WARNING", "FAIL")
    assert comp_res.total_checks > 0
    assert len(comp_res.layer_results) == 5


def test_generate_pr_markdown_report():
    cost_diff = CostDiffResult(
        base_concrete_m3=100.0,
        head_concrete_m3=103.5,
        delta_concrete_m3=3.5,
        pct_concrete=3.5,
        base_rebar_kg=8000.0,
        head_rebar_kg=8280.0,
        delta_rebar_kg=280.0,
        pct_rebar=3.5,
        base_formwork_m2=500.0,
        head_formwork_m2=494.0,
        delta_formwork_m2=-6.0,
        pct_formwork=-1.2,
        base_cost=1000000.0,
        head_cost=1045000.0,
        delta_cost=45000.0,
        pct_cost=4.5,
        currency="THB",
        detailed_items_diff=[
            {
                "code": "CONC_240",
                "name": "Concrete 240 ksc",
                "unit": "m3",
                "base_qty": 100.0,
                "head_qty": 103.5,
                "delta_qty": 3.5,
                "base_amount": 240000.0,
                "head_amount": 248400.0,
                "delta_amount": 8400.0,
            }
        ],
    )

    compliance = ComplianceSummary(
        status="PASS",
        total_checks=25,
        total_violations=0,
        errors_count=0,
        warnings_count=0,
        layer_results={
            1: {"name": "Spatial & Functional", "passed": True, "checks_count": 5, "violations_count": 0},
            2: {"name": "Legal & Life Safety", "passed": True, "checks_count": 5, "violations_count": 0},
            3: {"name": "Structural Integrity", "passed": True, "checks_count": 5, "violations_count": 0},
            4: {"name": "MEP Continuity & Gravity", "passed": True, "checks_count": 5, "violations_count": 0},
            5: {"name": "Constructability & Clashes", "passed": True, "checks_count": 5, "violations_count": 0},
        },
    )

    md = generate_pr_markdown_report(cost_diff, compliance)

    assert "Building-as-Code CI Audit & Cost Diff Report" in md
    assert "Building_Compliance-PASS" in md
    assert "+3.5%" in md
    assert "+45,000" in md
    assert "Concrete Volume" in md
    assert "CONC_240" in md


def test_cli_ci_report_command(tmp_path: Path):
    base_file = Path("tests/fixtures/townhouse/project.yaml")
    out_md = tmp_path / "pr_comment.md"

    res = runner.invoke(app, [
        "ci", "report",
        "--base", str(base_file),
        "--head", str(base_file),
        "-o", str(out_md),
    ])

    assert res.exit_code == 0
    assert out_md.exists()
    content = out_md.read_text(encoding="utf-8")
    assert "Building-as-Code CI Audit & Cost Diff Report" in content
    assert "Concrete Volume" in content
