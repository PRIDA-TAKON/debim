"""
Unit tests for AST preprocessor module macro expansion and grid replication in debim loader.
"""

import pytest
import yaml

from debim.loader import expand_module_instances, load_manifest
from debim.schema import ProjectManifest


@pytest.fixture
def shophouse_manifest_yaml(tmp_path):
    """Create a temporary project.yaml file containing a 4-bay shophouse module and replication config."""
    yaml_content = """
schema: IFC4-Minimal
project:
  id: PRJ-SHOPHOUSE-4BAY
  name: "4-Bay Shophouse Project"
  units:
    length: METER
    area: SQUARE_METER
    volume: CUBIC_METER
spatial_structure:
  storeys:
    - id: L1
      name: "Ground Floor"
      elevation: 0.00
      height: 3.50
    - id: L2
      name: "Second Floor"
      elevation: 3.50
      height: 3.20
grids:
  axes_x:
    "1": 0.0
    "2": 4.0
    "3": 8.0
    "4": 12.0
    "5": 16.0
  axes_y:
    "A": 0.0
    "B": 12.0
materials:
  - id: MAT_CONC
    name: "Concrete 240 ksc"
    category: concrete
    unit_cost_ref: REF-CONC
modules:
  - id: SHOPHOUSE_BAY
    name: "Standard Shophouse Bay Module"
    local_grids:
      axes_x:
        "1": 0.0
        "2": 4.0
      axes_y:
        "A": 0.0
        "B": 12.0
    elements:
      - class: IfcColumn
        tag: COL-C1
        material: MAT_CONC
        profile: {shape: BOX, width: 0.30, depth: 0.30}
        placement: {grid: ["1", "A"], base_storey: L1, top_storey: L2}
      - class: IfcColumn
        tag: COL-C2
        material: MAT_CONC
        profile: {shape: BOX, width: 0.30, depth: 0.30}
        placement: {grid: ["1", "B"], base_storey: L1, top_storey: L2}
      - class: IfcColumn
        tag: COL-C3
        material: MAT_CONC
        profile: {shape: BOX, width: 0.30, depth: 0.30}
        placement: {grid: ["2", "A"], base_storey: L1, top_storey: L2}
      - class: IfcColumn
        tag: COL-C4
        material: MAT_CONC
        profile: {shape: BOX, width: 0.30, depth: 0.30}
        placement: {grid: ["2", "B"], base_storey: L1, top_storey: L2}
      - class: IfcBeam
        tag: BM-B1
        material: MAT_CONC
        profile: {shape: BOX, width: 0.20, depth: 0.40}
        placement: {from_grid: ["1", "A"], to_grid: ["2", "A"], storey: L2}
      - class: IfcBeam
        tag: BM-B2
        material: MAT_CONC
        profile: {shape: BOX, width: 0.20, depth: 0.40}
        placement: {from_grid: ["1", "B"], to_grid: ["2", "B"], storey: L2}
      - class: IfcBeam
        tag: BM-B3
        material: MAT_CONC
        profile: {shape: BOX, width: 0.20, depth: 0.40}
        placement: {from_grid: ["1", "A"], to_grid: ["1", "B"], storey: L2}
      - class: IfcBeam
        tag: BM-B4
        material: MAT_CONC
        profile: {shape: BOX, width: 0.20, depth: 0.40}
        placement: {from_grid: ["2", "A"], to_grid: ["2", "B"], storey: L2}
      - class: IfcSlab
        tag: SLAB-S1
        material: MAT_CONC
        thickness: 0.12
        placement:
          boundary: [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]
          storey: L1
      - class: IfcWall
        tag: WALL-FRONT
        material: MAT_CONC
        thickness: 0.15
        height: 3.50
        placement: {from_grid: ["1", "A"], to_grid: ["2", "A"], storey: L1}
      - class: IfcWall
        tag: WALL-PARTY-L
        material: MAT_CONC
        thickness: 0.15
        height: 3.50
        placement: {from_grid: ["1", "A"], to_grid: ["1", "B"], storey: L1}
      - class: IfcWall
        tag: WALL-PARTY-R
        material: MAT_CONC
        thickness: 0.15
        height: 3.50
        placement: {from_grid: ["2", "A"], to_grid: ["2", "B"], storey: L1}
instances:
  - replicate:
      module: SHOPHOUSE_BAY
      count: 4
      along: grid_x
      prefix_pattern: "U{index}_"
      party_wall_deduplication: true
"""
    file_path = tmp_path / "project.yaml"
    file_path.write_text(yaml_content, encoding="utf-8")
    return file_path


