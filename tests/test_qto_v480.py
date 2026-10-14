"""
Unit tests for Thai Comptroller General's Department (CGD / กรมบัญชีกลาง ว480)
reinforcement density rules, formwork contact deductions, Factor F, and BOQ sheets (ปร.4, ปร.4(พ), ปร.5).
"""

import pytest
from debim.cost import (
    PriceCatalog,
    PriceItem,
    calculate_factor_f,
    estimate_cost,
)
from debim.qto import (
    CGD_V480_REINFORCEMENT_DENSITY,
    calculate_element_qto,
    calculate_qto,
)
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedFooting,
    ResolvedSlab,
    ResolvedStair,
    ResolvedStairFlight,
    ResolvedStairStep,
)
from debim.schema import (
    BoxProfile,
    Dimensions,
    FootingPlacement,
    FootingProfile,
    Grids,
    IfcBeam,
    IfcColumn,
    IfcFooting,
    IfcSlab,
    IfcStair,
    Material,
    ProjectInfo,
    ProjectManifest,
    SlabPlacement,
    SpatialStructure,
    StairPlacement,
    Storey,
)


def test_cgd_v480_reinforcement_density_fallbacks():
    """Verify default reinforcement density table values and QTO fallback calculations."""
    assert CGD_V480_REINFORCEMENT_DENSITY["footing"]["total_density"] == 110.0
    assert CGD_V480_REINFORCEMENT_DENSITY["column"]["total_density"] == 160.0
    assert CGD_V480_REINFORCEMENT_DENSITY["beam"]["total_density"] == 130.0
    assert CGD_V480_REINFORCEMENT_DENSITY["slab"]["total_density"] == 90.0
    assert CGD_V480_REINFORCEMENT_DENSITY["slab"]["ground_slab_wiremesh"] == 3.5
    assert CGD_V480_REINFORCEMENT_DENSITY["stair"]["total_density"] == 110.0

    # 1. Footing (no explicit rebar) -> 1.5m x 1.5m x 0.5m = 1.125 m3
    f_elem = IfcFooting(
        **{
            "class": "IfcFooting",
            "tag": "F-01",
            "material": "CONC_240",
            "profile": FootingProfile(width=1.5, depth=1.5, thickness=0.5),
            "placement": FootingPlacement(grid=("1", "A"), storey="L1"),
        }
    )
    r_footing = ResolvedFooting(
        tag="F-01",
        element=f_elem,
        position=(0.0, 0.0, -1.0),
        width=1.5,
        depth=1.5,
        thickness=0.5,
    )
    qto_f = calculate_element_qto(r_footing)
    assert qto_f.concrete_volume == pytest.approx(1.125)
    assert qto_f.total_rebar_weight == pytest.approx(1.125 * 110.0)  # 123.75 kg
    assert qto_f.rebar_weights["DB12_16"] == pytest.approx(1.125 * 95.0)
    assert qto_f.rebar_weights["RB9"] == pytest.approx(1.125 * 15.0)

    # 2. Column (no explicit rebar) -> 0.3m x 0.3m x 3.5m = 0.315 m3
    c_elem = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "COL-01",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.3, depth=0.3),
            "placement": {"grid": ["1", "A"], "base_storey": "L1", "top_storey": "L2"},
        }
    )
    r_col = ResolvedColumn(
        tag="COL-01",
        element=c_elem,
        start_point=(0.0, 0.0, 0.0),
        end_point=(0.0, 0.0, 3.5),
        height=3.5,
    )
    qto_c = calculate_element_qto(r_col)
    assert qto_c.concrete_volume == pytest.approx(0.315)
    assert qto_c.total_rebar_weight == pytest.approx(0.315 * 160.0)  # 50.4 kg
    assert qto_c.rebar_weights["DB16_20"] == pytest.approx(0.315 * 135.0)
    assert qto_c.rebar_weights["RB6_9"] == pytest.approx(0.315 * 25.0)

    # 3. Beam (no explicit rebar) -> 0.2m x 0.4m x 4.0m = 0.320 m3
    b_elem = IfcBeam(
        **{
            "class": "IfcBeam",
            "tag": "B-01",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.2, depth=0.4),
            "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "L1"},
        }
    )
    r_beam = ResolvedBeam(
        tag="B-01",
        element=b_elem,
        start_point=(0.0, 0.0, 3.5),
        end_point=(4.0, 0.0, 3.5),
        span_length=4.0,
    )
    qto_b = calculate_element_qto(r_beam)
    assert qto_b.concrete_volume == pytest.approx(0.320)
    assert qto_b.total_rebar_weight == pytest.approx(0.320 * 130.0)  # 41.6 kg

    # 4. Elevated Slab (no explicit rebar) -> 20 m2 x 0.12m = 2.4 m3
    s_elem = IfcSlab(
        **{
            "class": "IfcSlab",
            "tag": "S-01",
            "material": "CONC_240",
            "thickness": 0.12,
            "slab_type": "SOLID",
            "placement": SlabPlacement(boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")], storey="L1"),
        }
    )
    r_slab = ResolvedSlab(
        tag="S-01",
        element=s_elem,
        polygon=[(0.0, 0.0, 3.5), (4.0, 0.0, 3.5), (4.0, 5.0, 3.5), (0.0, 5.0, 3.5)],
        thickness=0.12,
        area=20.0,
        center=(2.0, 2.5, 3.5),
    )
    qto_s = calculate_element_qto(r_slab)
    assert qto_s.concrete_volume == pytest.approx(2.4)
    assert qto_s.total_rebar_weight == pytest.approx(2.4 * 90.0)  # 216.0 kg

    # 5. Ground Slab (wiremesh fallback) -> 20 m2 x 3.5 kg/m2 = 70.0 kg
    s_ground = IfcSlab(
        **{
            "class": "IfcSlab",
            "tag": "GS-01",
            "material": "CONC_240",
            "thickness": 0.10,
            "slab_type": "GROUND_SLAB",
            "placement": SlabPlacement(boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")], storey="GL"),
        }
    )
    r_gs = ResolvedSlab(
        tag="GS-01",
        element=s_ground,
        polygon=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 5.0, 0.0), (0.0, 5.0, 0.0)],
        thickness=0.10,
        area=20.0,
        center=(2.0, 2.5, 0.0),
    )
    qto_gs = calculate_element_qto(r_gs)
    assert qto_gs.rebar_weights["WIRE_MESH"] == pytest.approx(20.0 * 3.5)  # 70.0 kg


