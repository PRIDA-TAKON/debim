"""
Unit tests for debim-standards integration:
- Local cache retrieval & HTTP/offline fallbacks
- Audit compliance MR 55 legal rulesets hook
- 2D furniture fit solver fallback
- BOQ pricing and embodied carbon footprint calculation
"""

from pathlib import Path
import pytest

from debim.standards import (
    fetch_catalog,
    get_furniture,
    get_material_price,
    get_regulations,
    list_standards,
    sync_standards,
)
from debim.audit import run_5_layer_audit
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.schema import (
    Dimensions,
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
from debim.solver import solve_manifest_furniture_fit


def test_standards_cache_and_retrieval():
    """Verify standards cache syncing and fetching functions."""
    sync_res = sync_standards(force=False)
    assert isinstance(sync_res, dict)
    assert "furniture" in sync_res
    assert "regulations" in sync_res
    assert "material_prices" in sync_res

    info = list_standards()
    assert "furniture" in info
    assert info["furniture"]["count"] > 0

    bed = get_furniture("BED_KING_6FT")
    assert bed is not None
    assert bed.width == 1.83
    assert bed.depth == 1.98
    assert bed.clearance["front"] == 0.60
    assert bed.footprint_area > 0

    reg = get_regulations("TH")
    assert reg is not None
    assert reg["natural_ventilation_ratio"] == 0.10
    assert reg["stair_riser_max"] == 0.20
    assert reg["corridor_width_min"] == 1.00

    price = get_material_price("MAT-CONC-240")
    assert price is not None
    assert price.material_cost == 2400.0
    assert price.labor_cost == 450.0
    assert price.embodied_carbon == 350.0


def test_audit_regulations_integration():
    """Verify Layer 2 of debim audit uses get_regulations('TH')."""
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ_REG", name="Test Regulations"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST1", name="FL1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 4.0}),
        materials=[Material(id="CONC", name="Concrete", category="structure", unit_cost_ref="MAT-CONC-240")],
        elements=[
            IfcSpace(
                tag="SP_WET",
                name="Bathroom WC",
                drop_elevation=0.00,  # Violates MR 55 drop <= -0.10m
                placement=SpacePlacement(storey="ST1", boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")]),
            )
        ],
    )

    report = run_5_layer_audit(manifest, apply_fixes=False)
    l2 = report.layers[2]
    assert not l2.passed
    violation_codes = [v.rule_code for v in l2.items]
    assert "LAYER2_BATHROOM_SLAB_DROP" in violation_codes


def test_solver_furniture_fit_fallback():
    """Verify 2D fit solver resolves furniture specs from get_furniture(...) when not in manifest."""
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ_FIT", name="Test Fit"),
        spatial_structure=SpatialStructure(storeys=[Storey(id="ST1", name="FL1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"1": 0.0, "2": 6.0}, axes_y={"A": 0.0, "B": 6.0}),
        materials=[Material(id="CONC", name="Concrete", category="structure", unit_cost_ref="MAT-CONC-240")],
        elements=[
            IfcSpace(
                tag="SP_BED",
                name="Bedroom",
                contains=["BED_KING_6FT"],  # Not defined in manifest.variables -> fallback to debim-standards
                placement=SpacePlacement(storey="ST1", boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")]),
            )
        ],
    )

    fit_res = solve_manifest_furniture_fit(manifest)
    assert fit_res.passed
    assert len(fit_res.spaces) == 1
    s_res = fit_res.spaces[0]
    assert len(s_res.placements) == 1
    p = s_res.placements[0]
    assert p.ref == "BED_KING_6FT"
    assert p.width == 1.83
    assert p.depth == 1.98


def test_boq_embodied_carbon_calculation(tmp_path: Path):
    """Verify BOQ cost estimation with --standards calculates pricing & embodied carbon footprint."""
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ_BOQ", name="Test BOQ Carbon"),
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

    # Calculate with standards
    cost_std = estimate_cost(qto, price_cat, manifest=manifest, use_standards=True)
    assert cost_std.grand_total > 0
    assert cost_std.total_embodied_carbon > 0

    conc_line = next((item for item in cost_std.line_items if item.code == "MAT-CONC-240"), None)
    assert conc_line is not None
    assert conc_line.unit_material_cost == 2400.0
    assert conc_line.unit_labor_cost == 450.0
    assert conc_line.embodied_carbon_unit == 350.0
    assert conc_line.total_embodied_carbon == conc_line.quantity * 350.0
