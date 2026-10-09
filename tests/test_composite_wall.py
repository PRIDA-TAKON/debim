"""
Tests for Multi-layer Composite Walls (IfcMaterialLayerSet).
"""

from pathlib import Path
import pytest

from debim.schema import IfcWall, WallLayer, WallPlacement, load_manifest, ProjectManifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.cost import estimate_cost, PriceCatalog, PriceItem
from debim.compiler import compile_to_ifc


def test_composite_wall_schema_auto_thickness():
    layers = [
        WallLayer(name="Exterior Plaster", material="PLASTER_EXT", thickness=0.015, function="finish"),
        WallLayer(name="AAC Block Core", material="AAC_BLOCK", thickness=0.075, function="structure"),
        WallLayer(name="Interior Plaster", material="PLASTER_INT", thickness=0.015, function="finish"),
    ]
    wall = IfcWall(
        tag="W-COMP-01",
        height=3.0,
        placement=WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
        layers=layers,
    )
    # Thickness should be auto-computed from sum of layers: 0.015 + 0.075 + 0.015 = 0.105 m
    assert pytest.approx(wall.thickness, 1e-4) == 0.105
    assert wall.material == "PLASTER_EXT"


def test_composite_wall_qto_and_cost(tmp_path):
    project_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-COMPOSITE-WALL
  name: "Composite Wall Test"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }
spatial_structure:
  storeys:
    - id: L1
      name: "Ground Floor"
      elevation: 0.0
      height: 3.0
grids:
  axes_x: { "1": 0.0, "2": 4.0 }
  axes_y: { "A": 0.0, "B": 5.0 }
materials:
  - id: MAT_AAC
    name: "Autoclaved Aerated Concrete"
    category: masonry
    unit_cost_ref: "AAC-01"
  - id: MAT_PLASTER
    name: "Cement Plaster"
    category: finish
    unit_cost_ref: "PLASTER-01"
elements:
  - class: IfcWall
    tag: "W01"
    height: 3.0
    placement:
      from_grid: ["1", "A"]
      to_grid: ["2", "A"]
      storey: L1
    layers:
      - name: "Ext Plaster"
        material: MAT_PLASTER
        thickness: 0.02
        function: finish
      - name: "AAC Core"
        material: MAT_AAC
        thickness: 0.08
        function: structure
      - name: "Int Plaster"
        material: MAT_PLASTER
        thickness: 0.02
        function: finish
"""
    p_file = tmp_path / "project.yaml"
    p_file.write_text(project_yaml, encoding="utf-8")

    manifest = load_manifest(p_file)
    assert len(manifest.elements) == 1
    w = manifest.elements[0]
    assert pytest.approx(w.thickness, 1e-4) == 0.12  # 0.02 + 0.08 + 0.02

    resolved = resolve_manifest(manifest)
    qto = calculate_qto(resolved)
    eqto = qto.get_element("W01")
    assert eqto is not None
    assert eqto.wall_layers is not None
    assert len(eqto.wall_layers) == 3

    # Wall length = 4.0m, height = 3.0m => Area = 12.0 m2
    for layer_qto in eqto.wall_layers:
        assert pytest.approx(layer_qto.area, 1e-3) == 12.0

    # Layer 0 (Plaster 0.02m) => Vol = 12 * 0.02 = 0.24 m3
    assert pytest.approx(eqto.wall_layers[0].volume, 1e-3) == 0.24
    # Layer 1 (AAC 0.08m) => Vol = 12 * 0.08 = 0.96 m3
    assert pytest.approx(eqto.wall_layers[1].volume, 1e-3) == 0.96
    # Layer 2 (Plaster 0.02m) => Vol = 12 * 0.02 = 0.24 m3
    assert pytest.approx(eqto.wall_layers[2].volume, 1e-3) == 0.24

    # Test Cost Engine with individual layer prices
    catalog = PriceCatalog(
        currency="THB",
        items={
            "AAC-01": PriceItem(
                name="AAC Block",
                unit="m3",
                material_cost=2500.0,
                labor_cost=500.0,
            ),
            "PLASTER-01": PriceItem(
                name="Cement Plaster",
                unit="m2",
                material_cost=80.0,
                labor_cost=70.0,
            ),
        },
    )
    cost = estimate_cost(qto, catalog, manifest=manifest)
    assert cost.grand_total > 0

    # Test IFC Compilation
    out_ifc = tmp_path / "model.ifc"
    compile_to_ifc(resolved, str(out_ifc))
    assert out_ifc.exists()