def test_formwork_contact_deductions():
    """Verify beam-column and footing-column formwork contact area deductions."""
    col1 = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "COL-1",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.3, depth=0.3),
            "placement": {"grid": ["1", "A"], "base_storey": "L1", "top_storey": "L2"},
        }
    )
    col2 = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "COL-2",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.3, depth=0.3),
            "placement": {"grid": ["2", "A"], "base_storey": "L1", "top_storey": "L2"},
        }
    )
    beam = IfcBeam(
        **{
            "class": "IfcBeam",
            "tag": "B-1",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.2, depth=0.4),
            "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "L1"},
        }
    )
    footing = IfcFooting(
        **{
            "class": "IfcFooting",
            "tag": "F-1",
            "material": "CONC_240",
            "profile": FootingProfile(width=1.5, depth=1.5, thickness=0.5),
            "placement": FootingPlacement(grid=("1", "A"), storey="L1", offset_z=-0.5),
        }
    )

    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-V480-TEST", name="V480 Formwork Deductions"),
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0}),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Level 1", elevation=0.0, height=3.5),
                Storey(id="L2", name="Level 2", elevation=3.5, height=3.5),
            ]
        ),
        materials=[Material(id="CONC_240", name="Concrete 240", category="concrete", unit_cost_ref="MAT-CONC")],
        elements=[footing, col1, col2, beam],
    )

    qto = calculate_qto(manifest)

    # Beam B-1:
    # Gross formwork = (2 * depth + width) * length = (2*0.4 + 0.2) * 4.0 = 4.0 m2
    # Connected at both C-1 and C-2 ends -> Beam cross section area = 0.2 * 0.4 = 0.08 m2
    # Deduction for 2 joints = 2 * 0.08 = 0.16 m2 -> Net formwork = 3.84 m2
    b_qto = qto.get_element("B-1")
    assert b_qto is not None
    assert b_qto.formwork_area == pytest.approx(4.0 - 0.16)

    # Footing F-1:
    # Gross formwork = 2 * (1.5 + 1.5) * 0.5 = 3.0 m2
    # Column C-1 lands on F-1 top surface -> Column area = 0.3 * 0.3 = 0.09 m2
    # Net formwork = 3.0 - 0.09 = 2.91 m2
    f_qto = qto.get_element("F-1")
    assert f_qto is not None
    assert f_qto.formwork_area == pytest.approx(3.0 - 0.09)


