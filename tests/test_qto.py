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
