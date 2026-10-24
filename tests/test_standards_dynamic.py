"""
Unit tests for debim dynamic multi-jurisdiction standards client & repository linker:
- StandardsClient local directory lookup, fallback caching, and multi-jurisdiction querying (th, sg, us, uk)
- Helper methods: get_regulations, get_material_spec, get_unit_cost, get_human_scale
- Integration with debim audit --jurisdiction th validating against regulations/th
- Integration with debim boq / estimate_cost for jurisdiction pricing & carbon factors
"""

import os
from pathlib import Path
import pytest

from debim.standards_client import (
    StandardsClient,
    get_human_scale,
    get_material_spec,
    get_regulations,
    get_unit_cost,
)
from debim.audit import run_5_layer_audit, AuditMatrixEvaluator
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.schema import (
    Grids,
    IfcSpace,
    IfcWall,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpacePlacement,
    SpatialStructure,
    Storey,
    WallPlacement,
)


def test_standards_client_jurisdictions():
    """Verify StandardsClient retrieves jurisdiction regulations for TH, SG, US, UK."""
    client = StandardsClient()

    th_reg = client.get_regulations("th")
    assert th_reg["jurisdiction"] == "TH"
    assert th_reg["natural_ventilation_ratio"] == 0.10
    assert th_reg["stair_riser_max"] == 0.20
    assert th_reg["door_clear_width_min"] == 0.80

    sg_reg = client.get_regulations("sg")
    assert sg_reg["jurisdiction"] == "SG"
    assert sg_reg["stair_riser_max"] == 0.175
    assert sg_reg["corridor_width_min"] == 1.20
    assert sg_reg["currency"] == "SGD"

    us_reg = client.get_regulations("us")
    assert us_reg["jurisdiction"] == "US"
    assert us_reg["stair_riser_max"] == 0.178
    assert us_reg["corridor_width_min"] == 1.118
    assert us_reg["currency"] == "USD"

    uk_reg = client.get_regulations("uk")
    assert uk_reg["jurisdiction"] == "UK"
    assert uk_reg["clear_headroom_min"] == 2.30
    assert uk_reg["currency"] == "GBP"


def test_standards_client_helper_methods():
    """Verify helper methods get_regulations, get_material_spec, get_unit_cost, get_human_scale."""
    reg_th = get_regulations("th")
    assert reg_th["jurisdiction"] == "TH"

    mat_spec = get_material_spec("MAT-CONC-240", jurisdiction="th")
    assert mat_spec is not None
    assert mat_spec["name"] == "Ready-Mixed Concrete 240 ksc Cylinder"
    assert mat_spec["material_cost"] == 2400.0

    cost_info = get_unit_cost("MAT-CONC-240", jurisdiction="th")
    assert cost_info is not None
    assert cost_info["currency"] == "THB"
    assert cost_info["total_price"] == 2850.0
    assert cost_info["embodied_carbon"] == 350.0

    scale_info = get_human_scale("BED_KING_6FT", jurisdiction="th")
    assert scale_info is not None
    assert scale_info["dimensions"]["width"] == 1.83
    assert scale_info["clearance"]["front"] == 0.60


def test_standards_client_local_dir_lookup(tmp_path: Path):
    """Verify local directory lookup takes precedence when local repo exists."""
    standards_dir = tmp_path / "debim-standards"
    regs_dir = standards_dir / "regulations"
    regs_dir.mkdir(parents=True)

    th_file = regs_dir / "th.yaml"
    th_file.write_text("""
jurisdiction: TH
name: Custom Local Thailand Standards
natural_ventilation_ratio: 0.12
stair_riser_max: 0.18
stair_tread_min: 0.25
corridor_width_min: 1.20
door_clear_width_min: 0.90
bathroom_slab_drop_max: -0.12
""", encoding="utf-8")

    client = StandardsClient(standards_dir=standards_dir)
    reg = client.get_regulations("th")
    assert reg["name"] == "Custom Local Thailand Standards"
    assert reg["natural_ventilation_ratio"] == 0.12
    assert reg["stair_riser_max"] == 0.18


def test_audit_multi_jurisdiction():
    """Verify debim audit uses requested jurisdiction regulations."""
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ_AUDIT_JUR", name="Test Audit Jurisdictions"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST1", name="FL1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 4.0}),
        materials=[Material(id="CONC", name="Concrete", category="structure", unit_cost_ref="MAT-CONC-240")],
        elements=[
            IfcSpace(
                tag="SP_WET",
                name="Bathroom WC",
                drop_elevation=-0.08,  # Satisfies SG max_drop -0.05, violates TH max_drop -0.10
                placement=SpacePlacement(storey="ST1", boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")]),
            )
        ],
    )

    report_th = run_5_layer_audit(manifest, jurisdiction="th")
    l2_th = report_th.layers[2]
    assert not l2_th.passed
    assert any(v.rule_code == "LAYER2_BATHROOM_SLAB_DROP" for v in l2_th.items)

    report_sg = run_5_layer_audit(manifest, jurisdiction="sg")
    l2_sg = report_sg.layers[2]
    # Under SG rules, drop_elevation -0.08 <= -0.05 passes
    assert not any(v.rule_code == "LAYER2_BATHROOM_SLAB_DROP" for v in l2_sg.items)


def test_boq_multi_jurisdiction(tmp_path: Path):
    """Verify BOQ cost estimation with --jurisdiction resolves correct currency & pricing."""
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ_BOQ_JUR", name="Test BOQ Jurisdiction"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST1", name="FL1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 4.0}),
        materials=[Material(id="CONC_240", name="Concrete 240", category="structure", unit_cost_ref="MAT-CONC-240")],
        elements=[
            IfcWall(
                tag="W1",
                material="CONC_240",
                thickness=0.20,
                height=3.0,
                placement=WallPlacement(storey="ST1", from_grid=("1", "A"), to_grid=("2", "A")),
            )
        ],
    )

    tmpl_path = tmp_path / "prices.yaml"
    generate_cost_template(manifest, output_path=tmpl_path)
    price_cat = load_price_catalog(tmpl_path)
    qto = calculate_qto(manifest)

    cost_est = estimate_cost(qto, price_cat, manifest=manifest, use_standards=True, jurisdiction="th")
    assert cost_est.grand_total > 0
    assert cost_est.currency == "THB"
    assert cost_est.total_embodied_carbon > 0