def test_factor_f_and_boq_sheets():
    """Verify CGD Factor F interpolation and ปร.4, ปร.4(พ), ปร.5 sheets generation."""
    # 1. Check exact bracket values
    assert calculate_factor_f(500000.0) == 1.3073
    assert calculate_factor_f(10000000.0) == 1.2726
    assert calculate_factor_f(500000000.0) == 1.1120

    # 2. Check linear interpolation between 5M (1.2858) and 10M (1.2726) for 7.5M
    # Expected: 1.2858 + 0.5 * (1.2726 - 1.2858) = 1.2792
    assert calculate_factor_f(7500000.0) == pytest.approx(1.2792, abs=1e-4)

    # 3. Create sample project and cost estimate
    col = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "COL-01",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.3, depth=0.3),
            "placement": {"grid": ["1", "A"], "base_storey": "L1", "top_storey": "L2"},
        }
    )
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-BOQ-TEST", name="Thai BOQ Project"),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="L1", elevation=0.0, height=3.5),
                Storey(id="L2", name="L2", elevation=3.5, height=3.5),
            ]
        ),
        materials=[Material(id="CONC_240", name="Concrete 240", category="concrete", unit_cost_ref="MAT-CONC")],
        elements=[col],
    )
    qto = calculate_qto(manifest)
    catalog = PriceCatalog(
        currency="THB",
        items={
            "MAT-CONC": PriceItem(name="Concrete 240", unit="m3", material_cost=2000.0, labor_cost=400.0),
            "MAT-FORMWORK": PriceItem(name="Timber Formwork", unit="m2", material_cost=300.0, labor_cost=100.0),
            "MAT-REBAR": PriceItem(name="Steel Rebar", unit="kg", material_cost=30.0, labor_cost=5.0),
        },
    )

    cost_est = estimate_cost(qto, catalog, manifest)

    # Generate ปร.4
    pr4 = cost_est.generate_pr4(project_name="โครงการอาคารพักอาศัย")
    assert pr4.title == "แบบ ปร.4 - รายการปริมาณงานและราคา"
    assert pr4.project_name == "โครงการอาคารพักอาศัย"
    assert len(pr4.items) > 0
    assert pr4.total_direct_cost == cost_est.grand_total

    # Generate ปร.4(พ)
    pr4_p = cost_est.generate_pr4_p(qto, catalog, project_name="โครงการอาคารพักอาศัย")
    assert pr4_p.title == "แบบ ปร.4(พ) - แบบสรุปพิกัดตารางเหล็กเสริมและไม้แบบ"
    assert pr4_p.total_rebar_weight_kg == qto.total_rebar_weight
    assert pr4_p.total_formwork_area_m2 == qto.total_formwork_area
    assert pr4_p.total_amount > 0.0

    # Generate ปร.5
    pr5 = cost_est.generate_pr5(project_name="โครงการอาคารพักอาศัย")
    assert pr5.title == "แบบ ปร.5 - แบบสรุปค่าก่อสร้าง"
    assert pr5.direct_cost == cost_est.grand_total
    assert pr5.factor_f == calculate_factor_f(cost_est.grand_total)
    assert pr5.total_construction_cost == pytest.approx(cost_est.grand_total * pr5.factor_f)
    assert len(pr5.groups) == 1
    assert pr5.groups[0].factor_f == pr5.factor_f
