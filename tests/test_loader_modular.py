"""
Unit tests for AST preprocessor module macro expansion and grid replication in debim.loader.
"""

from pathlib import Path
import pytest
import yaml

from debim.loader import expand_module_instances, load_manifest
from debim.schema import ProjectManifest, IfcColumn, IfcBeam, IfcSlab, IfcWall


SHOPHOUSE_4BAY_YAML = """
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
  - id: MAT_BRICK
    name: "Clay Brick Wall"
    category: masonry
    unit_cost_ref: REF-BRICK
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
        profile:
          shape: BOX
          width: 0.30
          depth: 0.30
        placement:
          grid: ["1", "A"]
          base_storey: L1
          top_storey: L2
      - class: IfcColumn
        tag: COL-C2
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.30
          depth: 0.30
        placement:
          grid: ["1", "B"]
          base_storey: L1
          top_storey: L2
      - class: IfcColumn
        tag: COL-C3
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.30
          depth: 0.30
        placement:
          grid: ["2", "A"]
          base_storey: L1
          top_storey: L2
      - class: IfcColumn
        tag: COL-C4
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.30
          depth: 0.30
        placement:
          grid: ["2", "B"]
          base_storey: L1
          top_storey: L2
      - class: IfcBeam
        tag: BM-B1
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.20
          depth: 0.40
        placement:
          from_grid: ["1", "A"]
          to_grid: ["2", "A"]
          storey: L2
      - class: IfcBeam
        tag: BM-B2
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.20
          depth: 0.40
        placement:
          from_grid: ["1", "B"]
          to_grid: ["2", "B"]
          storey: L2
      - class: IfcBeam
        tag: BM-B3
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.20
          depth: 0.40
        placement:
          from_grid: ["1", "A"]
          to_grid: ["1", "B"]
          storey: L2
      - class: IfcBeam
        tag: BM-B4
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.20
          depth: 0.40
        placement:
          from_grid: ["2", "A"]
          to_grid: ["2", "B"]
          storey: L2
      - class: IfcSlab
        tag: SLB-S1
        material: MAT_CONC
        thickness: 0.12
        placement:
          boundary: [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]
          storey: L2
      - class: IfcWall
        tag: WALL-F1
        material: MAT_BRICK
        thickness: 0.10
        height: 3.50
        placement:
          from_grid: ["1", "A"]
          to_grid: ["2", "A"]
          storey: L1
      - class: IfcWall
        tag: WALL-R1
        material: MAT_BRICK
        thickness: 0.10
        height: 3.50
        placement:
          from_grid: ["1", "B"]
          to_grid: ["2", "B"]
          storey: L1
      - class: IfcWall
        tag: WALL-P1
        material: MAT_BRICK
        thickness: 0.10
        height: 3.50
        placement:
          from_grid: ["1", "A"]
          to_grid: ["1", "B"]
          storey: L1
      - class: IfcWall
        tag: WALL-P2
        material: MAT_BRICK
        thickness: 0.10
        height: 3.50
        placement:
          from_grid: ["2", "A"]
          to_grid: ["2", "B"]
          storey: L1
instances:
  - module: SHOPHOUSE_BAY
    replicate:
      module: SHOPHOUSE_BAY
      count: 4
      along: grid_x
      prefix_pattern: "U{index}_"
      party_wall_deduplication: true
"""


@pytest.fixture
def shophouse_manifest_file(tmp_path: Path) -> Path:
    """Create a temporary project.yaml manifest file for a 4-bay shophouse."""
    manifest_path = tmp_path / "project.yaml"
    manifest_path.write_text(SHOPHOUSE_4BAY_YAML, encoding="utf-8")
    return manifest_path


