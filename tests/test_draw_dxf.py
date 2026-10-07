"""
Unit tests for 2D AutoCAD DXF Exporter engine (debim.draw.dxf) and CLI integration.
"""

from pathlib import Path
import pytest
import yaml
import ezdxf
from typer.testing import CliRunner

from debim.cli import app
from debim.draw import export_2d_dxf
from debim.schema import ProjectManifest, load_manifest

FARNSWORTH_PATH = Path("examples/farnsworth_house/project.yaml")
runner = CliRunner()


def test_dxf_export_farnsworth(tmp_path: Path):
    """Test DXF export on Farnsworth House model and verify layers, units, and styles."""
    assert FARNSWORTH_PATH.exists()
    manifest = load_manifest(FARNSWORTH_PATH)

    dxf_file = tmp_path / "farnsworth.dxf"
    res_path = export_2d_dxf(
        manifest_or_resolved=manifest,
        output_path=dxf_file,
        storey_id="Main_Floor",
        cut_offset_z=1.20,
        units="mm",
    )

    assert res_path.exists()

    # Re-read file using ezdxf.readfile to verify validity
    doc = ezdxf.readfile(res_path)

    # Header check
    assert doc.header["$INSUNITS"] == 4  # 4 = mm
    assert doc.header["$MEASUREMENT"] == 1  # 1 = Metric

    # Thai Text Styles check
    style_names = [s.dxf.name for s in doc.styles]
    assert "THAI" in style_names
    assert "TH_SARABUN" in style_names

    # Layer hierarchy check
    layer_names = [layer.dxf.name for layer in doc.layers]
    expected_layers = ["A-WALL", "S-COLS", "A-DOOR", "A-WIND", "A-GRID", "A-DIMS"]
    for l in expected_layers:
        assert l in layer_names

    # Entity checks
    msp = doc.modelspace()
    entities = list(msp)
    assert len(entities) > 0

    # Column solid hatch check on S-COLS
    cols_hatches = [e for e in entities if e.dxftype() == "HATCH" and e.dxf.layer == "S-COLS"]
    assert len(cols_hatches) > 0

    # Wall lines on A-WALL
    wall_polys = [e for e in entities if e.dxf.layer == "A-WALL"]
    assert len(wall_polys) > 0

    # Grid lines & text on A-GRID
    grid_lines = [e for e in entities if e.dxf.layer == "A-GRID"]
    assert len(grid_lines) > 0


def test_dxf_export_synthetic_model(tmp_path: Path):
    """Test DXF export on synthetic BIM model with doors, windows, columns, and dimensions."""
    synthetic_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-DXF-TEST
  name: DXF Test Model
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
  tag: WALL-1
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
"""
    manifest = ProjectManifest.model_validate(yaml.safe_load(synthetic_yaml))

    dxf_file = tmp_path / "synthetic_m.dxf"
    # Export in meters
    res_path = export_2d_dxf(
        manifest_or_resolved=manifest,
        output_path=dxf_file,
        storey_id="Ground",
        cut_offset_z=1.20,
        units="m",
    )

    doc = ezdxf.readfile(res_path)
    assert doc.header["$INSUNITS"] == 6  # 6 = meters

    msp = doc.modelspace()
    entities = list(msp)

    # Check Window lines on A-WIND
    wind_elems = [e for e in entities if e.dxf.layer == "A-WIND"]
    assert len(wind_elems) > 0

    # Check Door arc on A-DOOR
    door_arcs = [e for e in entities if e.dxftype() == "ARC" and e.dxf.layer == "A-DOOR"]
    assert len(door_arcs) > 0

    # Check Dimension lines and text on A-DIMS
    dim_texts = [e for e in entities if e.dxftype() == "TEXT" and e.dxf.layer == "A-DIMS"]
    assert len(dim_texts) > 0


def test_cli_export_dxf(tmp_path: Path):
    """Test debim draw export-dxf CLI command execution."""
    manifest_file = tmp_path / "project.yaml"
    manifest_file.write_text("""
schema: IFC4-Minimal
project:
  id: PRJ-CLI-DXF
  name: CLI DXF Test
spatial_structure:
  storeys:
  - id: L1
    name: Level 1
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
- id: CONCRETE
  name: Structural Concrete
  category: masonry
  unit_cost_ref: MAT-CONC-01
elements:
- class: IfcColumn
  tag: C1
  material: CONCRETE
  profile:
    shape: BOX
    width: 0.3
    depth: 0.3
  placement:
    grid: ['1', 'A']
    base_storey: L1
    top_storey: L1
    offset_top: [0.0, 0.0, 3.0]
""", encoding="utf-8")

    out_dxf = tmp_path / "dist" / "plan.dxf"
    result = runner.invoke(
        app,
        ["draw", "export-dxf", "-m", str(manifest_file), "-o", str(out_dxf), "-u", "mm"],
    )

    assert result.exit_code == 0
    assert "2D AutoCAD DXF Export Successful!" in result.output
    assert out_dxf.exists()

    # Read back generated DXF
    doc = ezdxf.readfile(out_dxf)
    assert doc.header["$INSUNITS"] == 4
