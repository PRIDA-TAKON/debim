"""
Unit tests for 2D Cut-Plane & Geometry Projection Engine (debim.draw.projection).
"""

from pathlib import Path
import pytest
import yaml
from shapely.geometry import MultiPolygon, Polygon

from debim.draw import (
    CutElement,
    CutPlaneResult,
    GridLine2D,
    ProjectionElement,
    project_2d_floor_plan,
    slice_storey,
)
from debim.schema import ProjectManifest, load_manifest

FARNSWORTH_PATH = Path("examples/farnsworth_house/project.yaml")


def test_farnsworth_house_slice():
    """Test 2D floor plan projection on Farnsworth House model."""
    assert FARNSWORTH_PATH.exists()
    manifest = load_manifest(FARNSWORTH_PATH)

    result = slice_storey(manifest, storey_id="Main_Floor", cut_offset_z=1.20)

    assert isinstance(result, CutPlaneResult)
    assert result.storey_id == "Main_Floor"
    assert result.storey_elevation == 1.6
    assert result.cut_offset_z == 1.20
    assert result.cut_elevation == pytest.approx(2.8)

    # Heavy Cut elements check (Columns + Core Walls)
    heavy_tags = {e.tag for e in result.heavy_cut_elements}
    assert "CORE-SOUTH" in heavy_tags
    assert "CORE-NORTH" in heavy_tags
    assert "CORE-WEST" in heavy_tags
    assert "CORE-EAST" in heavy_tags

    for i in range(1, 5):
        assert f"COL-A{i}" in heavy_tags
        assert f"COL-B{i}" in heavy_tags

    # Medium Cut elements check (Glass Walls)
    medium_tags = {e.tag for e in result.medium_cut_elements}
    assert "GLASS-SOUTH" in medium_tags
    assert "GLASS-NORTH" in medium_tags
    assert "GLASS-WEST" in medium_tags
    assert "GLASS-EAST" in medium_tags

    # Low Projection elements check (Slabs)
    proj_tags = {e.tag for e in result.low_projection_elements}
    assert "SLAB-MAIN" in proj_tags
    assert "SLAB-TERRACE" in proj_tags

    # Grid lines check
    grid_ids = {g.id for e in result.grid_lines for g in [e]}
    assert "G0" in grid_ids
    assert "G6" in grid_ids
    assert "GA" in grid_ids
    assert "GB" in grid_ids

    # Bounding box check
    min_x, min_y, max_x, max_y = result.bounds
    assert min_x < -1.5
    assert max_x > 23.5
    assert min_y < -6.7
    assert max_y > 8.8


def test_synthetic_model_wall_openings_and_fittings():
    """Test 2D slicing with wall openings (doors/windows), stairs, and sanitary fixtures."""
    synthetic_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-TEST-2D
  name: Test 2D Blueprint Model
spatial_structure:
  storeys:
  - id: Ground
    name: Ground Floor
    elevation: 0.0
    height: 3.0
grids:
  axes_x:
    '1': 0.0
    '2': 6.0
  axes_y:
    A: 0.0
    B: 4.0
materials:
- id: CONCRETE
  name: Structural Concrete
  category: masonry
  unit_cost_ref: MAT-CONC-01
- id: CERAMIC
  name: Ceramic Tile
  category: masonry
  unit_cost_ref: MAT-TILE-01
elements:
- class: IfcColumn
  tag: COL-1
  material: CONCRETE
  profile:
    shape: BOX
    width: 0.4
    depth: 0.4
  placement:
    grid: ['1', 'A']
    base_storey: Ground
    top_storey: Ground
    offset_top: [0.0, 0.0, 3.0]