def test_4bay_shophouse_expansion(shophouse_manifest_yaml):
    """Test loading and expanding 4-bay shophouse module with party wall deduplication."""
    manifest = load_manifest(shophouse_manifest_yaml)

    assert isinstance(manifest, ProjectManifest)
    assert manifest.project.id == "PRJ-SHOPHOUSE-4BAY"

    columns = [e for e in manifest.elements if getattr(e, "class_", e.__class__.__name__) == "IfcColumn"]
    beams = [e for e in manifest.elements if getattr(e, "class_", e.__class__.__name__) == "IfcBeam"]
    slabs = [e for e in manifest.elements if getattr(e, "class_", e.__class__.__name__) == "IfcSlab"]
    walls = [e for e in manifest.elements if getattr(e, "class_", e.__class__.__name__) == "IfcWall"]

    # Mathematical expectation:
    # 4 bays * 4 columns = 16 columns
    assert len(columns) == 16
    # 4 bays * 4 beams = 16 beams
    assert len(beams) == 16
    # 4 bays * 1 slab = 4 slabs
    assert len(slabs) == 4
    # 4 front walls + 5 deduplicated party walls (grid lines 1, 2, 3, 4, 5) = 9 walls
    assert len(walls) == 9

    # Verify column tags and remapped grid placements
    column_tags = {c.tag for c in columns}
    assert "U1_COL-C1" in column_tags
    assert "U4_COL-C4" in column_tags

    u4_col4 = next(c for c in columns if c.tag == "U4_COL-C4")
    assert u4_col4.placement.grid == ("5", "B")

    # Verify deduplicated walls
    wall_tags = {w.tag for w in walls}
    assert "U1_WALL-FRONT" in wall_tags
    assert "U4_WALL-FRONT" in wall_tags
    # Bay 1 left party wall (grid 1) and right party wall (grid 2)
    assert "U1_WALL-PARTY-L" in wall_tags
    assert "U1_WALL-PARTY-R" in wall_tags
    # Bay 2 left party wall on grid 2 was deduplicated with Bay 1 right party wall on grid 2
    assert "U2_WALL-PARTY-L" not in wall_tags
    assert "U2_WALL-PARTY-R" in wall_tags  # grid 3


def test_party_wall_deduplication_disabled(tmp_path):
    """Test module expansion when party_wall_deduplication is set to false."""
    yaml_content = """
schema: IFC4-Minimal
project: {id: PRJ-NODEDUP, name: "No Deduplication Test"}
spatial_structure:
  storeys: [{id: L1, name: "Ground Floor", elevation: 0.0, height: 3.0}]
grids:
  axes_x: {"1": 0.0, "2": 4.0, "3": 8.0}
  axes_y: {"A": 0.0, "B": 6.0}
materials:
  - {id: MAT_CONC, name: Concrete, category: concrete, unit_cost_ref: REF}
modules:
  - id: BAY
    local_grids: {axes_x: {"1": 0.0, "2": 4.0}, axes_y: {"A": 0.0, "B": 6.0}}
    elements:
      - class: IfcWall
        tag: WALL-PARTY-L
        material: MAT_CONC
        thickness: 0.15
        height: 3.0
        placement: {from_grid: ["1", "A"], to_grid: ["1", "B"], storey: L1}
      - class: IfcWall
        tag: WALL-PARTY-R
        material: MAT_CONC
        thickness: 0.15
        height: 3.0
        placement: {from_grid: ["2", "A"], to_grid: ["2", "B"], storey: L1}
instances:
  - replicate:
      module: BAY
      count: 2
      along: grid_x
      party_wall_deduplication: false
"""
    p_file = tmp_path / "project.yaml"
    p_file.write_text(yaml_content, encoding="utf-8")

    manifest = load_manifest(p_file)
    walls = [e for e in manifest.elements if getattr(e, "class_", "") == "IfcWall"]

    # Without deduplication, 2 bays * 2 walls = 4 walls
    assert len(walls) == 4
    wall_tags = {w.tag for w in walls}
    assert "U1_WALL-PARTY-L" in wall_tags
    assert "U1_WALL-PARTY-R" in wall_tags
    assert "U2_WALL-PARTY-L" in wall_tags
    assert "U2_WALL-PARTY-R" in wall_tags


def test_custom_prefix_pattern_and_explicit_grid_mapping(tmp_path):
    """Test custom prefix_pattern formatting and explicit grid_x_mapping list."""
    yaml_content = """
schema: IFC4-Minimal
project: {id: PRJ-MAPPED, name: "Grid Mapping Test"}
spatial_structure:
  storeys: [{id: L1, name: "Ground Floor", elevation: 0.0, height: 3.0}]
grids:
  axes_x: {"1": 0.0, "2": 5.0, "3": 10.0}
  axes_y: {"A": 0.0, "B": 8.0}
materials:
  - {id: MAT_CONC, name: Concrete, category: concrete, unit_cost_ref: REF}
modules:
  - id: MOD_A
    local_grids: {axes_x: {"1": 0.0, "2": 5.0}, axes_y: {"A": 0.0, "B": 8.0}}
    elements:
      - class: IfcColumn
        tag: C1
        material: MAT_CONC
        profile: {shape: BOX, width: 0.3, depth: 0.3}
        placement: {grid: ["1", "A"], base_storey: L1, top_storey: L1}
instances:
  - replicate:
      module: MOD_A
      count: 2
      grid_x_mapping:
        - {"1": "1", "2": "2"}
        - {"1": "2", "2": "3"}
      prefix_pattern: "BAY_{index}_"
"""
    p_file = tmp_path / "project.yaml"
    p_file.write_text(yaml_content, encoding="utf-8")

    manifest = load_manifest(p_file)
    columns = [e for e in manifest.elements if getattr(e, "class_", "") == "IfcColumn"]

    assert len(columns) == 2
    col_tags = {c.tag for c in columns}
    assert "BAY_1_C1" in col_tags
    assert "BAY_2_C1" in col_tags

    bay2_col = next(c for c in columns if c.tag == "BAY_2_C1")
    assert bay2_col.placement.grid == ("2", "A")


