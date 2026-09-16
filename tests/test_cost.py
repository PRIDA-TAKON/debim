"""
Unit tests for Cost Estimation Engine (debim.cost).
"""

import pytest
from typer.testing import CliRunner

from debim.cli import app
from debim.cost import estimate_cost, load_price_catalog
from debim.qto import calculate_qto
from debim.schema import load_manifest


runner = CliRunner()


def test_load_price_catalog(sample_prices_path):
    catalog = load_price_catalog(sample_prices_path)
    assert catalog.currency == "THB"
    assert "MAT-CONC-01" in catalog.items
    assert "MAT-AAC-01" in catalog.items
    assert "MAT-REBAR-DB16" in catalog.items
    assert "MAT-FORMWORK" in catalog.items

    item_conc = catalog.items["MAT-CONC-01"]
    assert item_conc.material_cost == 2100.0
    assert item_conc.labor_cost == 450.0


def test_townhouse_cost_estimate(sample_project_path, sample_prices_path):
    manifest = load_manifest(sample_project_path)
    qto = calculate_qto(manifest)
    catalog = load_price_catalog(sample_prices_path)

    estimate = estimate_cost(qto, catalog, manifest)

    assert estimate.currency == "THB"
    assert len(estimate.line_items) == 4

    # Map line items by code
    items_by_code = {item.code: item for item in estimate.line_items}

    # MAT-CONC-01: qty 0.460 m3, mat 966.0, labor 207.0, total 1173.0
    item_conc = items_by_code["MAT-CONC-01"]
    assert item_conc.quantity == pytest.approx(0.460, rel=1e-2)
    assert item_conc.total_material_cost == pytest.approx(966.0, rel=1e-2)
    assert item_conc.total_labor_cost == pytest.approx(207.0, rel=1e-2)
    assert item_conc.total_amount == pytest.approx(1173.0, rel=1e-2)

    # MAT-AAC-01: qty 13.700 m2, mat 3836.0, labor 1644.0, total 5480.0
    item_aac = items_by_code["MAT-AAC-01"]
    assert item_aac.quantity == pytest.approx(13.700, rel=1e-2)
    assert item_aac.total_material_cost == pytest.approx(3836.0, rel=1e-2)
    assert item_aac.total_labor_cost == pytest.approx(1644.0, rel=1e-2)
    assert item_aac.total_amount == pytest.approx(5480.0, rel=1e-2)

    # MAT-FORMWORK: qty 34.200 m2, mat 11970.0, labor 5130.0, total 17100.0
    item_form = items_by_code["MAT-FORMWORK"]
    assert item_form.quantity == pytest.approx(34.200, rel=1e-2)
    assert item_form.total_material_cost == pytest.approx(11970.0, rel=1e-2)
    assert item_form.total_labor_cost == pytest.approx(5130.0, rel=1e-2)
    assert item_form.total_amount == pytest.approx(17100.0, rel=1e-2)

    # MAT-REBAR-DB16: qty 84.738 kg, mat 2330.30, labor 381.32, total 2711.62
    item_rebar = items_by_code["MAT-REBAR-DB16"]
    assert item_rebar.quantity == pytest.approx(84.738, rel=1e-2)
    assert item_rebar.total_material_cost == pytest.approx(2330.30, rel=1e-2)
    assert item_rebar.total_labor_cost == pytest.approx(381.32, rel=1e-2)
    assert item_rebar.total_amount == pytest.approx(2711.62, rel=1e-2)

    # Project totals
    assert estimate.total_material_cost == pytest.approx(19102.30, rel=1e-2)
    assert estimate.total_labor_cost == pytest.approx(7362.32, rel=1e-2)
    assert estimate.grand_total == pytest.approx(26464.62, rel=1e-2)


def test_export_csv(sample_project_path, sample_prices_path, tmp_path):
    manifest = load_manifest(sample_project_path)
    qto = calculate_qto(manifest)
    catalog = load_price_catalog(sample_prices_path)
    estimate = estimate_cost(qto, catalog, manifest)

    out_csv = tmp_path / "boq.csv"
    res_path = estimate.export_csv(out_csv)

    assert res_path.exists()
    content = res_path.read_text(encoding="utf-8")
    assert "Item Code,Description,Unit" in content
    assert "MAT-CONC-01" in content
    assert "MAT-FORMWORK" in content
    assert "TOTAL,Project Grand Total" in content


def test_cli_qto_and_cost_commands(sample_project_path, sample_prices_path, tmp_path):
    # Test `bim qto`
    res_qto = runner.invoke(app, ["qto", "--manifest", str(sample_project_path)])
    assert res_qto.exit_code == 0
    assert "Quantitative Take-Off (QTO) Summary" in res_qto.output
    assert "C-A1" in res_qto.output
    assert "0.460" in res_qto.output

    # Test `bim cost`
    out_csv = tmp_path / "boq.csv"
    res_cost = runner.invoke(
        app,
        [
            "cost",
            "--manifest",
            str(sample_project_path),
            "--prices",
            str(sample_prices_path),
            "--output",
            str(out_csv),
        ],
    )
    assert res_cost.exit_code == 0
    assert "Cost Estimate Summary" in res_cost.output
    assert "Project Budget Summary" in res_cost.output
    assert "19,102.30" in res_cost.output
    assert "Exported BOQ CSV to:" in res_cost.output
    assert out_csv.exists()