- class: IfcWall
  tag: WALL-MAIN
  material: CONCRETE
  thickness: 0.20
  height: 2.80
  placement:
    from_grid: ['1', 'A']
    to_grid: ['2', 'A']
    storey: Ground
  children:
  - class: IfcDoor
    tag: DOOR-1
    dimensions:
      width: 0.90
      height: 2.10
    offset_distance: 1.50
    sill_height: 0.0
  - class: IfcWindow
    tag: WIN-1
    dimensions:
      width: 1.20
      height: 1.50
    offset_distance: 3.50
    sill_height: 0.90
- class: IfcSlab
  tag: SLAB-GROUND
  material: CONCRETE
  thickness: 0.15
  placement:
    boundary: [['1', 'A'], ['2', 'A'], ['2', 'B'], ['1', 'B']]
    storey: Ground
- class: IfcSanitaryTerminal
  tag: WC-1
  terminal_type: WATER_CLOSET
  material: CERAMIC
  placement:
    grid: ['1', 'B']
    storey: Ground
    offset_x: 1.0
    offset_y: -1.0
    offset_z: 0.0
"""
    manifest = ProjectManifest.model_validate(yaml.safe_load(synthetic_yaml))

    # Slice at Z = 1.20m
    result = project_2d_floor_plan(manifest, storey_id="Ground", cut_offset_z=1.20)

    assert result.cut_elevation == 1.20
    assert len(result.cut_elements) >= 3  # Wall (with voids), Door cut, Window cut, Column cut

    cut_tags = {e.tag for e in result.cut_elements}
    assert "WALL-MAIN" in cut_tags
    assert "DOOR-1" in cut_tags
    assert "WIN-1" in cut_tags
    assert "COL-1" in cut_tags

    # Verify WALL-MAIN has opening subtracted (its area is less than un-cut rectangle 6.0 * 0.2 = 1.2m2)
    wall_elem = next(e for e in result.cut_elements if e.tag == "WALL-MAIN")
    uncut_area = 6.0 * 0.20
    assert wall_elem.geometry.area < uncut_area - 0.3  # openings subtracted

    # Verify WC-1 is in low_projection
    proj_tags = {e.tag for e in result.projection_elements}
    assert "WC-1" in proj_tags
    assert "SLAB-GROUND" in proj_tags


def test_window_above_cut_plane():
    """Test that windows above cut-plane are not cut in 2D section."""
    synthetic_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-TEST-WINDOW
  name: Test High Window Model
spatial_structure:
  storeys:
  - id: Ground
    name: Ground Floor
    elevation: 0.0
    height: 3.0
grids:
  axes_x:
    '1': 0.0
    '2': 5.0
  axes_y:
    A: 0.0
    B: 5.0
materials:
- id: M1
  name: Concrete
  category: masonry
  unit_cost_ref: MAT-1
elements:
- class: IfcWall
  tag: WALL-1
  material: M1
  thickness: 0.20
  height: 2.80
  placement:
    from_grid: ['1', 'A']
    to_grid: ['2', 'A']
    storey: Ground
  children:
  - class: IfcWindow
    tag: WIN-HIGH
    dimensions:
      width: 1.0
      height: 0.8
    offset_distance: 2.0
    sill_height: 2.0  # Window starts at Z=2.0m
"""
    manifest = ProjectManifest.model_validate(
        yaml.safe_load(synthetic_yaml)
    )

    # Slice at Z = 1.20m (below window sill height of 2.0m)
    res_low = slice_storey(manifest, "Ground", cut_offset_z=1.20)
    low_cut_tags = {e.tag for e in res_low.cut_elements}
    assert "WALL-1" in low_cut_tags
    assert "WIN-HIGH" not in low_cut_tags  # Not cut at Z=1.2m

    # Slice at Z = 2.20m (intersects window at Z=2.0m..2.8m)
    res_high = slice_storey(manifest, "Ground", cut_offset_z=2.20)
    high_cut_tags = {e.tag for e in res_high.cut_elements}
    assert "WALL-1" in high_cut_tags
    assert "WIN-HIGH" in high_cut_tags  # Intersects cut plane at Z=2.2m
