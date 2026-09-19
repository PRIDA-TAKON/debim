from pathlib import Path
import pytest
from debim.schema import load_manifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc


def test_contemporary_thai_house_manifest():
    manifest_path = Path("examples/contemporary_thai_house/project.yaml")
    assert manifest_path.exists(), "Manifest file should exist"

    manifest = load_manifest(manifest_path)
    assert manifest.project.id == "PRJ-THAI-HOUSE-05"
    assert len(manifest.spatial_structure.storeys) == 4
    assert len(manifest.grids.axes_x) == 6
    assert len(manifest.grids.axes_y) == 16


def test_contemporary_thai_house_resolution_and_qto():
    manifest_path = Path("examples/contemporary_thai_house/project.yaml")
    manifest = load_manifest(manifest_path)
    resolved = resolve_manifest(manifest)

    # 17 footings
    assert len(resolved.footings) == 17
    # 19 slabs (Level 1 ground slabs + Level 2 precast planks)
    assert len(resolved.slabs) == 19
    # 1 stair assembly verification
    assert len(resolved.stairs) == 1
    stair = resolved.stairs[0]
    assert len(stair.flights) == 2
    assert len(stair.steps) == 20  # 10 steps flight 1 + 10 steps flight 2
    assert len(stair.stringers) == 2  # Stringers for both flights
    assert stair.railing is not None
    assert stair.railing.total_length > 0.0
    assert stair.nosing_length == 20 * 1.00  # 20 steps * 1.00m width = 20.0m

    # 17 columns per floor level (C0, C1, C2)
    assert len(resolved.columns) > 30
    assert len(resolved.beams) > 30

    # 31 walls, 13 doors, 18 windows
    assert len(resolved.walls) == 31
    assert len(resolved.doors) == 13
    assert len(resolved.windows) == 18

    qto_result = calculate_qto(manifest_path)
    # Total concrete volume including 17 footings, 19 slabs, and 1 stair
    assert 50.0 <= qto_result.total_concrete_volume <= 58.0

    # Wall masonry takeoffs (brick area net of openings)
    masonry_area = sum(
        eq.concrete_volume / 0.10
        for eq in qto_result.elements
        if eq.material == "BRICK_MON"
    )
    assert 220.0 <= masonry_area <= 235.0
    assert 220.0 <= qto_result.total_wall_masonry_area <= 235.0

    # Wall finishes takeoffs (Plaster, Paint Interior/Exterior, Wall Tiles)
    assert 450.0 <= qto_result.total_wall_plaster_area <= 460.0
    assert 180.0 <= qto_result.total_wall_paint_interior_area <= 190.0
    assert 220.0 <= qto_result.total_wall_paint_exterior_area <= 235.0
    assert 40.0 <= qto_result.total_wall_tile_area <= 45.0


    # Stair architectural takeoffs
    assert qto_result.total_nosing_length == 20.0
    assert qto_result.total_railing_length > 5.0

    # Roof structure & covering takeoffs
    assert len(resolved.roofs) == 1
    house_roof = resolved.roofs[0]
    assert house_roof.roof_type == "HIP"
    assert len(house_roof.planes) == 4
    assert 140.0 <= qto_result.total_roof_covering_area <= 155.0
    assert 2200.0 <= qto_result.total_roof_steel_weight <= 2400.0
    assert round(qto_result.total_roof_ridge_length, 2) == 0.60
    assert qto_result.total_roof_hip_length > 25.0
    assert round(qto_result.total_roof_eaves_length, 2) == 45.20
    # Roof framing members (อกไก่, ตะเข้สัน, เสาดั้ง, ขื่อ, อะเส, จันทัน, แป)
    assert len(house_roof.framing_members) > 20
    house_m_types = {m.member_type for m in house_roof.framing_members}
    assert {"WALL_PLATE", "RIDGE_BEAM", "HIP_RAFTER", "KING_POST", "TIE_BEAM", "PURLIN"}.issubset(house_m_types)

    # Rebar weight verification
    assert qto_result.total_rebar_weight > 3000.0
    # Piles verification: 63 piles total, 378.0 meters total length
    assert qto_result.total_pile_count == 63
    assert qto_result.total_pile_length == 378.0

    # Substructure & Earthwork verification (BOQ Group 3)
    assert 65.0 <= qto_result.total_excavation_volume <= 70.0
    assert 3.0 <= qto_result.total_lean_concrete_volume <= 3.5
    assert 11.5 <= qto_result.total_sand_bedding_volume <= 12.5

    # Ceilings verification (BOQ Group 1)
    assert round(qto_result.total_ceiling_gypsum_area, 2) == 161.0
    assert round(qto_result.total_ceiling_tbar_area, 2) == 15.0
    assert round(qto_result.total_ceiling_eaves_area, 2) == 48.0

    # Flooring & Finishes verification (BOQ Group 2)
    assert qto_result.total_floor_tile_area == 110.0
    assert qto_result.total_floor_polish_area == 55.0
    assert qto_result.total_skirting_length == 123.0

    # Wall-Hosted MEP Fixtures verification
    # Check all sanitary fixtures, key switches/outlets, and AC units are wall-hosted
    wall_hosted_sanitary = [
        t for t in resolved.sanitary_terminals
        if getattr(t.element.placement, "wall", None) is not None
    ]
    assert len(wall_hosted_sanitary) == 13
    assert all(t.position is not None for t in wall_hosted_sanitary)

    # Check electrical elements wall-hosting
    wall_hosted_db = [
        db for db in resolved.distribution_boards
        if getattr(db.element.placement, "wall", None) is not None
    ]
    assert any(db.tag == "CU-MAIN-01" and db.element.placement.wall == "WALL-L1-C_2-4" for db in wall_hosted_db)

    wall_hosted_switches = [
        sw for sw in resolved.switches
        if getattr(sw.element.placement, "wall", None) is not None
    ]
    assert len(wall_hosted_switches) == 2

    wall_hosted_outlets = [
        out for out in resolved.outlets
        if getattr(out.element.placement, "wall", None) is not None
    ]
    assert len(wall_hosted_outlets) == 2

    # Check HVAC elements wall-hosting
    wall_hosted_hvac = [
        eq for eq in resolved.unitary_equipments
        if getattr(eq.element.placement, "wall", None) is not None
    ]
    assert len(wall_hosted_hvac) == 4





def test_contemporary_thai_house_ifc_compilation(tmp_path):
    manifest_path = Path("examples/contemporary_thai_house/project.yaml")
    out_ifc = tmp_path / "thai_house.ifc"
    
    compile_to_ifc(manifest_path, out_ifc)
    assert out_ifc.exists()
    assert out_ifc.stat().st_size > 5000
