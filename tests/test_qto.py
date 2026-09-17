"""
Unit tests for QTO Engine (debim.qto).
"""

import pytest
from debim.qto import (
    calculate_qto,
    get_bar_unit_weight,
    parse_main_bars,
    parse_stirrups,
)
from debim.schema import load_manifest


def test_bar_unit_weight_lookup_and_fallback():
    # Known standard weights
    assert get_bar_unit_weight("RB6") == pytest.approx(0.222, rel=1e-3)
    assert get_bar_unit_weight("RB9") == pytest.approx(0.499, rel=1e-3)
    assert get_bar_unit_weight("DB12") == pytest.approx(0.888, rel=1e-3)
    assert get_bar_unit_weight("DB16") == pytest.approx(1.578, rel=1e-3)
    assert get_bar_unit_weight("DB20") == pytest.approx(2.466, rel=1e-3)
    assert get_bar_unit_weight("DB25") == pytest.approx(3.853, rel=1e-3)

    # Fallback formula: diameter_mm^2 / 162.0
    # For T10 -> 100 / 162 = 0.61728...
    assert get_bar_unit_weight("T10") == pytest.approx(100.0 / 162.0, rel=1e-3)
    assert get_bar_unit_weight("UNKNOWN") == 0.0


def test_parse_main_bars():
    weights, total = parse_main_bars("4-DB16", element_length=3.5)
    # 4 * 3.5 * 1.578 = 22.092
    assert weights["DB16"] == pytest.approx(22.092, rel=1e-2)
    assert total == pytest.approx(22.092, rel=1e-2)

    # Combined notation "2-DB16 + 3-DB20"
    w_comb, tot_comb = parse_main_bars("2-DB16 + 3-DB20", element_length=4.0)
    # 2 * 4.0 * 1.578 = 12.624
    # 3 * 4.0 * 2.466 = 29.592
    assert w_comb["DB16"] == pytest.approx(12.624, rel=1e-2)
    assert w_comb["DB20"] == pytest.approx(29.592, rel=1e-2)
    assert tot_comb == pytest.approx(42.216, rel=1e-2)


def test_parse_stirrups():
    # RB6 @ 0.15m for col height 3.5m, w=0.2m, d=0.2m
    # perim = 0.8m, num = int(3.5/0.15)+1 = 24
    # weight = 24 * 0.8 * 0.222 = 4.2624
    w_dict, total = parse_stirrups("RB6 @ 0.15m", element_length=3.5, width=0.2, depth=0.2)
    assert w_dict["RB6"] == pytest.approx(4.2624, rel=1e-2)
    assert total == pytest.approx(4.2624, rel=1e-2)


def test_townhouse_qto_calculations(sample_project_path):
    manifest = load_manifest(sample_project_path)
    qto = calculate_qto(manifest)

    # Column C-A1
    col_qto = qto.get_element("C-A1")
    assert col_qto is not None
    assert col_qto.concrete_volume == pytest.approx(0.140, rel=1e-2)
    assert col_qto.formwork_area == pytest.approx(2.800, rel=1e-2)
    assert col_qto.total_rebar_weight == pytest.approx(26.354, rel=1e-2)

    # Beam B-A1_B1
    beam_qto = qto.get_element("B-A1_B1")
    assert beam_qto is not None
    assert beam_qto.concrete_volume == pytest.approx(0.320, rel=1e-2)
    assert beam_qto.formwork_area == pytest.approx(4.000, rel=1e-2)
    assert beam_qto.total_rebar_weight == pytest.approx(58.384, rel=1e-2)

    # Wall W-A1_A2
    wall_qto = qto.get_element("W-A1_A2")
    assert wall_qto is not None
    assert wall_qto.concrete_volume == pytest.approx(1.0275, rel=1e-2)
    assert wall_qto.formwork_area == pytest.approx(27.400, rel=1e-2)
    assert wall_qto.total_rebar_weight == 0.0

    # Project QTO Totals
    # Total Concrete Volume (Columns + Beams): 0.140 + 0.320 = 0.460 m³
    assert qto.total_concrete_volume == pytest.approx(0.460, rel=1e-2)

    # Total Formwork Area: 2.80 + 4.00 + 27.40 = 34.20 m²
    assert qto.total_formwork_area == pytest.approx(34.200, rel=1e-2)

    # Total Rebar Weight: 26.3544 + 58.3836 = 84.738 kg
    assert qto.total_rebar_weight == pytest.approx(84.738, rel=1e-2)


