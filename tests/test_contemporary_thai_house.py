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
    assert len(manifest.grids.axes_x) == 4
    assert len(manifest.grids.axes_y) == 6


def test_contemporary_thai_house_resolution_and_qto():
    manifest_path = Path("examples/contemporary_thai_house/project.yaml")
    manifest = load_manifest(manifest_path)
    resolved = resolve_manifest(manifest)

    # 17 footings
    assert len(resolved.footings) == 17
    # 19 slabs (Level 1 ground slabs + Level 2 precast planks)
    assert len(resolved.slabs) == 19
    # 17 columns per floor level (C0, C1, C2)
    assert len(resolved.columns) > 30
    assert len(resolved.beams) > 30

    qto_result = calculate_qto(manifest_path)
    # Total concrete volume including 17 footings and 19 slabs
    assert 50.0 <= qto_result.total_concrete_volume <= 56.0
    # Rebar weight verification
    assert qto_result.total_rebar_weight > 3000.0
    # Piles verification: 63 piles total, 378.0 meters total length
    assert qto_result.total_pile_count == 63
    assert qto_result.total_pile_length == 378.0


def test_contemporary_thai_house_ifc_compilation(tmp_path):
    manifest_path = Path("examples/contemporary_thai_house/project.yaml")
    out_ifc = tmp_path / "thai_house.ifc"
    
    compile_to_ifc(manifest_path, out_ifc)
    assert out_ifc.exists()
    assert out_ifc.stat().st_size > 5000
