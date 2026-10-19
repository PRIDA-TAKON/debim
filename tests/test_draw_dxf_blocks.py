"""
Unit tests for DXF Reusable Blocks and Standard CAD Layer Segregation (debim.draw.dxf).
"""

from pathlib import Path
import pytest
import yaml
import ezdxf

from debim.draw import export_2d_dxf
from debim.schema import ProjectManifest, load_manifest

FARNSWORTH_PATH = Path("examples/farnsworth_house/project.debim")


def test_dxf_layers_and_block_definitions(tmp_path: Path):
    """Verify that standard AIA/ISO CAD layers and reusable block definitions exist in exported DXF."""
    synthetic_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-DXF-BLOCKS
  name: DXF Reusable Blocks Test Model
spatial_structure:
  storeys:
  - id: L1
    name: Level 1
    elevation: 0.0
    height: 3.2
grids:
  axes_x:
    '1': 0.0
    '2': 6.0
  axes_y:
    A: 0.0
    B: 5.0
materials:
- id: CONCRETE
  name: Structural Concrete
  category: masonry
  unit_cost_ref: MAT-CONC-01
elements:
- class: IfcColumn
  tag: C1-1
  material: CONCRETE
  profile:
    shape: BOX
    width: 0.40
    depth: 0.40
  placement:
    grid: ['1', 'A']
    base_storey: L1
    top_storey: L1
    offset_top: [0.0, 0.0, 3.2]
- class: IfcColumn
  tag: C1-2
  material: CONCRETE
  profile:
    shape: BOX
    width: 0.40
    depth: 0.40
  placement:
    grid: ['2', 'A']
    base_storey: L1
    top_storey: L1
    offset_top: [0.0, 0.0, 3.2]
- class: IfcBeam
  tag: B1-1
  material: CONCRETE
  profile:
    shape: BOX
    width: 0.30
    depth: 0.50
  placement:
    from_grid: ['1', 'A']
    to_grid: ['2', 'A']
    storey: L1
- class: IfcWall
  tag: W1
  material: CONCRETE
  thickness: 0.20
  height: 3.0
  placement:
    from_grid: ['1', 'A']
    to_grid: ['2', 'A']
    storey: L1
  children:
  - class: IfcDoor
    tag: D1-Single
    dimensions:
      width: 0.90
      height: 2.10
    offset_distance: 1.20
    sill_height: 0.0
  - class: IfcDoor
    tag: D2-Double
    dimensions:
      width: 1.60
      height: 2.10
    offset_distance: 3.20
    sill_height: 0.0
  - class: IfcWindow
    tag: W1-Single
    dimensions:
      width: 1.00
      height: 1.50
    offset_distance: 4.80
    sill_height: 0.90
- class: IfcSanitaryTerminal
  tag: WC-1
  predefined_type: TOILET
  placement:
    grid: ['1', 'B']
    storey: L1
  dimensions:
    width: 0.45
    depth: 0.70
    height: 0.80
"""
    manifest = ProjectManifest.model_validate(yaml.safe_load(synthetic_yaml))

    dxf_path = tmp_path / "blocks_test.dxf"
    res_path = export_2d_dxf(
        manifest_or_resolved=manifest,
        output_path=dxf_path,
        storey_id="L1",
        cut_offset_z=1.20,
        units="mm",
    )

    assert res_path.exists()
    doc = ezdxf.readfile(res_path)

    # 1. Verify Standard CAD Layers
    layer_dict = {layer.dxf.name: layer for layer in doc.layers}
    expected_standard_layers = {
        "A-WALL": (7, 50),
        "S-COLS": (3, 50),
        "S-BEAM": (4, 25),
        "A-DOOR": (2, 25),
        "A-GLAZ": (4, 25),
        "DIM-ANNO": (5, 18),
        "GRID-ANNO": (1, 18),
        "A-SANR": (6, 25),
    }

    for layer_name, (expected_color, expected_lw) in expected_standard_layers.items():
        assert layer_name in layer_dict, f"Layer {layer_name} missing"
        layer_obj = layer_dict[layer_name]
        assert layer_obj.dxf.color == expected_color
        assert layer_obj.dxf.lineweight == expected_lw

    # 2. Verify Reusable DXF Blocks
    block_names = set(b.name for b in doc.blocks)
    expected_blocks = {"D1", "D2", "W1", "W2", "C1", "SANR_WC", "SANR_BASIN", "SANR_FIXTURE", "GRID_BUBBLE"}
    for blk in expected_blocks:
        assert blk in block_names, f"Block definition {blk} missing from doc.blocks"

    # 3. Verify Modelspace Insertions (INSERT Entities)
    msp = doc.modelspace()
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    assert len(inserts) > 0

    inserted_block_names = set(ins.dxf.name for ins in inserts)
    assert "C1" in inserted_block_names
    assert "D1" in inserted_block_names or "D2" in inserted_block_names
    assert "W1" in inserted_block_names
    assert "GRID_BUBBLE" in inserted_block_names

    # Verify Grid Bubble Attribute
    grid_inserts = [ins for ins in inserts if ins.dxf.name == "GRID_BUBBLE"]
    assert len(grid_inserts) >= 2
    grid_attribs = [attrib.dxf.text for ins in grid_inserts for attrib in ins.attribs]
    assert "1" in grid_attribs or "A" in grid_attribs

    # Verify Beams on S-BEAM with DASHED linetype
    beam_lines = [e for e in msp if e.dxf.layer == "S-BEAM"]
    assert len(beam_lines) > 0
    for b_line in beam_lines:
        assert b_line.dxf.linetype == "DASHED"


def test_dxf_farnsworth_block_hierarchy(tmp_path: Path):
    """Verify DXF block hierarchy and layer segregation on Farnsworth House model."""
    assert FARNSWORTH_PATH.exists()
    manifest = load_manifest(FARNSWORTH_PATH)

    dxf_path = tmp_path / "farnsworth_blocks.dxf"
    res_path = export_2d_dxf(
        manifest_or_resolved=manifest,
        output_path=dxf_path,
        storey_id="Main_Floor",
        cut_offset_z=1.20,
        units="mm",
    )

    doc = ezdxf.readfile(res_path)
    msp = doc.modelspace()

    # Block definitions check
    block_names = set(b.name for b in doc.blocks)
    assert "C1" in block_names
    assert "GRID_BUBBLE" in block_names

    # Check that modelspace contains INSERT block references for columns and grid bubbles
    column_inserts = [e for e in msp if e.dxftype() == "INSERT" and e.dxf.layer == "S-COLS"]
    assert len(column_inserts) > 0

    grid_inserts = [e for e in msp if e.dxftype() == "INSERT" and e.dxf.layer == "GRID-ANNO"]
    assert len(grid_inserts) > 0