def test_4bay_shophouse_expansion_counts_and_types(shophouse_manifest_file: Path):
    """Test loading a 4-bay shophouse manifest and verifying mathematical element counts."""
    manifest = load_manifest(shophouse_manifest_file)

    assert isinstance(manifest, ProjectManifest)
    assert manifest.project.id == "PRJ-SHOPHOUSE-4BAY"

    # Mathematical expansion expectation:
    # 4 bays * 4 columns = 16 columns
    # 4 bays * 4 beams = 16 beams
    # 4 bays * 1 slab = 4 slabs
    # 4 bays * 4 walls - 3 deduplicated party walls = 13 walls
    columns = [e for e in manifest.elements if isinstance(e, IfcColumn)]
    beams = [e for e in manifest.elements if isinstance(e, IfcBeam)]
    slabs = [e for e in manifest.elements if isinstance(e, IfcSlab)]
    walls = [e for e in manifest.elements if isinstance(e, IfcWall)]

    assert len(columns) == 16
    assert len(beams) == 16
    assert len(slabs) == 4
    assert len(walls) == 13

    # Total elements = 16 + 16 + 4 + 13 = 49
    assert len(manifest.elements) == 49


def test_4bay_shophouse_remapped_grid_coordinates(shophouse_manifest_file: Path):
    """Test that remapped grid coordinates correctly step along global axes."""
    manifest = load_manifest(shophouse_manifest_file)

    columns = [e for e in manifest.elements if isinstance(e, IfcColumn)]

    # Check U1 columns (Bay 1) mapped to global grids 1 and 2
    u1_col_grids = {e.tag: e.placement.grid for e in columns if e.tag.startswith("U1_")}
    assert u1_col_grids["U1_COL-C1"] == ("1", "A")
    assert u1_col_grids["U1_COL-C2"] == ("1", "B")
    assert u1_col_grids["U1_COL-C3"] == ("2", "A")
    assert u1_col_grids["U1_COL-C4"] == ("2", "B")

    # Check U2 columns (Bay 2) mapped to global grids 2 and 3
    u2_col_grids = {e.tag: e.placement.grid for e in columns if e.tag.startswith("U2_")}
    assert u2_col_grids["U2_COL-C1"] == ("2", "A")
    assert u2_col_grids["U2_COL-C2"] == ("2", "B")
    assert u2_col_grids["U2_COL-C3"] == ("3", "A")
    assert u2_col_grids["U2_COL-C4"] == ("3", "B")

    # Check U4 columns (Bay 4) mapped to global grids 4 and 5
    u4_col_grids = {e.tag: e.placement.grid for e in columns if e.tag.startswith("U4_")}
    assert u4_col_grids["U4_COL-C1"] == ("4", "A")
    assert u4_col_grids["U4_COL-C2"] == ("4", "B")
    assert u4_col_grids["U4_COL-C3"] == ("5", "A")
    assert u4_col_grids["U4_COL-C4"] == ("5", "B")

    # Check slabs boundary remapping
    slabs = [e for e in manifest.elements if isinstance(e, IfcSlab)]
    u1_slab = next(s for s in slabs if s.tag == "U1_SLB-S1")
    assert u1_slab.placement.boundary == [("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")]

    u4_slab = next(s for s in slabs if s.tag == "U4_SLB-S1")
    assert u4_slab.placement.boundary == [("4", "A"), ("5", "A"), ("5", "B"), ("4", "B")]


def test_shophouse_expansion_without_deduplication():
    """Test module replication with party_wall_deduplication: false."""
    data = yaml.safe_load(SHOPHOUSE_4BAY_YAML)
    data["instances"][0]["replicate"]["party_wall_deduplication"] = False

    manifest = ProjectManifest.model_validate(data)

    walls = [e for e in manifest.elements if isinstance(e, IfcWall)]
    # Without deduplication: 4 bays * 4 walls = 16 walls
    assert len(walls) == 16


