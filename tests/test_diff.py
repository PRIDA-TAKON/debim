"""
Unit tests for new CLI commands: export, summary, info, and diff
"""

import subprocess
import yaml
from pathlib import Path
from typer.testing import CliRunner
from debim.cli import app

runner = CliRunner()


def test_view_export(tmp_path: Path):
    sample_manifest = Path("examples/townhouse/project.yaml")
    export_path = tmp_path / "dist" / "viewer.html"

    result = runner.invoke(app, ["view", "-m", str(sample_manifest), "--export", str(export_path)])
    assert result.exit_code == 0
    assert export_path.exists()
    assert export_path.stat().st_size > 0
    content = export_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Townhouse-Feasibility" in content


def test_summary_and_info():
    sample_manifest = Path("examples/townhouse/project.yaml")
    prices_path = Path("examples/townhouse/prices.json")

    res_summary = runner.invoke(app, ["summary", "-m", str(sample_manifest), "-p", str(prices_path)])
    assert res_summary.exit_code == 0
    assert "Townhouse-Feasibility" in res_summary.output
    assert "Site Bounds" in res_summary.output
    assert "Element Statistics Breakdown" in res_summary.output
    assert "QTO & Cost Snapshot" in res_summary.output

    # Test 'info' alias
    res_info = runner.invoke(app, ["info", "-m", str(sample_manifest), "-p", str(prices_path)])
    assert res_info.exit_code == 0
    assert "Townhouse-Feasibility" in res_info.output


def test_diff_files(tmp_path: Path):
    manifest_a_path = Path("examples/townhouse/project.yaml")
    prices_path = Path("examples/townhouse/prices.json")

    # Read manifest_a and create modified manifest_b
    with open(manifest_a_path, "r", encoding="utf-8") as f:
        data_a = yaml.safe_load(f)

    data_b = yaml.safe_load(yaml.dump(data_a))
    # Modify an element and add a new element
    data_b["elements"][0]["profile"]["width"] = 0.50  # modify C1
    data_b["elements"].append({
        "class": "IfcColumn",
        "tag": "C_NEW",
        "material": "CONC_240",
        "profile": {"shape": "BOX", "width": 0.30, "depth": 0.30},
        "placement": {"grid": ["A", "1"], "base_storey": "L1", "top_storey": "L2"}
    })

    file_a = tmp_path / "revA.yaml"
    file_b = tmp_path / "revB.yaml"
    file_a.write_text(yaml.dump(data_a), encoding="utf-8")
    file_b.write_text(yaml.dump(data_b), encoding="utf-8")

    res = runner.invoke(app, ["diff", str(file_a), str(file_b), "-p", str(prices_path)])
    assert res.exit_code == 0
    assert "Comparing BIM Revisions:" in res.output
    assert "C_NEW" in res.output
    assert "+ Added" in res.output
    assert "~ Modified" in res.output
    assert "Quantity Take-Off (QTO) Deltas" in res.output
    assert "Cost Variance Breakdown" in res.output


def test_diff_git_revision():
    # Use HEAD~0 (or HEAD) vs HEAD on git repo
    prices_path = Path("examples/townhouse/prices.json")
    res = runner.invoke(app, ["diff", "HEAD:examples/townhouse/project.yaml", "examples/townhouse/project.yaml", "-p", str(prices_path)])
    assert res.exit_code == 0
    assert "Comparing BIM Revisions:" in res.output
    assert "Diff Summary" in res.output