def test_footing_substructure_qto():
    from debim.resolver import ResolvedCustomElement
    from debim.schema import IfcCustomElement, CustomElementPlacement
    from debim.qto import calculate_element_qto

    footing_elem = IfcCustomElement(
        **{
            "class": "IfcCustomElement",
            "tag": "F2-TEST",
            "name": "Footing F2",
            "source": "assets/footing_f2.glb",
            "placement": CustomElementPlacement(position=(0.0, 0.0, 0.0), storey="GL"),
        }
    )
    resolved = ResolvedCustomElement(
        tag="F2-TEST",
        element=footing_elem,
        position=(0.0, 0.0, 0.0),
    )
    eqto = calculate_element_qto(resolved)
    assert eqto.concrete_volume == pytest.approx(0.960, rel=1e-2)
    assert eqto.formwork_area == pytest.approx(3.680, rel=1e-2)
    assert eqto.total_rebar_weight > 0.0
    assert eqto.substructure is not None
    assert eqto.substructure.lean_concrete_volume == pytest.approx(0.120, rel=1e-2)
    assert eqto.substructure.sand_bedding_volume == pytest.approx(0.060, rel=1e-2)
    assert eqto.substructure.pile_count == 2
    assert eqto.substructure.pile_total_length == pytest.approx(24.0, rel=1e-2)


def test_ifcfooting_with_piles_qto():
    from debim.resolver import ResolvedFooting, ResolvedPile
    from debim.schema import IfcFooting, FootingProfile, FootingPlacement, FootingPiles, PileProfile
    from debim.qto import calculate_element_qto

    footing_elem = IfcFooting(
        **{
            "class": "IfcFooting",
            "tag": "F4-01",
            "material": "CONC_240",
            "profile": FootingProfile(width=1.20, depth=1.20, thickness=0.40),
            "placement": FootingPlacement(grid=("1", "A"), storey="L1"),
            "piles": FootingPiles(
                count=4,
                profile=PileProfile(shape="HEXAGONAL", dimension=0.15),
                length=6.00,
            ),
        }
    )
    resolved = ResolvedFooting(
        tag="F4-01",
        element=footing_elem,
        position=(0.0, 0.0, -1.50),
        width=1.20,
        depth=1.20,
        thickness=0.40,
        piles=[
            ResolvedPile(
                tag=f"F4-01-P{i+1}",
                position=(0.0, 0.0, -1.50),
                length=6.00,
                dimension=0.15,
                shape="HEXAGONAL",
            )
            for i in range(4)
        ],
    )
    eqto = calculate_element_qto(resolved)
    assert eqto.concrete_volume == pytest.approx(1.20 * 1.20 * 0.40, rel=1e-3)
    assert eqto.formwork_area == pytest.approx(2.0 * (1.20 + 1.20) * 0.40, rel=1e-3)
    assert eqto.substructure is not None
    assert eqto.substructure.pile_count == 4
    assert eqto.substructure.pile_total_length == pytest.approx(24.0, rel=1e-3)
    assert eqto.substructure.lean_concrete_volume == pytest.approx(1.20 * 1.20 * 0.10, rel=1e-3)
    assert eqto.substructure.sand_bedding_volume == pytest.approx(1.20 * 1.20 * 0.05, rel=1e-3)


def test_slab_qto():
    from debim.resolver import ResolvedSlab
    from debim.schema import IfcSlab, SlabPlacement, SlabReinforcement
    from debim.qto import calculate_element_qto

    slab_elem = IfcSlab(
        **{
            "class": "IfcSlab",
            "tag": "S-01",
            "material": "MAT_CONC",
            "thickness": 0.10,
            "slab_type": "SOLID",
            "placement": SlabPlacement(
                boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                storey="L1",
            ),
            "reinforcement": SlabReinforcement(mesh="Wire Mesh Ø 4mm @ 0.20m"),
        }
    )
    resolved = ResolvedSlab(
        tag="S-01",
        element=slab_elem,
        polygon=[(0.0, 0.0, 3.5), (4.0, 0.0, 3.5), (4.0, 5.0, 3.5), (0.0, 5.0, 3.5)],
        thickness=0.10,
        area=20.0,
        center=(2.0, 2.5, 3.5),
    )
    eqto = calculate_element_qto(resolved)
    assert eqto.concrete_volume == pytest.approx(2.0, rel=1e-3)  # 20.0 m2 * 0.10m = 2.0 m3
    assert eqto.formwork_area == pytest.approx(20.0, rel=1e-3)  # Soffit area
    assert eqto.total_rebar_weight > 0.0