def test_custom_prefix_pattern():
    """Test custom tag prefix pattern e.g., BAY_{index:02d}_."""
    data = yaml.safe_load(SHOPHOUSE_4BAY_YAML)
    data["instances"][0]["replicate"]["prefix_pattern"] = "BAY_{index:02d}_"

    manifest = ProjectManifest.model_validate(data)

    tags = [e.tag for e in manifest.elements]
    assert "BAY_01_COL-C1" in tags
    assert "BAY_02_COL-C1" in tags
    assert "BAY_04_COL-C4" in tags
    assert "BAY_01_SLB-S1" in tags


def test_explicit_grid_x_mapping():
    """Test module replication with explicit grid_x_mapping provided."""
    data = yaml.safe_load(SHOPHOUSE_4BAY_YAML)
    data["instances"][0]["replicate"]["grid_x_mapping"] = [
        {"1": "1", "2": "2"},
        {"1": "2", "2": "3"},
        {"1": "3", "2": "4"},
        {"1": "4", "2": "5"},
    ]

    manifest = ProjectManifest.model_validate(data)
    columns = [e for e in manifest.elements if isinstance(e, IfcColumn)]
    assert len(columns) == 16


def test_idempotent_module_expansion():
    """Test that calling expand_module_instances multiple times is idempotent."""
    data = yaml.safe_load(SHOPHOUSE_4BAY_YAML)
    expanded_1 = expand_module_instances(data)
    count_1 = len(expanded_1["elements"])

    expanded_2 = expand_module_instances(expanded_1)
    count_2 = len(expanded_2["elements"])

    assert count_1 == count_2 == 49


def test_grid_y_module_replication():
    """Test module replication along grid_y axis."""
    grid_y_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-TOWER-Y
  name: "Vertical Bay Tower"
spatial_structure:
  storeys:
    - id: L1
      name: "Ground Floor"
      elevation: 0.00
      height: 3.50
grids:
  axes_x:
    "1": 0.0
    "2": 6.0
  axes_y:
    "A": 0.0
    "B": 6.0
    "C": 12.0
    "D": 18.0
materials:
  - id: MAT_CONC
    name: "Concrete"
    category: concrete
    unit_cost_ref: REF-CONC
modules:
  - id: BAY_Y
    name: "Y Bay Module"
    local_grids:
      axes_x:
        "1": 0.0
        "2": 6.0
      axes_y:
        "A": 0.0
        "B": 6.0
    elements:
      - class: IfcColumn
        tag: COL-1
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.30
          depth: 0.30
        placement:
          grid: ["1", "A"]
          base_storey: L1
          top_storey: L1
      - class: IfcColumn
        tag: COL-2
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.30
          depth: 0.30
        placement:
          grid: ["1", "B"]
          base_storey: L1
          top_storey: L1
instances:
  - module: BAY_Y
    replicate:
      module: BAY_Y
      count: 3
      along: grid_y
      prefix_pattern: "ROW{index}_"
"""
    manifest = ProjectManifest.model_validate(yaml.safe_load(grid_y_yaml))
    columns = [e for e in manifest.elements if isinstance(e, IfcColumn)]

    # 3 bays along Y * 2 columns = 6 columns
    assert len(columns) == 6

    # Verify grid remapping along Y:
    # ROW1: A -> A, B -> B
    # ROW2: A -> B, B -> C
    # ROW3: A -> C, B -> D
    u1_cols = {e.tag: e.placement.grid for e in columns if e.tag.startswith("ROW1_")}
    assert u1_cols["ROW1_COL-1"] == ("1", "A")
    assert u1_cols["ROW1_COL-2"] == ("1", "B")

    u2_cols = {e.tag: e.placement.grid for e in columns if e.tag.startswith("ROW2_")}
    assert u2_cols["ROW2_COL-1"] == ("1", "B")
    assert u2_cols["ROW2_COL-2"] == ("1", "C")

    u3_cols = {e.tag: e.placement.grid for e in columns if e.tag.startswith("ROW3_")}
    assert u3_cols["ROW3_COL-1"] == ("1", "C")
    assert u3_cols["ROW3_COL-2"] == ("1", "D")
