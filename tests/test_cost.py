"""
Unit tests for Cost Estimation Engine (debim.cost).
"""

import json
from pathlib import Path
import yaml
import pytest
from typer.testing import CliRunner

from debim.cli import app
from debim.cost import (
    PriceCatalog,
    PriceItem,
    PriceItemStandards,
    estimate_cost,
    generate_cost_template,
    load_price_catalog,
)
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


def test_price_item_standards_and_backward_compatibility():
    # Test PriceItem creation with standards
    standards = PriceItemStandards(masterformat="03 31 00", uniformat="B1010", unspsc="30111500")
    item = PriceItem(
        name="Concrete 240 ksc",
        unit="m3",
        material_cost=2100.0,
        labor_cost=450.0,
        standards=standards,
    )
    assert item.standards.masterformat == "03 31 00"
    assert item.standards.uniformat == "B1010"
    assert item.standards.unspsc == "30111500"

    # Test legacy backward compatibility without standards and default costs
    item_legacy = PriceItem(name="Sample Item", unit="m2")
    assert item_legacy.material_cost == 0.0
    assert item_legacy.labor_cost == 0.0
    assert item_legacy.standards is None


def test_modular_yaml_catalog_loading(tmp_path):
    prices_dir = tmp_path / "prices"
    modules_dir = prices_dir / "modules"
    modules_dir.mkdir(parents=True)

    # Sub-module 1: Concrete & Masonry
    mod1_content = {
        "items": {
            "MAT-CONC-01": {
                "name": "Concrete 240 ksc",
                "unit": "m3",
                "material_cost": 2100.0,
                "labor_cost": 450.0,
                "standards": {"masterformat": "03 31 00", "uniformat": "B1010"},
            }
        }
    }
    with open(modules_dir / "structure.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(mod1_content, f)

    # Sub-module 2: Architecture
    mod2_content = {
        "items": {
            "MAT-AAC-01": {
                "name": "AAC Block 7.5cm",
                "unit": "m2",
                "material_cost": 280.0,
                "labor_cost": 120.0,
                "standards": {"masterformat": "04 22 00", "uniformat": "C1010"},
            }
        }
    }
    with open(modules_dir / "architecture.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(mod2_content, f)

    # Master catalog
    master_content = {
        "currency": "THB",
        "includes": ["modules/*.yaml"],
        "items": {
            "MAT-FORMWORK": {
                "name": "Timber Formwork",
                "unit": "m2",
                "material_cost": 350.0,
                "labor_cost": 150.0,
            }
        },
    }
    master_file = prices_dir / "catalog.yaml"
    with open(master_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(master_content, f)

    catalog = load_price_catalog(master_file)
    assert catalog.currency == "THB"
    assert "MAT-CONC-01" in catalog.items
    assert "MAT-AAC-01" in catalog.items
    assert "MAT-FORMWORK" in catalog.items
    assert catalog.items["MAT-CONC-01"].standards.masterformat == "03 31 00"


def test_generate_cost_template_single_file(sample_project_path, tmp_path):
    out_yaml = tmp_path / "prices.template.yaml"
    res_path = generate_cost_template(sample_project_path, output_path=out_yaml, format="yaml", modular=False)

    assert res_path.exists()
    catalog = load_price_catalog(res_path)
    assert catalog.currency == "THB"

    # Verify active items from townhouse manifest & QTO
    assert "MAT-CONC-01" in catalog.items
    assert "MAT-AAC-01" in catalog.items
    assert "MAT-FORMWORK" in catalog.items
    assert "MAT-REBAR-DB16" in catalog.items

    item_conc = catalog.items["MAT-CONC-01"]
    assert item_conc.material_cost == 0.0
    assert item_conc.labor_cost == 0.0
    assert item_conc.unit == "m3"
    assert item_conc.standards is not None
    assert item_conc.standards.masterformat == "03 30 00"


def test_footing_piles_cost_template_and_estimate():
    from debim.qto import calculate_qto
    from debim.cost import generate_cost_template, estimate_cost, PriceCatalog, PriceItem
    from debim.schema import (
        ProjectManifest,
        ProjectInfo,
        SpatialStructure,
        Storey,
        Grids,
        Material,
        IfcFooting,
        FootingProfile,
        FootingPlacement,
        FootingPiles,
        PileProfile,
        FootingReinforcement,
    )

    manifest = ProjectManifest(
        project=ProjectInfo(id="P01", name="Footing Rebar & Pile Test"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="L1", name="Level 1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 4.0}),
        materials=[
            Material(id="CONC_240", name="Concrete 240 ksc", category="concrete", unit_cost_ref="MAT-CONC-01")
        ],
        elements=[
            IfcFooting(
                **{
                    "class": "IfcFooting",
                    "tag": "F1-01",
                    "material": "CONC_240",
                    "profile": FootingProfile(width=1.5, depth=1.5, thickness=0.5),
                    "placement": FootingPlacement(grid=("1", "A"), storey="L1"),
                    "reinforcement": FootingReinforcement(
                        mesh_x="DB12 @ 0.15m",
                        mesh_y="DB12 @ 0.15m",
                    ),
                    "piles": FootingPiles(
                        count=4,
                        profile=PileProfile(shape="HEXAGONAL", dimension=0.15),
                        length=8.0,
                    ),
                }
            )
        ],
    )

    qto = calculate_qto(manifest)
    assert qto.total_pile_count == 4
    assert qto.total_pile_length == 32.0
    assert qto.total_pile_chipping_count == 4
    assert qto.total_rebar_weight > 0.0

    tmpl_path = generate_cost_template(manifest)
    catalog = load_price_catalog(tmpl_path)

    assert "MAT-REBAR-DB12" in catalog.items
    assert "MAT-PILE-PC" in catalog.items
    assert "MAT-PILE-DRIVE" in catalog.items
    assert "MAT-PILE-CHIP" in catalog.items

    # Populate dummy costs
    catalog.items["MAT-PILE-CHIP"].labor_cost = 250.0
    est = estimate_cost(qto, catalog, manifest)

    chip_line = next(item for item in est.line_items if item.code == "MAT-PILE-CHIP")
    assert chip_line.quantity == 4.0
    assert chip_line.total_labor_cost == 1000.0


def test_generate_cost_template_modular(sample_project_path, tmp_path):
    out_main = tmp_path / "prices" / "catalog.yaml"
    res_path = generate_cost_template(sample_project_path, output_path=out_main, modular=True)

    assert res_path.exists()
    modules_dir = tmp_path / "prices" / "modules"
    assert modules_dir.exists()
    assert (modules_dir / "structure.yaml").exists()
    assert (modules_dir / "architecture.yaml").exists()

    # Verify loading the modular template works seamlessly
    catalog = load_price_catalog(out_main)
    assert "MAT-CONC-01" in catalog.items
    assert "MAT-AAC-01" in catalog.items
    assert "MAT-FORMWORK" in catalog.items
    assert "MAT-REBAR-DB16" in catalog.items


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


def test_cli_cost_and_template_commands(sample_project_path, sample_prices_path, tmp_path):
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

    # Test `bim cost -p -` (stdin piping)
    sample_prices_content = Path(sample_prices_path).read_text(encoding="utf-8")
    res_stdin = runner.invoke(
        app,
        ["cost", "--manifest", str(sample_project_path), "-p", "-"],
        input=sample_prices_content,
    )
    assert res_stdin.exit_code == 0
    assert "Cost Estimate Summary" in res_stdin.output
    assert "19,102.30" in res_stdin.output

    # Test `bim cost template`
    tmpl_file = tmp_path / "prices.template.yaml"
    res_tmpl = runner.invoke(
        app,
        [
            "cost",
            "template",
            "--manifest",
            str(sample_project_path),
            "--output",
            str(tmpl_file),
        ],
    )
    assert res_tmpl.exit_code == 0
    assert "Cost Catalog Template Generated Successfully!" in res_tmpl.output
    assert tmpl_file.exists()