def test_expand_module_instances_dict_and_model_input():
    """Test expand_module_instances function directly with both dictionary and ProjectManifest input."""
    raw_dict = {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-DIRECT", "name": "Direct Test"},
        "spatial_structure": {"storeys": [{"id": "L1", "name": "L1", "elevation": 0.0, "height": 3.0}]},
        "grids": {"axes_x": {"1": 0.0, "2": 4.0}, "axes_y": {"A": 0.0, "B": 4.0}},
        "materials": [{"id": "M1", "name": "Mat", "category": "conc", "unit_cost_ref": "R1"}],
        "modules": [
            {
                "id": "MOD_X",
                "local_grids": {"axes_x": {"1": 0.0, "2": 4.0}, "axes_y": {"A": 0.0, "B": 4.0}},
                "elements": [
                    {
                        "class": "IfcColumn",
                        "tag": "COL-X",
                        "material": "M1",
                        "profile": {"shape": "BOX", "width": 0.3, "depth": 0.3},
                        "placement": {"grid": ["1", "A"], "base_storey": "L1", "top_storey": "L1"},
                    }
                ],
            }
        ],
        "instances": [
            {
                "replicate": {
                    "module": "MOD_X",
                    "count": 1,
                    "prefix_pattern": "U{index}_",
                }
            }
        ],
    }

    import copy

    # Test dict input
    dict_input = copy.deepcopy(raw_dict)
    res_dict = expand_module_instances(dict_input)
    assert isinstance(res_dict, dict)
    assert len(res_dict["elements"]) == 1
    assert res_dict["elements"][0]["tag"] == "U1_COL-X"

    # Test ProjectManifest input
    manifest_in = ProjectManifest.model_validate(copy.deepcopy(raw_dict))
    manifest_out = expand_module_instances(manifest_in)
    assert isinstance(manifest_out, ProjectManifest)
    assert len(manifest_out.elements) == 1
    assert manifest_out.elements[0].tag == "U1_COL-X"


def test_replicate_along_grid_y(tmp_path):
    """Test replication along grid_y direction with lettered grid axes remapping."""
    yaml_content = """
schema: IFC4-Minimal
project: {id: PRJ-GRID-Y, name: "Replicate Along Y Test"}
spatial_structure:
  storeys: [{id: L1, name: "Ground Floor", elevation: 0.0, height: 3.0}]
grids:
  axes_x: {"1": 0.0, "2": 5.0}
  axes_y: {"A": 0.0, "B": 4.0, "C": 8.0, "D": 12.0}
materials:
  - {id: MAT_CONC, name: Concrete, category: concrete, unit_cost_ref: REF}
modules:
  - id: BAY_Y
    local_grids: {axes_x: {"1": 0.0, "2": 5.0}, axes_y: {"A": 0.0, "B": 4.0}}
    elements:
      - class: IfcColumn
        tag: COL-CORNER
        material: MAT_CONC
        profile: {shape: BOX, width: 0.3, depth: 0.3}
        placement: {grid: ["1", "B"], base_storey: L1, top_storey: L1}
instances:
  - replicate:
      module: BAY_Y
      count: 3
      along: grid_y
      prefix_pattern: "ROW_{index}_"
"""
    p_file = tmp_path / "project.yaml"
    p_file.write_text(yaml_content, encoding="utf-8")

    manifest = load_manifest(p_file)
    columns = [e for e in manifest.elements if getattr(e, "class_", "") == "IfcColumn"]

    assert len(columns) == 3
    col_tags = {c.tag for c in columns}
    assert "ROW_1_COL-CORNER" in col_tags
    assert "ROW_2_COL-CORNER" in col_tags
    assert "ROW_3_COL-CORNER" in col_tags

    # ROW_1: local B maps to global B
    row1 = next(c for c in columns if c.tag == "ROW_1_COL-CORNER")
    assert row1.placement.grid == ("1", "B")

    # ROW_2: local B (offset 1 bay = +1) maps to global C
    row2 = next(c for c in columns if c.tag == "ROW_2_COL-CORNER")
    assert row2.placement.grid == ("1", "C")

    # ROW_3: local B (offset 2 bays = +2) maps to global D
    row3 = next(c for c in columns if c.tag == "ROW_3_COL-CORNER")
    assert row3.placement.grid == ("1", "D")
